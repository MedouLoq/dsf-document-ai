"""Excel output for the liasse-fiscale pipeline.

One workbook per filing with three sheets — Identification, Bilan,
Compte de Résultat — keeping the original French labels and DSF row
references, with totals highlighted and negatives in red.
"""
import logging
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

logger = logging.getLogger(__name__)

# ── Style constants ──────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="2E7D32")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
SUBHEADER_FILL = PatternFill("solid", fgColor="C8E6C9")
SUBHEADER_FONT = Font(name="Arial", bold=True, size=10)
TOTAL_FILL = PatternFill("solid", fgColor="FFF9C4")
TOTAL_FONT = Font(name="Arial", bold=True, size=10)
NORMAL_FONT = Font(name="Arial", size=10)
BOLD_FONT = Font(name="Arial", bold=True, size=10)
NEGATIVE_FONT = Font(name="Arial", size=10, color="FF0000")
NEGATIVE_BOLD_FONT = Font(name="Arial", bold=True, size=10, color="FF0000")
TITLE_FONT = Font(name="Arial", bold=True, size=14, color="2E7D32")
SUBTITLE_FONT = Font(name="Arial", bold=True, size=12, color="2E7D32")

THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")
NUMBER_FORMAT = '#,##0'

TOTAL_REFS = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"}


def _apply_border(ws, min_row, max_row, min_col, max_col):
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.border = THIN_BORDER


def _write_number(ws, row, col, value, font=None, is_total=False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.number_format = NUMBER_FORMAT
    cell.alignment = RIGHT
    if value is not None and isinstance(value, (int, float)) and value < 0:
        cell.font = NEGATIVE_BOLD_FONT if is_total else NEGATIVE_FONT
    else:
        cell.font = font or NORMAL_FONT
    return cell


# ══════════════════════════════════════════════════════
#  IDENTIFICATION SHEET
# ══════════════════════════════════════════════════════

def build_identification_sheet(wb, data: dict):
    ws = wb.create_sheet("Identification")

    ws.merge_cells("A1:D1")
    ws["A1"] = "A1. IDENTIFICATION DE L'ENTREPRISE"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = CENTER

    fields = [
        ("Nom ou dénomination sociale", data.get("nom_entreprise", "")),
        ("Sigle ou enseigne", data.get("sigle", "")),
        ("NIF", data.get("nif", "")),
        ("Date de dépôt", data.get("date_depot", "")),
        ("Date d'ouverture de l'exercice", data.get("date_ouverture_exercice", "")),
        ("Date de clôture de l'exercice", data.get("date_cloture_exercice", "")),
        ("Premier exercice (O/N)", data.get("premier_exercice", "")),
        ("Dernier exercice (O/N)", data.get("dernier_exercice", "")),
        ("Activité principale exercée", data.get("activite_principale", "")),
        ("Activités secondaires", data.get("activites_secondaires", "")),
        ("Forme juridique", data.get("forme_juridique", "")),
        ("Date de création", data.get("date_creation", "")),
        ("N° registre de commerce", data.get("numero_registre_commerce", "")),
        ("Adresse complète", data.get("adresse_complete", "")),
        ("Pays", data.get("pays", "")),
        ("Téléphone", data.get("telephone", "")),
        ("E-mail", data.get("email", "")),
    ]

    row = 3
    for label, value in fields:
        ws.cell(row=row, column=1, value=label).font = BOLD_FONT
        ws.cell(row=row, column=1).alignment = LEFT
        ws.cell(row=row, column=2, value=value or "").font = NORMAL_FONT
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        row += 1

    # Contacts
    row += 1
    ws.cell(row=row, column=1, value="CONTACTS").font = SUBTITLE_FONT
    ws.cell(row=row, column=1).fill = SUBHEADER_FILL
    row += 1

    contacts = [
        ("Représentant légal", [
            ("Nom", data.get("representant_legal_nom", "")),
            ("Fonction", data.get("representant_legal_fonction", "")),
            ("Téléphone", data.get("representant_legal_telephone", "")),
            ("E-mail", data.get("representant_legal_email", "")),
        ]),
        ("Responsable comptabilité", [
            ("Nom", data.get("responsable_comptabilite_nom", "")),
            ("Fonction", data.get("responsable_comptabilite_fonction", "")),
            ("Téléphone", data.get("responsable_comptabilite_telephone", "")),
            ("E-mail", data.get("responsable_comptabilite_email", "")),
        ]),
        ("Cabinet comptable", [
            ("Nom", data.get("cabinet_comptable_nom", "")),
            ("Adresse", data.get("cabinet_comptable_adresse", "")),
            ("Téléphone", data.get("cabinet_comptable_telephone", "")),
            ("E-mail", data.get("cabinet_comptable_email", "")),
        ]),
    ]

    for section_name, fields_list in contacts:
        ws.cell(row=row, column=1, value=section_name).font = BOLD_FONT
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="E8F5E9")
        row += 1
        for label, value in fields_list:
            ws.cell(row=row, column=2, value=label).font = BOLD_FONT
            ws.cell(row=row, column=3, value=value or "").font = NORMAL_FONT
            row += 1
        row += 1

    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 30


# ══════════════════════════════════════════════════════
#  BILAN SHEET
# ══════════════════════════════════════════════════════

def build_bilan_sheet(wb, data: dict):
    ws = wb.create_sheet("Bilan")

    exercice = data.get("exercice_clos", "")

    ws.merge_cells("A1:F1")
    ws["A1"] = f"B11. BILAN — Exercice clos au {exercice}" if exercice else "B11. BILAN"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = CENTER

    # Headers
    headers = [("Section", 1), ("Réf", 2), ("Libellé", 3),
               ("Brut", 4), ("Amort. & Prov.", 5), ("Net", 6), ("Net N-1", 7)]
    for label, col in headers:
        c = ws.cell(row=3, column=col, value=label)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER

    row = 4

    # ── ACTIF ──
    ws.cell(row=row, column=1, value="ACTIF").font = SUBTITLE_FONT
    ws.cell(row=row, column=1).fill = SUBHEADER_FILL
    for c in range(1, 8):
        ws.cell(row=row, column=c).fill = SUBHEADER_FILL
    row += 1

    actif = data.get("actif", [])
    for item in actif:
        ref = str(item.get("ref", ""))
        is_total = ref.upper() in TOTAL_REFS
        font = TOTAL_FONT if is_total else NORMAL_FONT

        ws.cell(row=row, column=1, value=item.get("section", "")).font = font
        ws.cell(row=row, column=1).alignment = LEFT
        ws.cell(row=row, column=2, value=ref).font = font
        ws.cell(row=row, column=2).alignment = CENTER
        ws.cell(row=row, column=3, value=item.get("label", "")).font = font
        ws.cell(row=row, column=3).alignment = LEFT

        _write_number(ws, row, 4, item.get("brut", 0), font, is_total)
        _write_number(ws, row, 5, item.get("amort", 0), font, is_total)
        _write_number(ws, row, 6, item.get("net", 0), font, is_total)
        _write_number(ws, row, 7, item.get("net_prev", 0), font, is_total)

        if is_total:
            for c in range(1, 8):
                ws.cell(row=row, column=c).fill = TOTAL_FILL
        row += 1

    # ── PASSIF ──
    row += 1
    ws.cell(row=row, column=1, value="PASSIF").font = SUBTITLE_FONT
    ws.cell(row=row, column=1).fill = SUBHEADER_FILL
    for c in range(1, 8):
        ws.cell(row=row, column=c).fill = SUBHEADER_FILL
    row += 1

    passif = data.get("passif", [])
    for item in passif:
        ref = str(item.get("ref", ""))
        is_total = ref.upper() in TOTAL_REFS
        font = TOTAL_FONT if is_total else NORMAL_FONT

        ws.cell(row=row, column=1, value=item.get("section", "")).font = font
        ws.cell(row=row, column=1).alignment = LEFT
        ws.cell(row=row, column=2, value=ref).font = font
        ws.cell(row=row, column=2).alignment = CENTER
        ws.cell(row=row, column=3, value=item.get("label", "")).font = font
        ws.cell(row=row, column=3).alignment = LEFT

        # Passif doesn't have brut/amort
        _write_number(ws, row, 6, item.get("net", 0), font, is_total)
        _write_number(ws, row, 7, item.get("net_prev", 0), font, is_total)

        if is_total:
            for c in range(1, 8):
                ws.cell(row=row, column=c).fill = TOTAL_FILL
        row += 1

    # ── Soldes intermédiaires ──
    sig = data.get("soldes_intermediaires", [])
    if sig:
        row += 1
        ws.cell(row=row, column=1, value="Soldes Intermédiaires de Gestion").font = SUBTITLE_FONT
        ws.cell(row=row, column=1).fill = SUBHEADER_FILL
        for c in range(1, 8):
            ws.cell(row=row, column=c).fill = SUBHEADER_FILL
        row += 1

        for item in sig:
            ref = str(item.get("ref", ""))
            ws.cell(row=row, column=2, value=ref).font = BOLD_FONT
            ws.cell(row=row, column=2).alignment = CENTER
            ws.cell(row=row, column=3, value=item.get("label", "")).font = BOLD_FONT
            ws.cell(row=row, column=3).alignment = LEFT
            _write_number(ws, row, 6, item.get("net", 0), BOLD_FONT, True)
            _write_number(ws, row, 7, item.get("net_prev", 0), BOLD_FONT, True)
            row += 1

    _apply_border(ws, 3, row - 1, 1, 7)

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 8
    ws.column_dimensions["C"].width = 42
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 16
    ws.column_dimensions["F"].width = 16
    ws.column_dimensions["G"].width = 16


# ══════════════════════════════════════════════════════
#  COMPTE DE RÉSULTAT SHEET
# ══════════════════════════════════════════════════════

def build_compte_resultat_sheet(wb, data: dict):
    ws = wb.create_sheet("Compte de Résultat")

    exercice = data.get("exercice", "")
    prev = data.get("exercice_precedent", "")

    ws.merge_cells("A1:D1")
    ws["A1"] = f"B12. COMPTE DE RÉSULTAT — Exercice {exercice}" if exercice else "B12. COMPTE DE RÉSULTAT"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = CENTER

    # Headers
    headers = [("Réf", 1), ("Libellé", 2),
               (f"Exercice {exercice}" if exercice else "Exercice", 3),
               (f"Rappel {prev}" if prev else "Rappel N-1", 4)]
    for label, col in headers:
        c = ws.cell(row=3, column=col, value=label)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER

    row = 4

    # Determination du resultat
    ws.cell(row=row, column=1, value="I. Détermination du résultat").font = SUBTITLE_FONT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    ws.cell(row=row, column=1).fill = SUBHEADER_FILL
    for c in range(1, 5):
        ws.cell(row=row, column=c).fill = SUBHEADER_FILL
    row += 1

    det = data.get("determination_resultat", [])
    for item in det:
        ref = str(item.get("ref", ""))
        is_total = ref.upper() in TOTAL_REFS
        font = TOTAL_FONT if is_total else NORMAL_FONT

        ws.cell(row=row, column=1, value=ref).font = font
        ws.cell(row=row, column=1).alignment = CENTER
        ws.cell(row=row, column=2, value=item.get("label", "")).font = font
        ws.cell(row=row, column=2).alignment = LEFT
        _write_number(ws, row, 3, item.get("current", 0), font, is_total)
        _write_number(ws, row, 4, item.get("prev", 0), font, is_total)

        if is_total:
            for c in range(1, 5):
                ws.cell(row=row, column=c).fill = TOTAL_FILL
        row += 1

    # SIG
    sig = data.get("soldes_intermediaires_gestion", [])
    if sig:
        row += 1
        ws.cell(row=row, column=1, value="II. Soldes Intermédiaires de Gestion").font = SUBTITLE_FONT
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        ws.cell(row=row, column=1).fill = SUBHEADER_FILL
        for c in range(1, 5):
            ws.cell(row=row, column=c).fill = SUBHEADER_FILL
        row += 1

        for item in sig:
            ref = str(item.get("ref", ""))
            ws.cell(row=row, column=1, value=ref).font = BOLD_FONT
            ws.cell(row=row, column=1).alignment = CENTER
            ws.cell(row=row, column=2, value=item.get("label", "")).font = BOLD_FONT
            ws.cell(row=row, column=2).alignment = LEFT
            _write_number(ws, row, 3, item.get("current", 0), BOLD_FONT, True)
            _write_number(ws, row, 4, item.get("prev", 0), BOLD_FONT, True)
            row += 1

    _apply_border(ws, 3, row - 1, 1, 4)

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 50
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18


# ══════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════

def build_excel(extracted_data: dict, output_path: str) -> str:
    """Build Excel workbook from extracted DSF data."""
    wb = Workbook()
    wb.remove(wb.active)

    if extracted_data.get("identification"):
        build_identification_sheet(wb, extracted_data["identification"])

    if extracted_data.get("bilan"):
        build_bilan_sheet(wb, extracted_data["bilan"])

    if extracted_data.get("compte_resultat"):
        build_compte_resultat_sheet(wb, extracted_data["compte_resultat"])

    if not wb.sheetnames:
        ws = wb.create_sheet("Info")
        ws["A1"] = "No data extracted. Check the PDF and logs."

    wb.save(output_path)
    logger.info(f"Excel saved to {output_path}")
    return output_path
