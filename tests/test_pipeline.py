import json
from pathlib import Path

import numpy as np
import pytest
from openpyxl import load_workbook
from PIL import Image, ImageDraw

from dsf_ai.form import fix_shift, parse_amount
from dsf_ai.form_excel import COLUMNS, export_eretes
from dsf_ai.gemini import parse_json_response
from dsf_ai.imaging import drop_blank_pages, fix_rotation, is_blank
from dsf_ai.liasse import LiasseExtractor, normalise_section_code
from dsf_ai.liasse_excel import build_excel

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
LIASSE = json.loads((SAMPLES / "synthetic_liasse.json").read_text())
FORMS = json.loads((SAMPLES / "synthetic_forms.json").read_text())


# ── JSON parsing ────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Here you go:\n{"a": 1,}\nThanks',
    '{"a": [1, 2,], }',
])
def test_parse_json_response_tolerates_noise(raw):
    assert parse_json_response(raw)["a"] in (1, [1, 2])


def test_parse_json_response_rejects_non_json():
    with pytest.raises(ValueError):
        parse_json_response("no json here")


# ── Section codes ───────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [("A1", "A1"), (" a-1. ", "A1"), ("B11\n", "B11"), ("", "NONE"), ("NONE", "NONE")])
def test_normalise_section_code(raw, expected):
    assert normalise_section_code(raw) == expected


# ── Classify-then-extract pipeline with a fake model ────────────────
class FakeClient:
    """Answers classification prompts from a page plan, extraction prompts from the sample JSON."""

    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def generate(self, parts, prompt, **kwargs):
        self.calls.append((len(parts), prompt[:40]))
        if prompt.startswith("Look at this page"):
            # pages are encoded with their index in the red channel of pixel (0,0)
            from io import BytesIO
            idx = Image.open(BytesIO(parts[0][0])).getpixel((0, 0))[0]
            return self.plan[idx]
        if "A1" in prompt[:80]:
            return json.dumps(LIASSE["identification"])
        if "BILAN" in prompt[:80]:
            return json.dumps(LIASSE["bilan"])
        return "```json\n" + json.dumps(LIASSE["compte_resultat"]) + "\n```"


def _pages(n):
    imgs = []
    for i in range(n):
        img = Image.new("RGB", (60, 80), "white")
        img.putpixel((0, 0), (i, 0, 0))
        imgs.append(img)
    return imgs


def test_pipeline_stops_classifying_once_all_targets_found():
    plan = ["NONE", "A1", "B11", "NONE", "B12", "B13", "C21", "D31"]
    client = FakeClient(plan)
    result = LiasseExtractor(client).extract_images(_pages(len(plan)), "test.pdf")

    assert result["pages_classified"] == 5
    assert result["pages_skipped_early"] == 3
    assert result["page_classification"]["5"] == "B12"
    assert result["identification"]["nif"] == "00000000"
    assert len(result["bilan"]["actif"]) == len(LIASSE["bilan"]["actif"])
    assert result["compte_resultat"]["exercice"] == "2024"
    # each extraction call sends the target page + the following page
    extraction_calls = [c for c in client.calls if not c[1].startswith("Look at this page")]
    assert [n for n, _ in extraction_calls] == [2, 2, 2]


def test_pipeline_records_errors_without_crashing():
    class Broken(FakeClient):
        def generate(self, parts, prompt, **kw):
            if "BILAN" in prompt[:80]:
                return "not json"
            return super().generate(parts, prompt, **kw)

    result = LiasseExtractor(Broken(["A1", "B11", "B12"])).extract_images(_pages(3))
    assert result["identification"] and result["compte_resultat"] and not result["bilan"]
    assert any(k.startswith("error_B11") for k in result)


# ── Imaging ─────────────────────────────────────────────────────────
def test_blank_page_detection():
    blank = Image.new("RGB", (200, 200), "white")
    text = blank.copy()
    ImageDraw.Draw(text).rectangle([20, 20, 120, 60], fill="black")
    assert is_blank(blank) and not is_blank(text)
    assert drop_blank_pages([blank, text, blank]) == [text]


def test_fix_rotation_turns_portrait_to_landscape():
    portrait = np.full((300, 200, 3), 255, dtype=np.uint8)
    assert fix_rotation(portrait).shape[:2] == (200, 300)
    landscape = np.full((200, 300, 3), 255, dtype=np.uint8)
    assert fix_rotation(landscape) is landscape


# ── Handwritten-form helpers ────────────────────────────────────────
@pytest.mark.parametrize("text,value", [("4,923", 4.923), ("(11,140)", -11.14), ("", None), ("—", None), ("1 323", 1323.0)])
def test_parse_amount(text, value):
    assert parse_amount(text) == value


def test_fix_shift_moves_values_right_when_band_is_misaligned():
    data = {"charges_et_resultats": {
        "charges_pertes_diverses_64": 1.0, "frais_personnel_65": 2.0, "impots_taxes_66": 3.0,
        "charges_financieres_67": 4.0, "dotations_amort_prov_68": 5.0, "total_charges_exploitation": None,
    }}
    fixed = fix_shift(data)["charges_et_resultats"]
    assert fixed["charges_pertes_diverses_64"] is None
    assert fixed["frais_personnel_65"] == 1.0
    assert fixed["total_charges_exploitation"] == 5.0


def test_fix_shift_leaves_complete_band_alone():
    band = {k: float(i) for i, k in enumerate([
        "charges_pertes_diverses_64", "frais_personnel_65", "impots_taxes_66",
        "charges_financieres_67", "dotations_amort_prov_68", "total_charges_exploitation"], 1)}
    assert fix_shift({"charges_et_resultats": dict(band)})["charges_et_resultats"] == band


# ── Excel outputs ───────────────────────────────────────────────────
def test_liasse_excel_has_three_sheets_and_balanced_totals(tmp_path):
    out = tmp_path / "liasse.xlsx"
    build_excel(LIASSE, str(out))
    wb = load_workbook(out)
    assert wb.sheetnames == ["Identification", "Bilan", "Compte de Résultat"]
    totals = {}
    for row in wb["Bilan"].iter_rows(min_row=4, values_only=True):
        if row[1] in ("D", "H"):
            totals[row[1]] = row[5]
    assert totals["D"] == totals["H"] > 0


def test_eretes_export_one_row_per_company_with_formulas(tmp_path):
    out = tmp_path / "eretes.xlsx"
    export_eretes(FORMS, str(out))
    ws = load_workbook(out).active
    headers = [c.value for c in ws[1]]
    assert headers == [h for h, _ in COLUMNS]
    assert ws.max_row == 1 + len(FORMS)
    assert ws.cell(row=2, column=headers.index("Nom ou Raison sociale") + 1).value == FORMS[0]["company_info"]["nom_raison_sociale"]
    assert str(ws.cell(row=2, column=headers.index("Valeur ajouté") + 1).value).startswith("=")
