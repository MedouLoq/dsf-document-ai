"""Generate the synthetic sample data shipped in samples/.

Everything here is fictional: company names, NIFs, people, addresses and
amounts are invented, and the totals are computed so the statements
balance. Run from the repo root:

    python scripts/make_samples.py
"""
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "samples"
random.seed(7)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_HAND = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"
GREEN = (46, 125, 50)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ═════════════════════════════════════════════════════════════════
#  1. Liasse fiscale — one fictional company
# ═════════════════════════════════════════════════════════════════
IDENTIFICATION = {
    "nom_entreprise": "SOCIÉTÉ EXEMPLE DE NÉGOCE SARL",
    "sigle": "SEN",
    "nif": "00000000",
    "date_depot": "28/03/2025",
    "date_ouverture_exercice": "01/01/2024",
    "date_cloture_exercice": "31/12/2024",
    "premier_exercice": "N",
    "dernier_exercice": "N",
    "activite_principale": "Commerce de gros de matériaux de construction",
    "activites_secondaires": "Transport de marchandises",
    "forme_juridique": "SARL",
    "date_creation": "15/06/2016",
    "numero_registre_commerce": "RC-EXEMPLE-0001",
    "adresse_complete": "Îlot Exemple, Lot 0, Nouakchott",
    "pays": "Mauritanie",
    "telephone": "+222 00 00 00 00",
    "email": "contact@example.com",
    "nombre_employes": "24",
    "representant_legal_nom": "Représentant Exemple",
    "representant_legal_fonction": "Gérant",
    "representant_legal_telephone": "+222 00 00 00 01",
    "representant_legal_email": "gerant@example.com",
    "responsable_comptabilite_nom": "Comptable Exemple",
    "responsable_comptabilite_fonction": "Chef comptable",
    "responsable_comptabilite_telephone": "+222 00 00 00 02",
    "responsable_comptabilite_email": "compta@example.com",
    "cabinet_comptable_nom": "Cabinet Démo Audit",
    "cabinet_comptable_adresse": "Avenue Fictive, Nouakchott",
    "cabinet_comptable_telephone": "+222 00 00 00 03",
    "cabinet_comptable_email": "audit@example.org",
}

ACTIF_ROWS = [
    ("01", "Immobilisations incorporelles", "Actif immobilisé"),
    ("03", "Terrains", "Actif immobilisé"),
    ("05", "Constructions", "Actif immobilisé"),
    ("07", "Matériel d'exploitation", "Actif immobilisé"),
    ("09", "Matériel de transport", "Actif immobilisé"),
    ("11", "Matériel de bureau et informatique", "Actif immobilisé"),
    ("13", "Autres immobilisations corporelles", "Actif immobilisé"),
    ("A", "Total actif immobilisé", "Actif immobilisé"),
    ("21", "Stocks", "Actif circulant"),
    ("27", "Clients et comptes rattachés", "Actif circulant"),
    ("31", "État, collectivités et organismes sociaux", "Actif circulant"),
    ("35", "Débiteurs divers", "Actif circulant"),
    ("41", "Banques", "Actif circulant"),
    ("43", "Caisse", "Actif circulant"),
    ("B", "Total actif circulant", "Actif circulant"),
    ("45", "Charges constatées d'avance", "Comptes de régularisation"),
    ("C", "Total comptes de régularisation", "Comptes de régularisation"),
    ("D", "TOTAL ACTIF (D=A+B+C)", "Comptes de régularisation"),
]
PASSIF_ROWS = [
    ("51", "Capital", "Capitaux propres"),
    ("53", "Réserves", "Capitaux propres"),
    ("55", "Report à nouveau", "Capitaux propres"),
    ("57", "Résultat de l'exercice", "Capitaux propres"),
    ("E", "Total capitaux propres et ressources assimilées", "Capitaux propres"),
    ("71", "Emprunts et dettes à long et moyen terme", "Emprunts et dettes"),
    ("75", "Fournisseurs et comptes rattachés", "Emprunts et dettes"),
    ("81", "État, collectivités et organismes sociaux", "Emprunts et dettes"),
    ("85", "Créditeurs divers", "Emprunts et dettes"),
    ("89", "Concours bancaires courants", "Emprunts et dettes"),
    ("F", "Total emprunts et dettes", "Emprunts et dettes"),
    ("91", "Produits constatés d'avance", "Comptes de régularisation"),
    ("G", "Total comptes de régularisation", "Comptes de régularisation"),
    ("H", "TOTAL PASSIF (H=E+F+G)", "Comptes de régularisation"),
]
CR_ROWS = [
    ("01", "Ventes de marchandises"), ("05", "Production vendue de services"), ("11", "Autres produits"),
    ("A", "Total des produits d'exploitation"),
    ("21", "Achats de marchandises et de matières premières"), ("23", "Variation de stocks de marchandises"),
    ("25", "Achats non stockés"), ("31", "Charges externes liées à l'activité"), ("35", "Frais de personnel"),
    ("37", "Impôts, taxes et versements assimilés"), ("39", "Dotations aux amortissements"),
    ("B", "Total des charges d'exploitation"), ("C", "Résultat d'exploitation"),
    ("51", "Produits financiers"), ("53", "Charges financières"), ("D", "Résultat financier"),
    ("F", "Résultat avant impôt"), ("71", "Impôt sur les bénéfices"), ("G", "Résultat net de l'exercice"),
]


def r(lo, hi):
    return random.randint(lo, hi) * 1000


def build_compte_resultat():
    cur, prev = {}, {}
    for d, scale in ((cur, 1.0), (prev, 0.86)):
        d["01"], d["05"], d["11"] = int(r(180000, 190000) * scale), int(r(22000, 26000) * scale), int(r(800, 1200) * scale)
        d["A"] = d["01"] + d["05"] + d["11"]
        d["21"], d["23"] = int(d["01"] * 0.71), -int(r(1500, 3000) * scale)
        d["25"], d["31"] = int(r(3000, 4000) * scale), int(r(9000, 11000) * scale)
        d["35"], d["37"], d["39"] = int(r(16000, 18000) * scale), int(r(1800, 2400) * scale), int(r(4000, 5000) * scale)
        d["B"] = sum(d[k] for k in ("21", "23", "25", "31", "35", "37", "39"))
        d["C"] = d["A"] - d["B"]
        d["51"], d["53"] = int(r(100, 300) * scale), int(r(2200, 2800) * scale)
        d["D"] = d["51"] - d["53"]
        d["F"] = d["C"] + d["D"]
        d["71"] = max(int(d["F"] * 0.25), 0)
        d["G"] = d["F"] - d["71"]
    rows = [{"ref": ref, "label": lbl, "current": cur[ref], "prev": prev[ref]} for ref, lbl in CR_ROWS]
    sig = [
        {"ref": "H", "label": "Chiffre d'affaires (CA)", "current": cur["01"] + cur["05"], "prev": prev["01"] + prev["05"]},
        {"ref": "J", "label": "Valeur ajoutée (VA)",
         "current": cur["A"] - sum(cur[k] for k in ("21", "23", "25", "31")),
         "prev": prev["A"] - sum(prev[k] for k in ("21", "23", "25", "31"))},
    ]
    sig.append({"ref": "K", "label": "Excédent brut d'exploitation (EBE)",
                "current": sig[1]["current"] - cur["35"] - cur["37"], "prev": sig[1]["prev"] - prev["35"] - prev["37"]})
    sig.append({"ref": "L", "label": "Capacité d'autofinancement (CAF)",
                "current": cur["G"] + cur["39"], "prev": prev["G"] + prev["39"]})
    return {"exercice": "2024", "exercice_precedent": "2023",
            "determination_resultat": rows, "soldes_intermediaires_gestion": sig}, cur["G"], prev["G"]


def build_bilan(result_cur, result_prev):
    actif, totals = [], {}
    for ref, label, section in ACTIF_ROWS:
        if ref.isdigit():
            brut = r(2000, 60000) if ref not in ("31", "45") else r(500, 3000)
            amort = int(brut * random.uniform(0.15, 0.55)) if section == "Actif immobilisé" and ref != "03" else 0
            net = brut - amort
            row = {"ref": ref, "label": label, "section": section, "brut": brut, "amort": amort,
                   "net": net, "net_prev": int(net * random.uniform(0.8, 1.1))}
        else:
            members = {"A": "Actif immobilisé", "B": "Actif circulant", "C": "Comptes de régularisation"}
            pick = [x for x in actif if x["ref"].isdigit() and (ref == "D" or x["section"] == members[ref])]
            row = {"ref": ref, "label": label, "section": section,
                   **{k: sum(x[k] for x in pick) for k in ("brut", "amort", "net", "net_prev")}}
        actif.append(row)
        totals[ref] = row
    total_net, total_prev = totals["D"]["net"], totals["D"]["net_prev"]

    v = {"51": (20_000_000, 20_000_000), "53": (2_000_000, 2_000_000), "55": (r(3000, 6000), r(2000, 4000)),
         "57": (result_cur, result_prev), "71": (r(15000, 25000), r(18000, 28000)), "81": (r(2000, 4000), r(2000, 4000)),
         "85": (r(1000, 3000), r(1000, 3000)), "89": (r(3000, 6000), r(4000, 7000)), "91": (r(300, 900), r(200, 800))}
    # Suppliers balance the sheet
    others = sum(v[k][0] for k in v)
    others_prev = sum(v[k][1] for k in v)
    v["75"] = (total_net - others, total_prev - others_prev)

    passif = []
    groups = {"E": ("51", "53", "55", "57"), "F": ("71", "75", "81", "85", "89"), "G": ("91",)}
    for ref, label, section in PASSIF_ROWS:
        if ref in groups:
            net, prev = sum(v[k][0] for k in groups[ref]), sum(v[k][1] for k in groups[ref])
        elif ref == "H":
            net, prev = total_net, total_prev
        else:
            net, prev = v[ref]
        passif.append({"ref": ref, "label": label, "section": section, "net": net, "net_prev": prev})
    p = {x["ref"]: x for x in passif}
    cap_perm = p["E"]["net"] + p["71"]["net"], p["E"]["net_prev"] + p["71"]["net_prev"]
    fr = cap_perm[0] - totals["A"]["net"], cap_perm[1] - totals["A"]["net_prev"]
    bfr = (totals["B"]["net"] - totals["41"]["net"] - totals["43"]["net"]) - (p["F"]["net"] - p["71"]["net"] - p["89"]["net"])
    bfr_prev = (totals["B"]["net_prev"] - totals["41"]["net_prev"] - totals["43"]["net_prev"]) - (p["F"]["net_prev"] - p["71"]["net_prev"] - p["89"]["net_prev"])
    sig = [{"ref": "I", "label": "Capitaux permanents", "net": cap_perm[0], "net_prev": cap_perm[1]},
           {"ref": "J", "label": "Fond de roulement", "net": fr[0], "net_prev": fr[1]},
           {"ref": "K", "label": "Besoin en fond de roulement", "net": bfr, "net_prev": bfr_prev}]
    assert p["H"]["net"] == total_net
    return {"exercice_clos": "31/12/2024", "actif": actif, "passif": passif, "soldes_intermediaires": sig}


# Page layout of the synthetic PDF ↔ what the classifier should return
PAGE_PLAN = ["NONE", "A1", "B11", "NONE", "B12", "B13", "BLANK", "C21", "D31"]


def build_liasse_json():
    cr, res_cur, res_prev = build_compte_resultat()
    bilan = build_bilan(res_cur, res_prev)
    plan = [p for p in PAGE_PLAN if p != "BLANK"]
    # classification stops right after B12 (all targets found)
    classified = plan[: plan.index("B12") + 1]
    return {
        "source_file": "synthetic_liasse.pdf",
        "total_pages": len(plan),
        "pages_classified": len(classified),
        "pages_skipped_early": len(plan) - len(classified),
        "page_classification": {str(i + 1): c for i, c in enumerate(classified)},
        "identification": IDENTIFICATION,
        "bilan": bilan,
        "compte_resultat": cr,
    }


# ── Synthetic PDF rendering (A4 at 100 DPI, PIL only) ────────────
W, H = 827, 1169


def page(banner=None, title=""):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 24), "DÉCLARATION STATISTIQUE ET FISCALE — EXEMPLE SYNTHÉTIQUE", fill=(120, 120, 120), font=font(FONT, 11))
    if banner:
        d.rectangle([40, 50, W - 40, 92], fill=GREEN)
        d.text((56, 60), banner, fill="white", font=font(FONT_B, 20))
        d.text((140, 63), title, fill="white", font=font(FONT_B, 15))
    return img, d


def fmt(n):
    return f"{n:,}".replace(",", " ") if n else "-"


def table(d, y, headers, widths, rows, bold_refs=()):
    x0 = 40
    f, fb = font(FONT, 10), font(FONT_B, 10)
    d.rectangle([x0, y, x0 + sum(widths), y + 22], fill=(200, 230, 201))
    x = x0
    for h, w in zip(headers, widths):
        d.text((x + 4, y + 5), h, fill="black", font=fb)
        x += w
    y += 22
    for row in rows:
        bold = row[0] in bold_refs
        if bold:
            d.rectangle([x0, y, x0 + sum(widths), y + 19], fill=(255, 249, 196))
        x = x0
        for i, (val, w) in enumerate(zip(row, widths)):
            txt = fmt(val) if isinstance(val, int) else str(val)
            fnt = fb if bold else f
            if isinstance(val, int):
                tw = d.textlength(txt, font=fnt)
                d.text((x + w - tw - 4, y + 4), txt, fill="black", font=fnt)
            else:
                d.text((x + 4, y + 4), txt[:52], fill="black", font=fnt)
            x += w
        d.line([x0, y + 19, x0 + sum(widths), y + 19], fill=(190, 190, 190))
        y += 19
    d.rectangle([x0, y - 19 * len(rows) - 22, x0 + sum(widths), y], outline="black")
    return y


def render_liasse_pdf(data, path):
    idf, bil, cr = data["identification"], data["bilan"], data["compte_resultat"]
    pages = []

    img, d = page()
    d.text((80, 200), idf["nom_entreprise"], fill="black", font=font(FONT_B, 18))
    d.text((80, 240), "Objet : dépôt de la liasse fiscale — exercice 2024", fill="black", font=font(FONT, 13))
    for i, line in enumerate(["Madame, Monsieur,", "", "Veuillez trouver ci-joint notre déclaration statistique et fiscale",
                              "pour l'exercice clos le 31/12/2024.", "", "Document synthétique généré pour démonstration."]):
        d.text((80, 300 + 22 * i), line, fill="black", font=font(FONT, 12))
    pages.append(img)

    img, d = page("A1", "IDENTIFICATION DE L'ENTREPRISE")
    rows = [(k.replace("_", " ").capitalize(), v) for k, v in idf.items()]
    y = 120
    for k, v in rows:
        d.text((50, y), k, fill=(60, 60, 60), font=font(FONT_B, 10))
        d.rectangle([330, y - 3, W - 50, y + 15], outline=(160, 160, 160))
        d.text((336, y), str(v), fill="black", font=font(FONT, 10))
        y += 31
    pages.append(img)

    img, d = page("B11", "BILAN — ACTIF")
    table(d, 120, ["Réf", "Libellé", "Brut", "Amort.", "Net", "Net N-1"], [40, 290, 100, 90, 100, 100],
          [(x["ref"], x["label"], x["brut"], x["amort"], x["net"], x["net_prev"]) for x in bil["actif"]],
          bold_refs=("A", "B", "C", "D"))
    pages.append(img)

    img, d = page(None)
    d.text((40, 60), "BILAN — PASSIF (suite)", fill=GREEN, font=font(FONT_B, 16))
    y = table(d, 100, ["Réf", "Libellé", "Net", "Net N-1"], [40, 420, 130, 130],
              [(x["ref"], x["label"], x["net"], x["net_prev"]) for x in bil["passif"]], bold_refs=("E", "F", "G", "H"))
    table(d, y + 30, ["Réf", "Soldes intermédiaires", "Net", "Net N-1"], [40, 420, 130, 130],
          [(x["ref"], x["label"], x["net"], x["net_prev"]) for x in bil["soldes_intermediaires"]])
    pages.append(img)

    img, d = page("B12", "RÉSULTAT COMPTABLE")
    y = table(d, 120, ["Réf", "Libellé", "Exercice", "Rappel"], [40, 420, 130, 130],
              [(x["ref"], x["label"], x["current"], x["prev"]) for x in cr["determination_resultat"]],
              bold_refs=("A", "B", "C", "D", "F", "G"))
    table(d, y + 30, ["Réf", "Soldes intermédiaires de gestion", "Exercice", "Rappel"], [40, 420, 130, 130],
          [(x["ref"], x["label"], x["current"], x["prev"]) for x in cr["soldes_intermediaires_gestion"]])
    pages.append(img)

    for code, title in (("B13", "TABLEAU DES IMMOBILISATIONS"), (None, None), ("C21", "DÉTAIL DES STOCKS"), ("D31", "EFFECTIFS ET SALAIRES")):
        if code is None:
            pages.append(Image.new("RGB", (W, H), "white"))  # blank page, removed before classification
            continue
        img, d = page(code, title)
        d.text((60, 140), "(page non ciblée — ignorée par le pipeline)", fill=(120, 120, 120), font=font(FONT, 12))
        pages.append(img)

    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=100)


# ═════════════════════════════════════════════════════════════════
#  2. Handwritten statistical forms — two fictional companies
# ═════════════════════════════════════════════════════════════════
def form_result(name, sigle, nif, activite, forme, seed):
    random.seed(seed)

    def m(lo, hi):
        return round(random.uniform(lo, hi), 3)

    achats = {"achats_marchandises_600": m(40, 90), "variation_stocks_marchandises_6031": m(-3, 3),
              "achats_matieres_premieres_601": m(5, 20), "achats_emballages_602": m(0.2, 1.5),
              "variation_stocks_matieres_prem_6031": None, "variation_stocks_emballages_6031": None,
              "achats_non_stockes_606": m(1, 4), "achats_sous_traitance_61": m(0.5, 3),
              "charges_externes_invest_62": m(0.5, 2), "charges_externes_activite_63": m(2, 6)}
    achats["total_consommations_intermediaires"] = round(sum(v for v in achats.values() if v), 3)
    ch = {"charges_pertes_diverses_64": m(0.1, 1), "frais_personnel_65": m(6, 15), "impots_taxes_66": m(0.5, 2),
          "charges_financieres_67": m(0.3, 2), "dotations_amort_prov_68": m(1, 4)}
    ch["total_charges_exploitation"] = round(sum(ch.values()) + achats["total_consommations_intermediaires"], 3)
    prod = {"ventes_marchandises_700": m(70, 130), "prod_biens_vendue_7010": m(5, 25), "production_exportee": None,
            "travaux_7012": None, "etudes_7015": None, "prestations_services_7017": m(2, 8),
            "produits_activites_annexes_706": m(0.1, 1), "production_stockee_71": None, "production_immobilisee_72": None,
            "produits_divers_74": m(0.1, 0.6), "subvention_recue_76": None}
    total_prod = round(sum(v for v in prod.values() if v), 3)
    rex = round(total_prod - ch["total_charges_exploitation"], 3)
    impot = round(max(rex, 0) * 0.25, 3)
    ch.update({"resultat_exploitation_82": rex, "resultat_cessions_immo_85": None, "impots_resultat_86": impot,
               "resultat_net_periode_87": round(rex - impot, 3), "total_charges": round(ch["total_charges_exploitation"] + impot, 3)})
    acq = {"terrain_210": None, "agenc_installations_211": m(0.2, 1), "construction_212": None,
           "installations_complexes_213": None, "materiel_exploitation_214": m(1, 5), "materiel_transport_215": m(0, 4),
           "materiel_bureau_informatique_216": m(0.1, 0.8), "autres_immob_corp_218": None, "immob_en_cours_23": None}
    acq["total_acquisitions"] = round(sum(v for v in acq.values() if v), 3)
    return {
        "company_info": {"nom_raison_sociale": name, "nif_raw": nif, "localisation": "Nouakchott",
                         "activite_principale": activite, "activite_secondaire": None, "forme_juridique": forme,
                         "sigle": sigle, "nom_enqueteur": "Enquêteur Démo", "annee": "2024"},
        "achats_et_stocks": achats,
        "charges_et_resultats": ch,
        "produits": prod,
        "autres_produits_et_infos": {"produits_financiers_77": m(0, 0.5), "reprises_78": None, "frais_immob_transferer_79": None,
                                     "total_produits": total_prod, "effectif_salarie": random.randint(8, 60),
                                     "dividendes_versees": None, "resultat_instance_affectation": None,
                                     "reserves": m(1, 5), "report_nouveau": m(-2, 4), "capital": m(5, 20)},
        "acquisitions": acq,
    }


FORMS = [
    ("BOULANGERIE EXEMPLE SARL", "BES", "0 0 0 0 0 0 0 1", "Boulangerie et pâtisserie", "SARL", 11),
    ("TRANSPORTS DÉMO SA", "TDSA", "0 0 0 0 0 0 0 2", "Transport routier de marchandises", "SA", 12),
]


def render_form_scan(data, path):
    """Draw a landscape grid form with 'handwritten' values, saved rotated like a real scan."""
    w, h = 1400, 990
    img = Image.new("RGB", (w, h), (250, 249, 244))
    d = ImageDraw.Draw(img)
    f, fb, hand = font(FONT, 11), font(FONT_B, 12), font(FONT_HAND, 17)
    d.rectangle([w // 2 - 60, 18, w // 2 + 60, 54], outline="black", width=3)
    d.text((w // 2 - 22, 25), "2024", fill="black", font=font(FONT_B, 20))
    d.text((40, 20), "DSF — Déclaration Statistique et Fiscale (exemple synthétique)", fill="black", font=fb)
    ci = data["company_info"]
    d.text((40, 70), "Raison sociale :", fill="black", font=f)
    d.text((160, 64), ci["nom_raison_sociale"], fill=(20, 40, 140), font=hand)
    d.text((40, 100), "NIF :", fill="black", font=f)
    for i, ch in enumerate(ci["nif_raw"].replace(" ", "")):
        d.rectangle([90 + 26 * i, 96, 112 + 26 * i, 120], outline="black")
        d.text((95 + 26 * i, 96), ch, fill=(20, 40, 140), font=hand)
    d.text((450, 100), "Activité :", fill="black", font=f)
    d.text((530, 94), ci["activite_principale"], fill=(20, 40, 140), font=hand)

    bands = [
        ("achats_et_stocks", ["600", "6031", "601", "602", "606", "61", "62", "63", "Total CI"],
         ["achats_marchandises_600", "variation_stocks_marchandises_6031", "achats_matieres_premieres_601",
          "achats_emballages_602", "achats_non_stockes_606", "achats_sous_traitance_61", "charges_externes_invest_62",
          "charges_externes_activite_63", "total_consommations_intermediaires"]),
        ("charges_et_resultats", ["64", "65", "66", "67", "68", "Total", "82", "86", "87"],
         ["charges_pertes_diverses_64", "frais_personnel_65", "impots_taxes_66", "charges_financieres_67",
          "dotations_amort_prov_68", "total_charges_exploitation", "resultat_exploitation_82", "impots_resultat_86",
          "resultat_net_periode_87"]),
        ("produits", ["700", "7010", "7017", "706", "74", "77", "Total", "Effectif", "Capital"],
         ["ventes_marchandises_700", "prod_biens_vendue_7010", "prestations_services_7017",
          "produits_activites_annexes_706", "produits_divers_74", "@produits_financiers_77", "@total_produits",
          "@effectif_salarie", "@capital"]),
        ("acquisitions", ["211", "214", "215", "216", "Total"],
         ["agenc_installations_211", "materiel_exploitation_214", "materiel_transport_215",
          "materiel_bureau_informatique_216", "total_acquisitions"]),
    ]
    y = 160
    for section, labels, keys in bands:
        cw = (w - 80) // len(labels)
        for i, (lbl, key) in enumerate(zip(labels, keys)):
            x = 40 + i * cw
            d.rectangle([x, y, x + cw, y + 40], outline="black", fill=(232, 240, 232))
            d.text((x + 6, y + 12), lbl, fill="black", font=fb)
            d.rectangle([x, y + 40, x + cw, y + 110], outline="black")
            src = data["autres_produits_et_infos"] if key.startswith("@") else data[section]
            val = src.get(key.lstrip("@"))
            if val is not None:
                txt = str(val) if isinstance(val, int) else (f"({abs(val):.3f})" if val < 0 else f"{val:.3f}").replace(".", ",")
                d.text((x + 10 + random.randint(-4, 6), y + 60 + random.randint(-6, 6)), txt, fill=(20, 40, 140), font=hand)
        y += 160
    img.rotate(90, expand=True).save(path, quality=88)  # scans arrive in portrait


def main():
    SAMPLES.mkdir(exist_ok=True)
    liasse = build_liasse_json()
    (SAMPLES / "synthetic_liasse.json").write_text(json.dumps(liasse, ensure_ascii=False, indent=2))
    render_liasse_pdf(liasse, SAMPLES / "synthetic_liasse.pdf")

    forms = [form_result(*spec) for spec in FORMS]
    for i, f in enumerate(forms, 1):
        f["_source_file"] = f"synthetic_form_{i}.jpg"
        render_form_scan(f, SAMPLES / f"synthetic_form_{i}.jpg")
    (SAMPLES / "synthetic_forms.json").write_text(json.dumps(forms, ensure_ascii=False, indent=2))

    from dsf_ai.form_excel import export_eretes
    from dsf_ai.liasse_excel import build_excel
    build_excel(liasse, str(SAMPLES / "synthetic_liasse.xlsx"))
    export_eretes(forms, str(SAMPLES / "synthetic_forms_eretes.xlsx"))
    print("Wrote:", *sorted(p.name for p in SAMPLES.iterdir()), sep="\n  ")


if __name__ == "__main__":
    main()
