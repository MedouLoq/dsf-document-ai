"""ERETES-format Excel export for the handwritten-form pipeline.

ERETES is the national-accounts tool used by statistics offices; analysts
feed it one row per company. Column headers below match the import
template used in production (including its original spelling), and the
aggregate columns are written as live Excel formulas.
"""
import logging

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# (header, json path | special) — "" = left blank for analysts to fill
COLUMNS = [
    ("Année", "company_info.annee"),
    ("N°", "_row_num"),
    ("source", "_static:DSF"),
    ("Nom ou Raison sociale", "company_info.nom_raison_sociale"),
    ("NIF", "company_info.nif_raw"),
    ("Produit SCN2008", ""),
    ("Branche SCN2008", ""),
    ("Sigle ou Enseigne", "company_info.sigle"),
    ("N° Attribut", ""),
    ("N° RCN", ""),
    ("Forme juridique", "company_info.forme_juridique"),
    ("Nature", ""),
    ("Secteur", ""),
    ("Activité principale", "company_info.activite_principale"),
    ("Ville", "company_info.localisation"),
    ("Activité secondaire", "company_info.activite_secondaire"),
    ("Adresse / Localisation", "company_info.localisation"),
    # Achats
    ("60 Achat et Variation des stocks", "_formula_60"),
    ("600 Achat marchandises", "achats_et_stocks.achats_marchandises_600"),
    ("6031 Variation des stocks de mdises", "achats_et_stocks.variation_stocks_marchandises_6031"),
    ("601 Achat matières premières", "achats_et_stocks.achats_matieres_premieres_601"),
    ("602 Achat demballages", "achats_et_stocks.achats_emballages_602"),
    ("6031 Variation stocks mat prem", "achats_et_stocks.variation_stocks_matieres_prem_6031"),
    ("6031 Variation stocks embalages", "achats_et_stocks.variation_stocks_emballages_6031"),
    ("606 Achat approv non stockée", "achats_et_stocks.achats_non_stockes_606"),
    ("61 Achat de sous traitance", "achats_et_stocks.achats_sous_traitance_61"),
    ("62 Charges externes liées à linvestissement", "achats_et_stocks.charges_externes_invest_62"),
    ("63 Charges externes liées à lactivité", "achats_et_stocks.charges_externes_activite_63"),
    ("Total Consommation Intermédiaire", "achats_et_stocks.total_consommations_intermediaires"),
    # Charges
    ("64 charges et perte diverse", "charges_et_resultats.charges_pertes_diverses_64"),
    ("65 frais de personnel", "charges_et_resultats.frais_personnel_65"),
    ("66 Impôt et Taxes", "charges_et_resultats.impots_taxes_66"),
    ("67 charges financieres", "charges_et_resultats.charges_financieres_67"),
    ("68 Dotation aux amor et prov", "charges_et_resultats.dotations_amort_prov_68"),
    ("Total des charges dexploitations", "charges_et_resultats.total_charges_exploitation"),
    ("82 Résultat dexploitation", "charges_et_resultats.resultat_exploitation_82"),
    ("85 Resultats Cession dimmobilisation", "charges_et_resultats.resultat_cessions_immo_85"),
    ("86 Impôt sur le résultat", "charges_et_resultats.impots_resultat_86"),
    ("87 Resultat Net de la periode", "charges_et_resultats.resultat_net_periode_87"),
    # Produits
    ("70 Vent march et prod vend", "_formula_70"),
    ("700 Vente de marchandises", "produits.ventes_marchandises_700"),
    ("7010 prod de bien vendus", "produits.prod_biens_vendue_7010"),
    ("Production exportée", "produits.production_exportee"),
    ("7012 Travaux", "produits.travaux_7012"),
    ("7015 Etudes", "produits.etudes_7015"),
    ("7017 Prestation de services", "produits.prestations_services_7017"),
    ("706 Produits des acitivités annexes", "produits.produits_activites_annexes_706"),
    ("71 Production stockée ou destockée", "produits.production_stockee_71"),
    ("72 Prod de lentreprise pour elle m", "produits.production_immobilisee_72"),
    ("74 produits et profits divers", "produits.produits_divers_74"),
    ("76 subvention reçes", "produits.subvention_recue_76"),
    ("77 Produits financiers", "autres_produits_et_infos.produits_financiers_77"),
    ("78 Reprise", "autres_produits_et_infos.reprises_78"),
    ("79 frai à immobilsations ou transférer", "autres_produits_et_infos.frais_immob_transferer_79"),
    ("Total de la Production", "autres_produits_et_infos.total_produits"),
    # Autres infos
    ("Effectif Salarié", "autres_produits_et_infos.effectif_salarie"),
    ("Dividendes versées", "autres_produits_et_infos.dividendes_versees"),
    ("Résultat en instance d'affectation", "autres_produits_et_infos.resultat_instance_affectation"),
    ("Réserves", "autres_produits_et_infos.reserves"),
    ("Report à nouveau", "autres_produits_et_infos.report_nouveau"),
    ("Capital", "autres_produits_et_infos.capital"),
    ("Valeur ajouté", "_formula_va"),
    # Acquisitions
    ("20 Acquisition des biens et valeurs Incorp", "_formula_20"),
    ("210Acquisition de terain", "acquisitions.terrain_210"),
    ("211Acquisition dagec,et installations", "acquisitions.agenc_installations_211"),
    ("212 Constructions", "acquisitions.construction_212"),
    ("213 Install Complexes", "acquisitions.installations_complexes_213"),
    ("214 Materiel dexploitation", "acquisitions.materiel_exploitation_214"),
    ("215 Materiel de transport", "acquisitions.materiel_transport_215"),
    ("216 Materiel Bureaux ei Informatique", "acquisitions.materiel_bureau_informatique_216"),
    ("218 Autres Immob Corporelles", "acquisitions.autres_immob_corp_218"),
    ("23 Immo en cours", "acquisitions.immob_en_cours_23"),
    ("Total des Aquisitions", "acquisitions.total_acquisitions"),
]

COL = {hdr: get_column_letter(i) for i, (hdr, _) in enumerate(COLUMNS, 1)}

FORMULAS = {
    # 60 = 600 + 6031 + 601 + 602 + 6031 + 6031 (contiguous columns)
    "_formula_60": lambda r: f"=SUM({COL['600 Achat marchandises']}{r}:{COL['6031 Variation stocks embalages']}{r})",
    "_formula_70": lambda r: f"={COL['700 Vente de marchandises']}{r}+{COL['7010 prod de bien vendus']}{r}",
    "_formula_va": lambda r: f"={COL['Total de la Production']}{r}-{COL['Total Consommation Intermédiaire']}{r}",
    "_formula_20": lambda r: f"=SUM({COL['210Acquisition de terain']}{r}:{COL['23 Immo en cours']}{r})",
}


def _get(data: dict, path: str):
    obj = data
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def export_eretes(results: list, output_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "DSF Extractions"

    hfont, hfill = Font(bold=True, size=8, name="Arial"), PatternFill("solid", fgColor="D9E1F2")
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
    dfont = Font(size=9, name="Arial")
    thin = Border(*(Side(style="thin") for _ in range(4)))
    num_fmt = "#,##0.000"

    for ci, (hdr, _) in enumerate(COLUMNS, 1):
        c = ws.cell(row=1, column=ci, value=hdr)
        c.font, c.fill, c.alignment, c.border = hfont, hfill, halign, thin

    for ri, result in enumerate(results, 2):
        for ci, (_, path) in enumerate(COLUMNS, 1):
            cell = ws.cell(row=ri, column=ci)
            cell.font, cell.border = dfont, thin
            if path == "_row_num":
                cell.value = ri - 1
            elif path.startswith("_static:"):
                cell.value = path.split(":", 1)[1]
            elif path in FORMULAS:
                cell.value = FORMULAS[path](ri)
                cell.number_format = num_fmt
            elif path:
                cell.value = _get(result, path)
                if isinstance(cell.value, (int, float)):
                    cell.number_format = num_fmt

    for ci, (hdr, _) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = max(10, min(len(hdr) * 0.9 + 2, 28))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(output_path)
    logger.info("ERETES export: %s (%d rows)", output_path, len(results))
    return output_path
