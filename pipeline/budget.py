"""
Budget de l'État par mission et par grand domaine, de 2012 à 2026 (crédits de paiement).

Sources : data.economie.gouv.fr (lois de finances initiales, projet 2015 et projet 2026,
annexes « budget vert » pour les LFI 2024 et 2025) et INSEE (indice des prix à la consommation).
Périmètre : budget général, hors « Remboursements et dégrèvements » et hors « Engagements
financiers de l'État » (charge de la dette), pour comparer les années à périmètre constant.

    python pipeline/budget.py          # écrit site/data/budget.json
"""

import collections
import csv
import io
import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "budget"
OUT = ROOT / "site" / "data" / "budget.json"
API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"

# année → (fichier local, URL, nature du texte, page de la source)
SOURCES = {
    2012: ("2012.csv", f"{API}/lfi-2012-dotation-bg-titre-2-et-hors-titre-2-par-mission/exports/csv?delimiter=%3B", "LFI", "lfi-2012-dotation-bg-titre-2-et-hors-titre-2-par-mission"),
    2013: ("2013.csv", f"{API}/lfi-2013-dotation-bg-titre-2-et-hors-titre-2-par-mission/exports/csv?delimiter=%3B", "LFI", "lfi-2013-dotation-bg-titre-2-et-hors-titre-2-par-mission"),
    2014: ("2014.csv", f"{API}/lfi-2014-dotation-t2-ht2-par-mission-du-bg/exports/csv?delimiter=%3B", "LFI", "lfi-2014-dotation-t2-ht2-par-mission-du-bg"),
    2015: ("2015.csv", f"{API}/projet-de-loi-de-finances-pour-2015-plf-2015/attachments/plf_2015_dotations_du_budget_general_bg_par_mission_et_titre_2_autres_titres_csv", "PLF", "projet-de-loi-de-finances-pour-2015-plf-2015"),
    2016: ("2016.csv", f"{API}/loi-de-finances-initiale-pour-2016-lfi-2016/attachments/lfi2016_t2_ht2_bg_programme_csv", "LFI", "loi-de-finances-initiale-pour-2016-lfi-2016"),
    2017: ("2017.csv", f"{API}/loi-de-finances-initiale-pour-2017-lfi-2017/attachments/lfi2017_t2_ht2_bg_programme_csv", "LFI", "loi-de-finances-initiale-pour-2017-lfi-2017"),
    2018: ("2018.csv", f"{API}/loi-de-finances-initiale-pour-2018-lfi-2018/attachments/lfi_2018_t2_ht2_etpt_bg_cas_ccf_ba_prog_min_csv", "LFI", "loi-de-finances-initiale-pour-2018-lfi-2018"),
    2019: ("2019.csv", f"{API}/loi-de-finances-initiale-pour-2019-lfi-2019-1/exports/csv?delimiter=%3B", "LFI", "loi-de-finances-initiale-pour-2019-lfi-2019-1"),
    2020: ("2020.csv", f"{API}/projet-de-loi-de-finances-initiale-pour-2020-lfi-2020/attachments/lfi2020_credits_csv", "LFI", "projet-de-loi-de-finances-initiale-pour-2020-lfi-2020"),
    2021: ("2021.csv", f"{API}/projet-de-loi-de-finances-initiale-pour-2021-lfi-2021/attachments/lfi2021_credits_ae_cp_csv", "LFI", "projet-de-loi-de-finances-initiale-pour-2021-lfi-2021"),
    2022: ("2022.csv", f"{API}/projet-de-loi-de-finances-initiale-pour-2022-lfi-2022/attachments/lfi2022_detaillee_csv", "LFI", "projet-de-loi-de-finances-initiale-pour-2022-lfi-2022"),
    2023: ("2023.csv", f"{API}/credits-ae-et-cp-votes-nomenclature-par-destination-et-nature-lfi-2023/exports/csv?delimiter=%3B", "LFI", "credits-ae-et-cp-votes-nomenclature-par-destination-et-nature-lfi-2023"),
    2024: ("plf2024.csv", f"{API}/plf-2024-depenses-2024-selon-nomenclatures-destination-et-nature/exports/csv?delimiter=%3B", "PLF", "plf-2024-depenses-2024-selon-nomenclatures-destination-et-nature"),
    2025: ("plf2025.csv", f"{API}/plf25-depenses-2025-selon-destination/exports/csv?delimiter=%3B", "PLF", "plf25-depenses-2025-selon-destination"),
}
# Les LFI 2024-2026 ne sont publiées que dans les annexes « budget vert », dont le périmètre diffère
# (cotisations de retraite des agents exclues) : on s'en tient aux projets de loi, au périmètre constant.
CPI_URL = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/001759970"
EXCLUDED = ("remboursements et degrevements", "engagements financiers de l'etat")

# Grands domaines : regroupement stable des missions, qui changent souvent de nom.
DOMAINES = [
    ("education", "Éducation", "#2d4bd8", ["enseignement scolaire"]),
    ("recherche", "Enseignement supérieur et recherche", "#5b6ee0", ["recherche et enseignement superieur"]),
    ("defense", "Défense et anciens combattants", "#3b4152", ["defense", "anciens combattants", "monde combattant"]),
    ("securite", "Sécurité et immigration", "#0e7c86", ["securite", "immigration", "circulation"]),
    ("justice", "Justice", "#6b3fc4", ["justice"]),
    ("solidarite", "Solidarités et santé", "#c2417a", ["solidarite", "sante", "regimes sociaux", "handicap", "egalite des chances"]),
    ("travail", "Travail et emploi", "#8c6d1f", ["travail", "emploi"]),
    ("territoires", "Logement, territoires et outre-mer", "#e8590c", ["territoires", "logement", "collectivites", "outre-mer", "ville"]),
    ("ecologie", "Écologie, transports et énergie", "#128a5c", ["ecologie", "energie"]),
    ("agriculture", "Agriculture", "#65a30d", ["agriculture"]),
    ("economie", "Économie et finances publiques", "#ca8a04", ["economie", "finances publiques", "fonction publique", "transformation publiques", "credits non repartis", "provisions", "gestion du patrimoine", "participations"]),
    ("culture", "Culture, médias et sport", "#d946ef", ["culture", "medias", "sport", "audiovisuel", "jeunesse"]),
    ("international", "Action extérieure et aide au développement", "#0891b2", ["action exterieure", "aide publique au developpement"]),
    ("institutions", "Institutions et administration", "#64748b", ["pouvoirs publics", "direction de l'action", "conseil et controle", "administration generale"]),
    ("crise", "Relance, crises et investissement", "#e0442f", ["relance", "crise sanitaire", "investir", "investissements d'avenir", "urgence"]),
]


# Missions renommées ou fusionnées : on les suit sous un intitulé unique.
CANON = {
    "securite": "Sécurités", "securites": "Sécurités", "securite civile": "Sécurités",
    "travail, emploi et administration des ministeres sociaux": "Travail et emploi",
    "ecologie, developpement et amenagement durables": "Écologie, développement et mobilité durables",
    "agriculture, peche, alimentation, foret et affaires rurales": "Agriculture, alimentation, forêt et affaires rurales",
    "politique des territoires": "Cohésion des territoires", "ville et logement": "Cohésion des territoires",
    "egalite des territoires, logement et ville": "Cohésion des territoires",
    "egalite des territoires et logement": "Cohésion des territoires",
    "gestion des finances publiques et des ressources humaines": "Gestion des finances publiques",
    "action et transformation publiques": "Transformation et fonction publiques",
    "investissements d'avenir": "Investir pour la France de 2030",
}


def plain(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def num(v):
    if v is None:
        return 0.0
    v = str(v).replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(v) if v not in ("", "-") else 0.0
    except ValueError:
        return 0.0


def fetch(name, url):
    dest = RAW / name
    if dest.exists() and time.time() - dest.stat().st_mtime < 30 * 86400:
        return dest
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "hemicycles.fr"})
    with urllib.request.urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())
    return dest


def read_rows(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.reader(io.StringIO(text), delimiter=";"))


def table(rows, header_idx=0):
    head = [h.strip() for h in rows[header_idx]]
    return [dict(zip(head, r)) for r in rows[header_idx + 1:] if any(c.strip() for c in r)]


def parse_year(year, path, code_names):
    """Renvoie [(mission, programme, cp)] pour le budget général."""
    rows = read_rows(path)
    out = []
    if year in (2012, 2013, 2014):
        for r in table(rows):
            out.append((r["mission"], r["programme"], num(r["total_cp"])))
    elif year in (2015, 2016, 2017):
        i = next(k for k, r in enumerate(rows) if r and r[0].strip().lower() == "mission")
        for r in rows[i + 1:]:
            if len(r) > 8 and r[0].strip() and r[2].strip().isdigit():
                out.append((r[0].strip(), r[2].strip(), num(r[8])))
    elif year == 2018:
        for r in table(rows):
            if r.get("Type de Budget", "").strip() == "Budget général":
                cp = next(v for k, v in r.items() if k.startswith("CP (T2 + HORS T2)"))
                out.append((r["Mission"], r["Code Programme"], num(cp)))
    elif year == 2019:
        for r in table(rows):
            if r["type_de_budget_hors_budgets_annexes"] == "Budget général":
                code_names[r["code_mission"]] = r["mission"]
                out.append((r["mission"], r["code_programme"], num(r["cp_lfi_2019"])))
    elif year == 2020:
        for r in table(rows):
            if r["typeBudget"] == "BG":
                out.append((code_names.get(r["mission"], r["mission"]), r["programme"], num(r["CP LFI 2020"])))
    elif year in (2021, 2022):
        for r in table(rows):
            if r["Type Mission"] == "BG":
                code_names.setdefault(r["Code Mission"], r["Mission"])
                out.append((r["Mission"], r["Programme"], num(r["CP ( T2 + HT2) LFI"])))
    elif year == 2023:
        for r in table(rows):
            if r["type_mission"] == "BG":
                # Les colonnes « LFI » de ce jeu sont vides : LFI = PLF + amendements votés
                cp = sum(num(r[c]) for c in ("cp_t2_plf_2023", "cp_hors_t2_plf_2023", "cp_t2_amendements_2023", "cp_hors_t2_amendements_2023"))
                out.append((r["mission"], str(int(num(r["programme"]))), cp))
    elif year == 2024:
        for r in table(rows):
            if r["type_mission"] == "BG":
                out.append((r["mission"], str(int(num(r["programme"]))), num(r["cp_plf"])))
    elif year == 2025:
        for r in table(rows):
            if r["typebudget"] == "BG":
                out.append((r["libelle_mission"], r["programme"], num(r["credit_de_paiement"])))
    return out


def domaine_of(mission):
    m = plain(mission)
    for key, _, _, kws in DOMAINES:
        if any(k in m for k in kws):
            return key
    return "autres"


def cpi_annual():
    path = fetch("ipc.xml", CPI_URL)
    t = path.read_text(encoding="utf-8")
    by = collections.defaultdict(list)
    for y, _, v in re.findall(r'TIME_PERIOD="(\d{4})-(\d{2})" OBS_VALUE="([\d.]+)"', t):
        by[int(y)].append(float(v))
    return {y: round(sum(v) / len(v), 3) for y, v in by.items() if len(v) == 12}


def main():
    code_names = {}
    # 2019 et 2021 d'abord : elles fournissent les libellés des codes de mission utilisés en 2020
    order = [2019, 2021] + [y for y in sorted(SOURCES) if y not in (2019, 2021)]
    per_year = {}
    for year in order:
        fname, url, _, _ = SOURCES[year]
        per_year[year] = parse_year(year, fetch(fname, url), code_names)

    missions = collections.defaultdict(lambda: collections.defaultdict(float))
    anciens = collections.defaultdict(set)
    labels = {}
    for year, rows in per_year.items():
        for mission, _, cp in rows:
            key = plain(mission)
            if any(x in key for x in EXCLUDED):
                continue
            canon = CANON.get(key)
            if canon:
                anciens[plain(canon)].add(mission)
                mission, key = canon, plain(canon)
            missions[key][year] += cp
            labels.setdefault(key, (year, mission))
            if year >= labels[key][0] and not canon:
                labels[key] = (year, mission)

    years = sorted(SOURCES)
    totals = {y: round(sum(v.get(y, 0) for v in missions.values())) for y in years}
    dom = collections.defaultdict(lambda: collections.defaultdict(float))
    mission_list = []
    for key, vals in missions.items():
        if sum(vals.values()) <= 0:
            continue
        label = labels[key][1]
        d = domaine_of(label)
        for y, v in vals.items():
            dom[d][y] += v
        mission_list.append({"key": key, "label": label, "domaine": d,
                             "anciens": sorted(a for a in anciens.get(key, ()) if plain(a) != key),
                             "values": {str(y): round(vals[y]) for y in years if vals.get(y)}})
    mission_list.sort(key=lambda m: -m["values"].get(str(years[-2]), 0))
    dom_meta = {k: (l, c) for k, l, c, _ in DOMAINES}
    dom_meta["autres"] = ("Autres", "#94a3b8")
    domaines = [{"key": k, "label": dom_meta[k][0], "couleur": dom_meta[k][1],
                 "values": {str(y): round(dom[k].get(y, 0)) for y in years}}
                for k in dom_meta if k in dom]
    domaines.sort(key=lambda d: -d["values"][str(years[-2])])

    cpi = cpi_annual()
    out = {
        "annees": years,
        "nature": {str(y): SOURCES[y][2] for y in years},
        "total": {str(y): totals[y] for y in years},
        "ipc": {str(y): cpi[y] for y in years if y in cpi},
        "ipcReference": max(y for y in years if y in cpi),
        "domaines": domaines,
        "missions": mission_list,
        "sources": [{"annee": y, "nature": SOURCES[y][2], "url": f"https://data.economie.gouv.fr/explore/dataset/{SOURCES[y][3]}/"} for y in years],
        "notes": [
            "2015, 2024 et 2025 : crédits du projet de loi de finances, le texte voté pouvant légèrement différer.",
            "2021-2023 : plan de relance et mesures d'urgence (crise sanitaire, bouclier énergétique dans la mission Écologie en 2023).",
            "2025 : création de la mission « Audiovisuel public » au budget général, auparavant financé hors budget général.",
            "Les missions renommées sont suivies sous leur intitulé le plus récent.",
        ],
        "perimetre": "Budget général de l'État, crédits de paiement votés en loi de finances initiale (projet de loi pour 2015, 2024 et 2025), "
                     "hors remboursements et dégrèvements d'impôts et hors charge de la dette.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for y in years:
        print(f"  {y} {SOURCES[y][2]} {totals[y] / 1e9:7.1f} Md€  ({len(per_year[y])} lignes)")
    print(f"  ✓ {len(mission_list)} missions, {len(domaines)} domaines → {OUT}")


if __name__ == "__main__":
    main()
