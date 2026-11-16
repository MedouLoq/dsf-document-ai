"""Pipeline 2 — handwritten single-page DSF statistical forms.

The "Déclaration Statistique et Fiscale" form is a printed grid where each
band has a row of printed account codes and, directly below, a row of
handwritten amounts. Scans arrive rotated, and some cells are split
diagonally. The pipeline:

1. fixes orientation (portrait scans of a landscape form),
2. asks Gemini to read every band column-by-column into a fixed schema,
3. optionally re-reads the diagonal "capital / reserves" cells with
   Google Document AI's Form Parser and fills any values Gemini left empty,
4. optionally corrects an off-by-one column shift in the charges band.
"""
import logging
import os
import re
from typing import Optional

from .gemini import parse_json_response
from .imaging import prepare_form_image

logger = logging.getLogger(__name__)

FORM_PROMPT = """You are reading a Mauritanian DSF (Déclaration Statistique et Fiscale) financial form.

THE FORM STRUCTURE:
This form has a header area and then a grid. The grid has horizontal BANDS.
Each band contains TWO rows:
  - ROW A: printed labels with account codes (like "64", "65", "66", "67", "68")
  - ROW B: handwritten values DIRECTLY BELOW each label

CRITICAL ALIGNMENT RULE:
Each handwritten value in Row B belongs to the label DIRECTLY ABOVE it in Row A.
The 1st value (leftmost) in Row B → 1st label (leftmost) in Row A.
The 2nd value in Row B → 2nd label in Row A.
Match them strictly by COLUMN POSITION, left to right.

IMPORTANT: Some label cells are WIDER than others. Match by VERTICAL GRID LINES, not cell width.

SPECIAL: DIAGONAL-SPLIT CELLS
Some cells in the "Dividendes/Résultat instance/Réserves/Report/Capital" row
are split diagonally with a curved line, with "22" in the upper-left and "23"
in the lower-right. The handwritten value may be written ACROSS the diagonal.
Read it as a single value. Do NOT treat these as empty.

NUMBER FORMAT:
- Comma = decimal separator: "4,923" → 4.923
- Parentheses = negative: "(11,140)" → -11.140
- All monetary values are in millions MRU
- Empty cell = null

NIF: Write EXACTLY as read from boxes, raw string, do NOT clean.
EFFECTIF SALARIÉ: integer.

Return ONLY valid JSON. No markdown fences. No commentary.

{
  "company_info": {
    "nom_raison_sociale": null, "nif_raw": null, "localisation": null,
    "activite_principale": null, "activite_secondaire": null,
    "forme_juridique": null, "sigle": null, "nom_enqueteur": null, "annee": null
  },
  "achats_et_stocks": {
    "achats_marchandises_600": null, "variation_stocks_marchandises_6031": null,
    "achats_matieres_premieres_601": null, "achats_emballages_602": null,
    "variation_stocks_matieres_prem_6031": null, "variation_stocks_emballages_6031": null,
    "achats_non_stockes_606": null, "achats_sous_traitance_61": null,
    "charges_externes_invest_62": null, "charges_externes_activite_63": null,
    "total_consommations_intermediaires": null
  },
  "charges_et_resultats": {
    "charges_pertes_diverses_64": null, "frais_personnel_65": null,
    "impots_taxes_66": null, "charges_financieres_67": null,
    "dotations_amort_prov_68": null, "total_charges_exploitation": null,
    "resultat_exploitation_82": null, "resultat_cessions_immo_85": null,
    "impots_resultat_86": null, "resultat_net_periode_87": null, "total_charges": null
  },
  "produits": {
    "ventes_marchandises_700": null, "prod_biens_vendue_7010": null,
    "production_exportee": null, "travaux_7012": null, "etudes_7015": null,
    "prestations_services_7017": null, "produits_activites_annexes_706": null,
    "production_stockee_71": null, "production_immobilisee_72": null,
    "produits_divers_74": null, "subvention_recue_76": null
  },
  "autres_produits_et_infos": {
    "produits_financiers_77": null, "reprises_78": null,
    "frais_immob_transferer_79": null, "total_produits": null,
    "effectif_salarie": null, "dividendes_versees": null,
    "resultat_instance_affectation": null, "reserves": null,
    "report_nouveau": null, "capital": null
  },
  "acquisitions": {
    "terrain_210": null, "agenc_installations_211": null, "construction_212": null,
    "installations_complexes_213": null, "materiel_exploitation_214": null,
    "materiel_transport_215": null, "materiel_bureau_informatique_216": null,
    "autres_immob_corp_218": null, "immob_en_cours_23": null, "total_acquisitions": null
  }
}"""


# ── Column-shift correction ─────────────────────────────────────────
# When the first cell of a band is empty, the model sometimes slides every
# value one column to the left. If a band starts with a value but has empty
# trailing cells, shift it right by one.
CHARGES_SEQ = [
    "charges_pertes_diverses_64", "frais_personnel_65", "impots_taxes_66",
    "charges_financieres_67", "dotations_amort_prov_68", "total_charges_exploitation",
]
RESULTS_SEQ = [
    "resultat_exploitation_82", "resultat_cessions_immo_85",
    "impots_resultat_86", "resultat_net_periode_87", "total_charges",
]


def fix_shift(data: dict) -> dict:
    charges = data.get("charges_et_resultats") or {}
    for seq in (CHARGES_SEQ, RESULTS_SEQ):
        vals = [charges.get(f) for f in seq]
        filled = [i for i, v in enumerate(vals) if v is not None]
        if len(filled) >= 2 and filled[0] == 0 and any(v is None for v in vals[filled[-1] + 1:]):
            for f, v in zip(seq, [None] + vals[:-1]):
                charges[f] = v
            logger.info("Fixed column shift in band starting at %s", seq[0])
    if charges:
        data["charges_et_resultats"] = charges
    return data


# ── Document AI patch for diagonal cells ────────────────────────────
DOCAI_FIELD_MAP = {
    "capital": "capital", "réserves": "reserves", "reserves": "reserves",
    "report": "report_nouveau", "résultat en instance": "resultat_instance_affectation",
    "affectation": "resultat_instance_affectation", "dividendes": "dividendes_versees",
    "effectif": "effectif_salarie", "total des produits": "total_produits",
}


def parse_amount(text: Optional[str]) -> Optional[float]:
    """'(11,140)' → -11.14 ; '4,923' → 4.923 ; '' → None"""
    if not text or not text.strip():
        return None
    s = text.strip()
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = re.sub(r"[^0-9.\-]", "", s.replace(" ", "").replace(",", "."))
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _layout_text(layout, text: str) -> str:
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return ""
    return "".join(text[int(s.start_index or 0):int(s.end_index or 0)] for s in layout.text_anchor.text_segments)


def patch_with_docai(data: dict, path: str, project_id: str, location: str, processor_id: str) -> dict:
    """Fill fields Gemini left empty using Document AI Form Parser key-value pairs."""
    try:
        from google.cloud import documentai

        client = documentai.DocumentProcessorServiceClient()
        name = client.processor_path(project_id, location, processor_id)
        with open(path, "rb") as fh:
            content = fh.read()
        mime = "application/pdf" if path.lower().endswith(".pdf") else "image/jpeg"
        doc = client.process_document(request=documentai.ProcessRequest(
            name=name, raw_document=documentai.RawDocument(content=content, mime_type=mime))).document

        autres = data.get("autres_produits_et_infos") or {}
        for page in doc.pages:
            for ff in page.form_fields:
                label = _layout_text(ff.field_name, doc.text).strip().lower()
                value = _layout_text(ff.field_value, doc.text).strip()
                for keyword, field_name in DOCAI_FIELD_MAP.items():
                    if keyword in label and autres.get(field_name) is None and value:
                        parsed = parse_amount(value)
                        if parsed is not None:
                            autres[field_name] = parsed
                            logger.info("DocAI filled %s=%s", field_name, parsed)
                        break
        data["autres_produits_et_infos"] = autres
    except Exception as exc:  # optional enhancement — never fail the extraction
        logger.warning("Document AI patch skipped: %s", exc)
    return data


class FormExtractor:
    def __init__(self, client, *, project_id: str = "", docai_location: str = "us",
                 docai_processor_id: str = "", apply_shift_fix: bool = False):
        self.client = client
        self.project_id = project_id
        self.docai_location = docai_location
        self.docai_processor_id = docai_processor_id
        self.apply_shift_fix = apply_shift_fix

    def extract(self, image_path: str) -> dict:
        image = prepare_form_image(image_path)
        raw = self.client.generate([(image, "image/jpeg")], FORM_PROMPT, temperature=0.1)
        data = parse_json_response(raw)
        if self.apply_shift_fix:
            data = fix_shift(data)
        if self.docai_processor_id and self.project_id:
            data = patch_with_docai(data, image_path, self.project_id, self.docai_location, self.docai_processor_id)
        data["_source_file"] = os.path.basename(image_path)
        return data
