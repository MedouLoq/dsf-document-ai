"""Pipeline 1 — typed multi-page DSF filings ("liasse fiscale").

1. Classify each page by the section code printed in its green banner
   (A1, B11, B12, …), stopping as soon as all target sections are found.
2. For each target section, send the page *and the following page* to
   Gemini, because sections often spill over (e.g. ACTIF on one page,
   PASSIF on the next).
3. Return one JSON document per filing (see samples/synthetic_liasse.json).
"""
import logging
import os
from typing import List

from PIL import Image

from .gemini import parse_json_response
from .imaging import pdf_to_images, to_png_bytes

logger = logging.getLogger(__name__)

TARGET_SECTIONS = {"A1", "B11", "B12"}

CLASSIFIER_PROMPT = """Look at this page from a Mauritanian DSF (liasse fiscale) document.
Find the section code in the green banner header. It may be rotated or sideways.

Section codes look like: A1, B11, B12, B13, B14, C21, D31, D32, D33, D35, D36, E41, E42, etc.

Reply with ONLY the code, nothing else. No explanation. No punctuation.

If the page has NO section code (cover letter, blank page, signature page, attestation), reply: NONE
"""

IDENTIFICATION_PROMPT = """Extract data from the A1 "Identification de l'entreprise" section of a Mauritanian DSF document.
You are given 1 or 2 pages — the main A1 page and possibly a continuation page. Read ALL pages.
Pages may be rotated — read them regardless.

Return ONLY valid JSON, no markdown fences, no explanation:

{
  "nom_entreprise": "",
  "sigle": "",
  "nif": "",
  "date_depot": "",
  "date_ouverture_exercice": "",
  "date_cloture_exercice": "",
  "premier_exercice": "",
  "dernier_exercice": "",
  "activite_principale": "",
  "activites_secondaires": "",
  "forme_juridique": "",
  "date_creation": "",
  "numero_registre_commerce": "",
  "adresse_complete": "",
  "pays": "",
  "telephone": "",
  "email": "",
  "nombre_employes": "",
  "representant_legal_nom": "",
  "representant_legal_fonction": "",
  "representant_legal_telephone": "",
  "representant_legal_email": "",
  "responsable_comptabilite_nom": "",
  "responsable_comptabilite_fonction": "",
  "responsable_comptabilite_telephone": "",
  "responsable_comptabilite_email": "",
  "cabinet_comptable_nom": "",
  "cabinet_comptable_adresse": "",
  "cabinet_comptable_telephone": "",
  "cabinet_comptable_email": ""
}

Rules:
- Empty/blank fields → "" (empty string)
- Keep numbers, dates, text EXACTLY as written in the document
- French stays in French
- "nombre_employes": look for employee count, effectif, nombre de salariés, etc. on BOTH pages. If not found, use "".
- Combine information from BOTH pages if present
"""

BILAN_PROMPT = """Extract data from the BILAN (balance sheet) section B11 of a Mauritanian DSF document.
You are given 1 or 2 pages — the Bilan may be SPLIT across both pages (e.g. ACTIF on page 1, PASSIF on page 2, or the Soldes intermédiaires on page 2). Read ALL pages.
Pages may be rotated — read them regardless.

The ACTIF rows have columns: Brut, Amortissements, Net (current), and sometimes Net N-1 (previous year).
The PASSIF rows have: Net (current), and sometimes Net N-1 (previous year).
There may be a "Soldes intermédiaires de gestion" table (Capitaux permanents, Fond de roulement, Besoin en fond de roulement).

Return ONLY valid JSON, no markdown fences, no explanation.
Use EXACTLY the label as written in the document:

{
  "exercice_clos": "31/12/2024",
  "actif": [
    {"ref": "01", "label": "Immobilisations incorporelles", "section": "Actif immobilisé", "brut": 0, "amort": 0, "net": 0, "net_prev": 0}
  ],
  "passif": [
    {"ref": "51", "label": "Capital", "section": "Capitaux propres", "net": 0, "net_prev": 0}
  ],
  "soldes_intermediaires": [
    {"ref": "I", "label": "Capitaux permanents", "net": 0, "net_prev": 0}
  ]
}

Rules:
- Extract EVERY row from ALL pages, in document order
- "ref" = exact code (01, 03, 05... A, B, C, D, E, F, G, H, I, J, K)
- "label" = EXACT French text from the document
- "section" = subsection name (Actif immobilisé, Actif circulant, Comptes de régularisation, Capitaux propres, Emprunts et dettes)
- Numbers: integers only, no spaces, no dots, no decimals
- Negative: minus sign (e.g., -14450356)
- Empty/blank/dash: use 0
- If Net N-1 column doesn't exist, set net_prev to 0
- Total rows (A, B, C, D, E, F, G, H) must be included
- IMPORTANT: check BOTH pages for data — Passif or Soldes may be on the second page
"""

COMPTE_RESULTAT_PROMPT = """Extract data from the B12 "Résultat comptable" (income statement) section of a Mauritanian DSF document.
You are given 1 or 2 pages — the data may continue on the second page. Read ALL pages.
Pages may be rotated — read them regardless.

Columns: Exercice (current year), and sometimes Rappel exercice (previous year).
There may be a "Soldes intermédiaires de gestion" table at the bottom or on the next page.

Return ONLY valid JSON, no markdown fences, no explanation.
Use EXACTLY the label as written (labels vary between companies):

{
  "exercice": "2024",
  "exercice_precedent": "2023",
  "determination_resultat": [
    {"ref": "01", "label": "Prestation de Services", "current": 10439740, "prev": 0}
  ],
  "soldes_intermediaires_gestion": [
    {"ref": "H", "label": "Chiffre d'affaires (CA)", "current": 10439740, "prev": 0}
  ]
}

Rules:
- Extract EVERY row from ALL pages, in document order
- "ref" = exact code (01, 03, 05, 07... A, B, C, D, E, F, G, H, I, J, K, L)
- "label" = EXACT French text as written
- Numbers: integers only, no spaces, no decimals
- Negative: minus sign (e.g., -1840133)
- Empty cells: use 0
- If Rappel exercice column doesn't exist, set prev to 0
- Include total rows (A, B, C, D, E, F, G)
- IMPORTANT: check BOTH pages for data
"""


def normalise_section_code(raw: str) -> str:
    code = (raw or "").strip().upper()
    code = code.split()[0] if code else "NONE"
    code = code.rstrip(".,:;").strip()
    return {"A-1": "A1", "A_1": "A1"}.get(code, code)


class LiasseExtractor:
    """Classify-then-extract pipeline for multi-page DSF filings."""

    def __init__(self, client, dpi: int = 200):
        self.client = client
        self.dpi = dpi

    def _ask(self, images: List[Image.Image], prompt: str, max_size: int = 2048, max_tokens: int = 8192) -> str:
        parts = [(to_png_bytes(img, max_size=max_size), "image/png") for img in images]
        return self.client.generate(parts, prompt, max_tokens=max_tokens)

    def classify_page(self, image: Image.Image) -> str:
        return normalise_section_code(self._ask([image], CLASSIFIER_PROMPT, max_size=1536, max_tokens=16))

    def extract_identification(self, images):
        return parse_json_response(self._ask(images, IDENTIFICATION_PROMPT))

    def extract_bilan(self, images):
        return parse_json_response(self._ask(images, BILAN_PROMPT))

    def extract_compte_resultat(self, images):
        return parse_json_response(self._ask(images, COMPTE_RESULTAT_PROMPT))

    # ── entry points ────────────────────────────────────────────
    def extract_pdf(self, pdf_path: str) -> dict:
        return self.extract_images(pdf_to_images(pdf_path, dpi=self.dpi), os.path.basename(pdf_path))

    def extract_images(self, images: List[Image.Image], source_name: str = "unknown") -> dict:
        # Step 1 — classify, stopping early once every target has been seen
        page_codes = {}
        found = set()
        for i, img in enumerate(images):
            if found == TARGET_SECTIONS:
                logger.info("All targets found — skipping remaining %d pages", len(images) - i)
                break
            try:
                code = self.classify_page(img)
            except Exception as exc:
                logger.warning("Page %d: classification failed (%s)", i + 1, str(exc)[:80])
                code = "NONE"
            page_codes[i] = code
            if code in TARGET_SECTIONS:
                found.add(code)
            logger.info("Page %d: %-6s %s", i + 1, code, "target" if code in TARGET_SECTIONS else "skip")

        result = {
            "source_file": source_name,
            "total_pages": len(images),
            "pages_classified": len(page_codes),
            "pages_skipped_early": len(images) - len(page_codes),
            "page_classification": {str(k + 1): v for k, v in page_codes.items()},
            "identification": {},
            "bilan": {},
            "compte_resultat": {},
        }

        # Step 2 — extract each target from its page + the next one
        extracted = set()
        for i, code in page_codes.items():
            if code not in TARGET_SECTIONS or code in extracted:
                continue
            pages = images[i:i + 2]
            desc = f"pages {i + 1}-{i + len(pages)}"
            try:
                if code == "A1":
                    data = self.extract_identification(pages)
                    if data.get("nom_entreprise") or data.get("nif"):
                        result["identification"] = data
                        extracted.add(code)
                elif code == "B11":
                    data = self.extract_bilan(pages)
                    if data.get("actif") or data.get("passif"):
                        result["bilan"] = data
                        extracted.add(code)
                elif code == "B12":
                    data = self.extract_compte_resultat(pages)
                    if data.get("determination_resultat"):
                        result["compte_resultat"] = data
                        extracted.add(code)
                logger.info("%s from %s: %s", code, desc, "ok" if code in extracted else "empty")
            except Exception as exc:
                logger.error("Error extracting %s from %s: %s", code, desc, exc)
                result[f"error_{code}_page_{i + 1}"] = str(exc)

        n = sum(1 for k in ("identification", "bilan", "compte_resultat") if result[k])
        logger.info("Done: %d/3 sections | classified %d/%d pages", n, len(page_codes), len(images))
        return result
