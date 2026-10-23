"""
Construit les données JSON du site (site/data/) à partir des archives open data
téléchargées par fetch.py.

    python pipeline/build.py

Fichiers produits :
  meta.json              chiffres clés, gouvernement, présidents, dates
  groupes.json           groupes AN + Sénat (couleurs, effectifs, cohésion, proximités)
  deputes.json           tous les députés de la 17e législature (actuels et anciens)
  senateurs.json         sénateurs en exercice
  dossiers.json          index des dossiers législatifs (statut, étape, thème…)
  dossiers/<uid>.json    parcours détaillé d'un dossier (navette, CMP, CC, promulgation)
  scrutins.json          index des scrutins publics de l'Assemblée
  scrutins/<num>.json    détail nominatif d'un scrutin
  votes/<PA…>.json       votes d'un député (une lettre par scrutin)
  agenda.json            ordre du jour à venir de l'Assemblée
"""

import collections
import datetime as dt
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "site" / "data"

Z_DOSSIERS = RAW / "Dossiers_Legislatifs.json.zip"
Z_SCRUTINS = RAW / "Scrutins.json.zip"
Z_AMO = RAW / "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"
Z_AGENDA = RAW / "Agenda.json.zip"

LEGISLATURE = "17"
LEG_START = "2024-07-07"
TODAY = dt.date.today().isoformat()

# ─────────────────────────────────────────────────────────────── référentiels

# Groupes de l'Assemblée, de la gauche vers la droite de l'hémicycle.
AN_GROUPS = {
    "LFI-NFP": {"ordre": 1, "bloc": "Gauche"},
    "GDR": {"ordre": 2, "bloc": "Gauche"},
    "ECOS": {"ordre": 3, "bloc": "Gauche"},
    "SOC": {"ordre": 4, "bloc": "Gauche"},
    "LIOT": {"ordre": 5, "bloc": "Centre"},
    "EPR": {"ordre": 6, "bloc": "Centre"},
    "DEM": {"ordre": 7, "bloc": "Centre"},
    "HOR": {"ordre": 8, "bloc": "Centre"},
    "DR": {"ordre": 9, "bloc": "Droite"},
    "AD": {"ordre": 10, "bloc": "Extrême droite"},
    "UDR": {"ordre": 10, "bloc": "Extrême droite"},
    "UDDPLR": {"ordre": 10, "bloc": "Extrême droite", "sigle": "UDR"},
    "RN": {"ordre": 11, "bloc": "Extrême droite"},
    "NI": {"ordre": 12, "bloc": "Non-inscrits"},
}

# Groupes du Sénat : codes internes AN → sigle public, couleur, place.
SN_GROUPS = {
    "CRCPO": {"sigle": "CRCE-K", "couleur": "#B5121B", "ordre": 1, "bloc": "Gauche"},
    "GESTP": {"sigle": "GEST", "couleur": "#3FA34D", "ordre": 2, "bloc": "Gauche"},
    "ECOPO": {"sigle": "ECO", "couleur": "#3FA34D", "ordre": 2, "bloc": "Gauche"},
    "SOCPO": {"sigle": "SER", "couleur": "#EE7BA6", "ordre": 3, "bloc": "Gauche"},
    "RDSEP": {"sigle": "RDSE", "couleur": "#C38FD6", "ordre": 4, "bloc": "Centre"},
    "LREMP": {"sigle": "RDPI", "couleur": "#F2C200", "ordre": 5, "bloc": "Centre"},
    "UCPOL": {"sigle": "UC", "couleur": "#1FA9C9", "ordre": 6, "bloc": "Centre"},
    "RTLIP": {"sigle": "LIRT", "couleur": "#6C8BD8", "ordre": 7, "bloc": "Droite"},
    "UMPPO": {"sigle": "LR", "couleur": "#1F4FA8", "ordre": 8, "bloc": "Droite"},
    "UNTPO": {"sigle": "UNT", "couleur": "#0D2A6B", "ordre": 9, "bloc": "Extrême droite"},
    "NIPOL": {"sigle": "NI", "couleur": "#9AA0A6", "ordre": 10, "bloc": "Non-inscrits"},
}

PROCEDURES = {
    "Proposition de loi ordinaire": ("loi", "PPL", "Proposition de loi"),
    "Projet de loi ordinaire": ("loi", "PJL", "Projet de loi"),
    "Projet ou proposition de loi constitutionnelle": ("loi", "CONST", "Révision de la Constitution"),
    "Projet ou proposition de loi organique": ("loi", "ORGA", "Loi organique"),
    "Projet de ratification des traités et conventions": ("loi", "TRAITE", "Traité / convention"),
    "Projet de loi de finances de l'année": ("loi", "PLF", "Budget de l'État"),
    "Projet de loi de finances rectificative": ("loi", "PLFR", "Budget rectificatif"),
    "Projet de loi de financement de la sécurité sociale": ("loi", "PLFSS", "Budget de la Sécu"),
    "Projet de loi relative aux résultats de la gestion et portant approbation des comptes":
        ("loi", "PLRG", "Approbation des comptes"),
    "Proposition de loi présentée en application de l'article 11 de la Constitution":
        ("loi", "RIP", "Référendum d'initiative partagée"),
    "Résolution": ("resolution", "PPR", "Proposition de résolution"),
    "Résolution Article 34-1": ("resolution", "PPR341", "Résolution (art. 34-1)"),
    "Rapport d'information sans mission": ("controle", "RAPP", "Rapport d'information"),
    "Mission d'information": ("controle", "MISINF", "Mission d'information"),
    "Commission d'enquête": ("controle", "COMENQ", "Commission d'enquête"),
    "Engagement de la responsabilité gouvernementale": ("gouv", "RESP", "Responsabilité du Gouvernement"),
    "Responsabilité pénale du président de la république": ("controle", "DESTIT", "Destitution (art. 68)"),
    "Pétitions": ("controle", "PETITION", "Pétition"),
    "Allocution du Président de l'Assemblée nationale": ("controle", "ALLOC", "Allocution"),
}

# Thèmes : mots-clés (regex, début de mot) sur le titre, puis repli sur la commission saisie au fond.
THEMES = [
    ("budget", "Budget & impôts", "", r"loi de finances|budg|fiscal|imp[ôo]t|taxe|dette publique|déficit|comptes publics|tva|douan"),
    ("sante", "Santé", "", r"santé|médec|médic|hôpita|hospital|soins?\b|maladie|infirmi|pharmac|patient|fin de vie|aide à mourir|soins palliatifs|cancer|vaccin|psychiatr|ehpad"),
    ("social", "Social & retraites", "", r"sécurité sociale|retraite|pension|handicap|famill|enfan|autonomie|solidarit|pauvret|aide sociale|allocation|protection sociale|dépendance|aidants?"),
    ("travail", "Travail & emploi", "", r"travail|emploi|chômage|salari|syndic|licenci|apprenti|smic|rémunérat|fonction publique|fonctionnaire|prud"),
    ("education", "Éducation & jeunesse", "", r"éducation|école|scolaire|élèves?|université|enseignement|étudiant|lycée|collège|baccalauréat|recherche|jeunesse|mineurs?"),
    ("justice", "Justice & sécurité", "", r"justice|pénal|crimin|tribunal|juge|magistrat|prison|pénitentiaire|police|gendarm|sécurité intérieure|terroris|violences?|délinquan|détention|narcotrafic|stupéfiant|fraude|victimes?"),
    ("immigration", "Immigration", "", r"immigration|immigré|asile|droit des étrangers|étrangers en situation|titre de séjour|nationalité|naturalisation|réfugié|migrat"),
    ("environnement", "Environnement & énergie", "", r"environnement|énergi|climat|biodiversit|nucléaire|renouvelable|carbone|écolog|\beau\b|eaux|déchet|pollution|artificialisation|forêt|littoral|pesticid"),
    ("logement", "Logement & urbanisme", "", r"logement|habitat|immobili|loyer|locat|bailleur|urbanisme|construction|hlm|copropriét|foncier"),
    ("transports", "Transports", "", r"transport|ferroviaire|aérien|sncf|autoroute|mobilit|aviation|routi|véhicule"),
    ("agriculture", "Agriculture & alimentation", "", r"agricult|agricole|alimenta|élevage|éleveur|pêche|viticult|semence|agroalimentaire|rural|paysan|animal|animaux|néonicotino|acétamipride|phytosanitaire|pesticid"),
    ("numerique", "Numérique", "", r"numérique|internet|données personnelles|intelligence artificielle|cyber|plateforme|réseaux sociaux|télécom|en ligne"),
    ("outremer", "Outre-mer", "", r"outre-mer|guadeloupe|martinique|la réunion|mayotte|guyane|nouvelle-calédonie|polynésie|saint-pierre|saint-martin|saint-barthélemy|wallis|corse"),
    ("institutions", "Institutions & démocratie", "", r"constitution|référendum|élect|parlement|sénat|organique|décentralis|collectivit|communes?\b|maires?\b|démocrat|suffrage|scrutin|mandat"),
    ("economie", "Économie & entreprises", "", r"entrepris|économ|commerce|industri|consommat|concurrence|banque|financ|assurance|artisan|tourisme"),
    ("international", "International & défense", "", r"accord|convention|traité|défense|armée|militaire|international|coopération|otan|ukraine|diplomat"),
    ("culture", "Culture, sport & médias", "", r"culture|patrimoine|audiovisuel|presse|médias?\b|sport|olympi|cinéma|musée|livre|langue"),
    ("europe", "Europe", "", r"union européenne|droit de l'union|européen|parlement européen"),
]
COMMISSION_THEMES = [
    ("affaires sociales", "social"), ("finances", "budget"), ("lois", "justice"),
    ("culture", "education"), ("culturelles", "education"), ("économiques", "economie"),
    ("étrangères", "international"), ("défense", "international"),
    ("développement durable", "environnement"), ("aménagement du territoire", "environnement"),
    ("européennes", "europe"),
]
THEME_INFO = {k: {"label": l, "emoji": e} for k, l, e, _ in THEMES}
THEME_INFO["autre"] = {"label": "Autres sujets", "emoji": ""}
THEME_RE = [(k, re.compile(rx, re.I)) for k, _, _, rx in THEMES]

# ─────────────────────────────────────────────────────────────── utilitaires


def tl(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def sv(v):
    """Valeur texte d'un champ JSON issu de XML (gère xsi:nil et #text)."""
    if v is None:
        return None
    if isinstance(v, dict):
        if v.get("@xsi:nil") == "true":
            return None
        return v.get("#text")
    return str(v)


def d10(v):
    v = sv(v)
    return v[:10] if v else None


def zjson(path: Path, prefix: str = ""):
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json") and prefix in name:
                yield name, json.loads(z.read(name))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("«", '"').replace("»", '"').replace("\xa0", " ")
    s = re.sub(r"\(n°[^)]*\)|n°\s*\d+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .;,:")


STOPWORDS = set("de la le les des du d l à au aux et en un une pour par sur visant relative relatif proposition projet loi "
                "résolution organique constitutionnelle portant tendant".split())


def words(s: str) -> set:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", s) if w not in STOPWORDS and len(w) > 2}


def slugify(text: str, max_len: int = 80) -> str:
    t = re.sub(r"[’'‘]", " ", text or "")
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > max_len:
        t = t[:max_len].rsplit("-", 1)[0]
    return t or "page"


def unique_slugs(items, key_fn, id_fn, suffix_fn):
    """Attribue un slug unique à chaque élément ; en cas de doublon, ajoute un suffixe."""
    seen = {}
    for it in items:
        base = key_fn(it)
        slug = base
        if slug in seen:
            slug = f"{base}-{suffix_fn(it)}"
        n = 2
        while slug in seen:
            slug = f"{base}-{n}"
            n += 1
        seen[slug] = id_fn(it)
        it["slug"] = slug


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def overlaps(start, end, a, b):
    """[start, end] (end None = en cours) chevauche-t-il [a, b] ?"""
    return start <= (b or "9999") and (end or "9999") >= a


def classify_theme(titre: str, commission: str | None) -> str:
    """Thème le plus représenté dans le titre ; la commission saisie au fond départage."""
    scores = collections.Counter()
    for rank, (key, rx) in enumerate(THEME_RE):
        n = len(rx.findall(titre or ""))
        if n:
            scores[key] += n - rank * 0.001
    c = (commission or "").lower()
    for frag, key in COMMISSION_THEMES:
        if frag in c:
            scores[key] += 0.5
            break
    return scores.most_common(1)[0][0] if scores else "autre"


# ─────────────────────────────────────────────────────────────── acteurs


def doc_list(raw):
    """Liens vers les textes officiels, dans l'ordre de la navette (un par document).

    kind : depot (texte initial, avec exposé des motifs), navette (texte adopté en séance par une chambre et
    transmis à l'autre), cmp (texte de la commission mixte paritaire), commission (texte adopté en commission),
    rapport (rapport de la commission).
    """
    out, seen = [], set()
    for uid, date, chamber, key, xtype in raw:
        if uid in seen or "-" in uid:
            continue
        seen.add(uid)
        an = uid[4:6] == "AN"
        if key == "texteAdopte":
            kind = "commission"
        elif xtype == "DepotInitiative_Type":
            kind = "depot"
        elif xtype == "DepotInitiativeNavette_Type":
            kind = "cmp" if chamber == "CMP" else "navette"
        elif xtype == "DepotAccordInternational_Type":
            kind = "accord"
        elif uid.startswith("RAPP"):
            kind = "rapport"
        else:
            continue
        out.append({"uid": uid, "date": date, "chambre": "AN" if an else "SN", "etape": chamber, "kind": kind, "an": an,
                    "url": f"https://www.assemblee-nationale.fr/dyn/opendata/{uid}.html" if an else None,
                    "pdf": f"https://www.assemblee-nationale.fr/dyn/opendata/{uid}.pdf" if an else None})
    return out

class Referentiel:
    """Acteurs (députés, sénateurs, ministres…) et organes."""

    def __init__(self):
        self.organes = {}
        self.acteurs = {}
        for name, obj in zjson(Z_AMO):
            if "/organe/" in name:
                o = obj["organe"]
                self.organes[o["uid"]] = o
            elif "/acteur/" in name:
                a = obj["acteur"]
                self.acteurs[sv(a["uid"])] = a
        self.mandats = {}  # mandatRef → mandat
        for a in self.acteurs.values():
            for m in self.mandats_of(a):
                self.mandats[m["uid"]] = m

    @staticmethod
    def mandats_of(a):
        return tl((a.get("mandats") or {}).get("mandat"))

    def organe_ref(self, m):
        r = (m.get("organes") or {}).get("organeRef")
        return r[0] if isinstance(r, list) else r

    def organe_libelle(self, uid):
        if isinstance(uid, dict):
            uid = uid.get("uid") or uid.get("organeRef")
        o = self.organes.get(uid)
        return o.get("libelle") if o else None

    def ident(self, uid):
        a = self.acteurs.get(uid)
        if not a:
            return None
        i = a["etatCivil"]["ident"]
        return {"civ": i.get("civ"), "prenom": i.get("prenom"), "nom": i.get("nom")}

    def nom(self, uid):
        i = self.ident(uid)
        return f"{i['prenom']} {i['nom']}" if i else None


def base_person(a):
    ec = a["etatCivil"]
    i = ec["ident"]
    prof = a.get("profession") or {}
    return {
        "id": sv(a["uid"]),
        "civ": i.get("civ"),
        "prenom": i.get("prenom"),
        "nom": i.get("nom"),
        "tri": unicodedata.normalize("NFD", f"{i.get('nom')} {i.get('prenom')}").encode("ascii", "ignore").decode().lower(),
        "femme": i.get("civ") == "Mme",
        "naissance": d10((ec.get("infoNaissance") or {}).get("dateNais")),
        "lieuNaissance": sv((ec.get("infoNaissance") or {}).get("villeNais")),
        "profession": re.sub(r"^\(\d+\)\s*-\s*", "", sv(prof.get("libelleCourant")) or "") or None,
        "categorie": sv((prof.get("socProcINSEE") or {}).get("famSocPro")),
    }


def build_groupes_an(ref):
    groupes = {}
    for o in ref.organes.values():
        if o.get("codeType") == "GP" and o.get("legislature") == LEGISLATURE:
            abrev = o.get("libelleAbrev") or ""
            info = AN_GROUPS.get(abrev, {"ordre": 13, "bloc": "Autre"})
            groupes[o["uid"]] = {
                "id": o["uid"],
                "chambre": "AN",
                "sigle": info.get("sigle", abrev),
                "nom": o.get("libelle"),
                "couleur": o.get("couleurAssociee") or "#888888",
                "ordre": info["ordre"],
                "bloc": info["bloc"],
                "debut": d10((o.get("viMoDe") or {}).get("dateDebut")),
                "fin": d10((o.get("viMoDe") or {}).get("dateFin")),
            }
    return groupes


def build_groupes_sn(ref):
    groupes = {}
    for o in ref.organes.values():
        if o.get("codeType") == "GROUPESENAT":
            abrev = o.get("libelleAbrev") or ""
            info = SN_GROUPS.get(abrev, {"sigle": abrev, "couleur": "#888888", "ordre": 11, "bloc": "Autre"})
            groupes[o["uid"]] = {
                "id": o["uid"],
                "chambre": "SN",
                "sigle": info["sigle"],
                "nom": o.get("libelle"),
                "couleur": info["couleur"],
                "ordre": info["ordre"],
                "bloc": info["bloc"],
                "debut": d10((o.get("viMoDe") or {}).get("dateDebut")),
                "fin": d10((o.get("viMoDe") or {}).get("dateFin")),
            }
    return groupes


def build_deputes(ref, groupes_an):
    deputes = {}
    dept_names = {}
    for uid, a in ref.acteurs.items():
        ms = ref.mandats_of(a)
        an = [m for m in ms if m["typeOrgane"] == "ASSEMBLEE" and m.get("legislature") == LEGISLATURE]
        if not an:
            continue
        an.sort(key=lambda m: m["dateDebut"])
        last = an[-1]
        lieu = (last.get("election") or {}).get("lieu") or {}
        mandature = last.get("mandature") or {}
        p = base_person(a)
        gps = sorted(
            [m for m in ms if m["typeOrgane"] == "GP" and m.get("legislature") == LEGISLATURE],
            key=lambda m: m["dateDebut"],
        )
        cur_gp = next((m for m in reversed(gps) if not m.get("dateFin")), gps[-1] if gps else None)
        qual = ((cur_gp or {}).get("infosQualite") or {}).get("libQualite") or ""
        coms = [
            {"id": ref.organe_ref(m), "nom": ref.organe_libelle(ref.organe_ref(m)),
             "role": (m.get("infosQualite") or {}).get("libQualite")}
            for m in ms
            if m["typeOrgane"] == "COMPER" and m.get("legislature") == LEGISLATURE and not m.get("dateFin")
        ]
        parti = next(
            (ref.organe_libelle(ref.organe_ref(m)) for m in ms if m["typeOrgane"] == "PARPOL" and not m.get("dateFin")),
            None,
        )
        fonctions = []
        for m in ms:
            if m.get("dateFin") or m.get("legislature") != LEGISLATURE:
                continue
            q = ((m.get("infosQualite") or {}).get("libQualite") or "")
            if m["typeOrgane"] == "BUREAU" and "âge" not in q:
                fonctions.append(q)
            elif m["typeOrgane"] == "COMPER" and q and q != "Membre":
                fonctions.append(f"{q} de la {lower_first(ref.organe_libelle(ref.organe_ref(m)) or 'commission')}")
        num_dep = sv(lieu.get("numDepartement"))
        if num_dep and lieu.get("departement"):
            dept_names[num_dep] = lieu["departement"]
        p.update({
            "actif": any(not m.get("dateFin") for m in an),
            "debut": an[0]["dateDebut"][:10],
            "fin": d10(last.get("dateFin")),
            "causeFin": sv(mandature.get("causeFin")),
            "periodes": [[m["dateDebut"][:10], d10(m.get("dateFin"))] for m in an],
            "departement": lieu.get("departement"),
            "numDepartement": num_dep,
            "region": lieu.get("region"),
            "circo": sv(lieu.get("numCirco")),
            "place": sv(mandature.get("placeHemicycle")),
            "premiereElection": sv(mandature.get("premiereElection")) == "1",
            "groupe": ref.organe_ref(cur_gp) if cur_gp else None,
            "apparente": "apparenté" in qual.lower(),
            "presidentGroupe": any(
                not m.get("dateFin") and ((m.get("infosQualite") or {}).get("libQualite") or "").lower().startswith("président")
                for m in gps),
            "historiqueGroupes": list({
                (groupes_an.get(ref.organe_ref(m), {}).get("sigle"), m["dateDebut"][:10], d10(m.get("dateFin"))): 1
                for m in gps
            }),
            "commissions": coms,
            "fonctions": fonctions,
            "parti": parti,
        })
        deputes[uid] = p
    return deputes, dept_names


def build_senateurs(ref, groupes_sn, dept_names):
    sen = {}
    dept_names = dict(dept_names)
    dept_names.setdefault("99", "Français établis hors de France")
    for uid, a in ref.acteurs.items():
        ms = ref.mandats_of(a)
        cur = [m for m in ms if m["typeOrgane"] == "SENAT" and not m.get("dateFin")]
        if not cur:
            continue
        m0 = sorted(cur, key=lambda m: m["dateDebut"])[-1]
        first = min(m["dateDebut"] for m in ms if m["typeOrgane"] == "SENAT")
        lieu = (m0.get("election") or {}).get("lieu") or {}
        num_dep = sv(lieu.get("numDepartement"))
        gp = next((m for m in ms if m["typeOrgane"] == "GROUPESENAT" and not m.get("dateFin")), None)
        qual = ((gp or {}).get("infosQualite") or {}).get("libQualite") or ""
        p = base_person(a)
        p.update({
            "actif": True,
            "debut": m0["dateDebut"][:10],
            "premierMandat": first[:10],
            "numDepartement": num_dep,
            "departement": dept_names.get(num_dep, lieu.get("departement") or num_dep),
            "groupe": ref.organe_ref(gp) if gp else None,
            "presidentGroupe": qual.lower().startswith("président"),
            "rattache": "rattach" in qual.lower(),
            "commissions": [
                {"id": ref.organe_ref(m), "nom": ref.organe_libelle(ref.organe_ref(m)),
                 "role": (m.get("infosQualite") or {}).get("libQualite")}
                for m in ms if m["typeOrgane"] == "COMSENAT" and not m.get("dateFin")
            ],
            "parti": next(
                (ref.organe_libelle(ref.organe_ref(m)) for m in ms if m["typeOrgane"] == "PARPOL" and not m.get("dateFin")),
                None,
            ),
            "ancienDepute": any(m["typeOrgane"] == "ASSEMBLEE" for m in ms),
            "fonctions": [
                f"{(m.get('infosQualite') or {}).get('libQualite')} de la {lower_first(ref.organe_libelle(ref.organe_ref(m)) or 'commission')}"
                for m in ms if m["typeOrgane"] == "COMSENAT" and not m.get("dateFin")
                and ((m.get("infosQualite") or {}).get("libQualite") or "Membre") not in ("Membre", "Membre suppléant")
            ],
        })
        sen[uid] = p
    return sen


def build_gouvernement(ref, deputes, senateurs):
    govs = sorted(
        [o for o in ref.organes.values() if o.get("codeType") == "GOUVERNEMENT"],
        key=lambda o: o["viMoDe"]["dateDebut"],
    )
    # Premiers ministres : mandats "Premier ministre" sur un organe MINISTERE.
    pms = []
    for uid, a in ref.acteurs.items():
        for m in ref.mandats_of(a):
            if m["typeOrgane"] == "MINISTERE" and (m.get("infosQualite") or {}).get("libQualite") == "Premier ministre":
                pms.append((m["dateDebut"][:10], d10(m.get("dateFin")), uid))
    historique = []
    for o in govs:
        deb, fin = o["viMoDe"]["dateDebut"][:10], d10(o["viMoDe"].get("dateFin"))
        if fin and fin < LEG_START:
            continue
        pm = next((p for p in sorted(pms) if p[0] <= (fin or TODAY) and (p[1] or "9999") >= deb and p[0] >= _minus_days(deb, 40)), None)
        historique.append({"id": o["uid"], "debut": deb, "fin": fin,
                           "pm": ref.nom(pm[2]) if pm else None, "pmId": pm[2] if pm else None})
    current = next((g for g in reversed(govs) if not g["viMoDe"].get("dateFin")), None)
    membres = []
    if current:
        for uid, a in ref.acteurs.items():
            ms = ref.mandats_of(a)
            if not any(m["typeOrgane"] == "GOUVERNEMENT" and ref.organe_ref(m) == current["uid"] and not m.get("dateFin") for m in ms):
                continue
            for m in ms:
                q = (m.get("infosQualite") or {}).get("libQualite") or ""
                if m["typeOrgane"] == "MINISTERE" and not m.get("dateFin") and q != "en mission" and m["dateDebut"][:10] >= current["viMoDe"]["dateDebut"][:10]:
                    p = base_person(a)
                    membres.append({
                        "id": uid, "civ": p["civ"], "prenom": p["prenom"], "nom": p["nom"], "femme": p["femme"],
                        "fonction": q, "portefeuille": ref.organe_libelle(ref.organe_ref(m)),
                        "rang": int(sv(m.get("preseance")) or 999), "debut": m["dateDebut"][:10],
                        "depute": uid in deputes, "senateur": uid in senateurs,
                    })
    rank = {"Premier ministre": 0, "Ministre d'État": 1, "Ministre": 2, "Ministre délégué": 3, "Secrétaire d'État": 4}
    membres.sort(key=lambda m: (rank.get(m["fonction"], 5), m["rang"], m["nom"]))
    return {"historique": historique, "membres": membres, "debut": current["viMoDe"]["dateDebut"][:10] if current else None}


def _minus_days(d, n):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=n)).isoformat()


def build_presidences(ref):
    """Président de la République et présidents des deux assemblées."""
    out = {}
    for uid, a in ref.acteurs.items():
        for m in ref.mandats_of(a):
            if m.get("dateFin"):
                continue
            q = ((m.get("infosQualite") or {}).get("libQualite") or "").lower()
            t = m["typeOrgane"]
            org = ref.organes.get(ref.organe_ref(m), {})
            if (org.get("viMoDe") or {}).get("dateFin"):
                continue  # mandat mal clôturé sur un organe dissous
            entry = {"id": uid, "nom": ref.nom(uid), "debut": m["dateDebut"][:10]}
            if t == "PRESREP":
                key = "republique"
            elif t == "BUREAU" and q.startswith("président") and "âge" not in q:
                lib = (org.get("libelle") or "").lower()
                key = "senat" if "sénat" in lib else "assemblee"
                if key == "assemblee" and org.get("legislature") not in (None, LEGISLATURE):
                    continue
            else:
                continue
            if key not in out or out[key]["debut"] < entry["debut"]:
                out[key] = entry
    return out


# ─────────────────────────────────────────────────────────────── scrutins

POS_CHAR = {"pours": "p", "contres": "c", "abstentions": "a", "nonVotants": "n", "nonVotantsVolontaires": "n"}
POS_MAJ = {"pour": "p", "contre": "c", "abstention": "a"}


def scrutin_kind(code_type, titre):
    t = norm(titre)
    if code_type == "MOC":
        return "censure"
    if t.startswith(("l'amendement", "le sous-amendement", "les amendements")):
        return "amendement"
    if t.startswith("l'ensemble") or t.startswith("la proposition de loi") or t.startswith("le projet de loi"):
        return "ensemble"
    if t.startswith(("l'article", "les articles", "l'annexe")):
        return "article"
    if "motion de rejet" in t or "motion référendaire" in t or "motion de renvoi" in t or t.startswith("la motion"):
        return "motion"
    if "déclaration du gouvernement" in t:
        return "declaration"
    if "résolution" in t:
        return "resolution"
    if "première partie" in t or "seconde partie" in t:
        return "ensemble"
    return "autre"


TEXT_RX = re.compile(
    r"((?:proposition|projet) de (?:loi|résolution)(?: organique| constitutionnelle)?\b[^()]*)"
)


def extract_text_title(titre):
    m = TEXT_RX.search(norm(titre))
    if not m:
        return None
    t = m.group(1)
    t = re.split(r" \(| - | – |, (?:dans|en|adopt|modifi|rejet)", t)[0]
    return t.strip(" .;,:")


# ─────────────────────────────────────────────────────────────── dossiers

STEP_LABELS = {
    "ANLUNI": "Lecture unique",
    "ANNLEC": "Nouvelle lecture", "SNNLEC": "Nouvelle lecture",
    "ANLDEF": "Lecture définitive",
    "CMP": "Commission mixte paritaire",
    "CC": "Conseil constitutionnel",
    "PROM": "Promulgation",
    "AN20": "Travaux de contrôle",
    "AN21": "Engagement de la responsabilité du Gouvernement",
    "AN-APPLI": "Rapport d'application",
    "CONGRES": "Congrès du Parlement",
}


def step_chamber(code):
    if code.startswith("CMP"):
        return "CMP"
    if code.startswith("CC"):
        return "CC"
    if code.startswith("PROM"):
        return "PROM"
    if code.startswith("SN"):
        return "SN"
    if code.startswith("AN"):
        return "AN"
    return "AUTRE"


def step_label(code, fallback):
    if code in STEP_LABELS:
        return STEP_LABELS[code]
    m = re.match(r"^(AN|SN)(\d)$", code)
    if m:
        n = int(m.group(2))
        return "1ère lecture" if n == 1 else f"{n}e lecture"
    return fallback or code


def outcome(libelle):
    l = (libelle or "").lower()
    if not l:
        return None
    if "49" in l and "considéré comme adopt" in l:
        return "adopte493"
    if "considéré comme rejet" in l:
        return "rejete493"
    if "motion adoptée" in l:
        return "motion_adoptee"
    if "désaccord" in l:
        return "desaccord"
    if l == "accord":
        return "accord"
    if "non conforme" in l:
        return "cc_non"
    if "partiellement conforme" in l:
        return "cc_partiel"
    if "conforme avec réserve" in l:
        return "cc_reserve"
    if l == "conforme":
        return "cc_conforme"
    if "rejet" in l:
        return "rejete"
    if "sans modification" in l:
        return "conforme"
    if "modifi" in l:
        return "modifie"
    if "adopt" in l or "définitive" in l:
        return "adopte"
    return "autre"


ADOPTED = {"adopte", "adopte493", "conforme", "modifie"}


def walk(node, depth=0):
    for a in tl((node or {}).get("acteLegislatif")):
        if isinstance(a, dict):
            yield a, depth
            yield from walk(a.get("actesLegislatifs"), depth + 1)


class Dossiers:
    def __init__(self, ref, deputes, senateurs, groupes):
        self.ref = ref
        self.deputes = deputes
        self.senateurs = senateurs
        self.groupes = groupes
        self.raw = {}
        self.docs = {}
        for name, obj in zjson(Z_DOSSIERS):
            if "/dossierParlementaire/" in name:
                d = obj["dossierParlementaire"]
                self.raw[d["uid"]] = d
            elif "/document/" in name:
                d = obj["document"]
                self.docs[d["uid"]] = d

    # — acteurs —
    def personne(self, acteur_ref, mandat_ref=None):
        if not acteur_ref:
            return None
        m = self.ref.mandats.get(mandat_ref) if mandat_ref else None
        gouv = bool(m and m["typeOrgane"] in ("MINISTERE", "GOUVERNEMENT"))
        p = {"id": acteur_ref, "nom": self.ref.nom(acteur_ref)}
        who = self.deputes.get(acteur_ref) or self.senateurs.get(acteur_ref)
        if who and who.get("slug"):
            p["slug"] = who["slug"]
        if gouv:
            p["gouv"] = True
            p["fonction"] = self.ref.organe_libelle(self.ref.organe_ref(m))
        elif acteur_ref in self.deputes:
            p["chambre"] = "AN"
            g = self.groupes.get(self.deputes[acteur_ref]["groupe"])
            p["groupe"] = g["sigle"] if g else None
        elif acteur_ref in self.senateurs:
            p["chambre"] = "SN"
            g = self.groupes.get(self.senateurs[acteur_ref]["groupe"])
            p["groupe"] = g["sigle"] if g else None
        return p

    def doc_info(self, uid):
        d = self.docs.get(uid)
        if not d:
            return None
        cos = tl((d.get("coSignataires") or {}).get("coSignataire"))
        auteurs = []
        for au in tl((d.get("auteurs") or {}).get("auteur")):
            ac = au.get("acteur") or {}
            if ac.get("acteurRef"):
                auteurs.append(ac["acteurRef"])
        return {
            "uid": uid,
            "titre": (d.get("titres") or {}).get("titrePrincipal"),
            "type": ((d.get("classification") or {}).get("type") or {}).get("libelle"),
            "auteurs": auteurs,
            "cosignataires": [((c.get("acteur") or {}).get("acteurRef")) for c in cos if not c.get("dateRetraitCosignature")],
        }

    # — parsing d'un dossier —
    def parse(self, dp):
        ref = self.ref
        uid = dp["uid"]
        titre_d = dp.get("titreDossier") or {}
        proc_lib = (dp.get("procedureParlementaire") or {}).get("libelle") or ""
        cat, typ, typ_lib = PROCEDURES.get(proc_lib, ("autre", "AUTRE", proc_lib or "Autre"))

        # Initiateurs
        init = dp.get("initiateur") or {}
        initiateurs = [self.personne(a.get("acteurRef"), a.get("mandatRef")) for a in tl((init.get("acteurs") or {}).get("acteur"))]
        initiateurs = [p for p in initiateurs if p]
        organes_init = [ref.organe_libelle(o.get("organeRef") if isinstance(o, dict) else o)
                        for o in tl((init.get("organes") or {}).get("organe"))]
        gouv = any(p.get("gouv") for p in initiateurs)
        if typ in ("CONST", "ORGA"):
            typ_lib = ("Projet de loi " if gouv else "Proposition de loi ") + ("constitutionnelle" if typ == "CONST" else "organique")
        if cat == "loi" and typ == "PPL" and gouv:
            typ_lib = "Projet de loi"

        steps = []
        all_dates = []
        vote_refs = []
        flags = {"procAcc": False, "art493": 0, "cmp": None, "cc": None, "retire": False}
        prom = None
        cc = None
        depot_doc = None
        documents = []  # textes officiels de la navette : déposé, rapports, adoptés
        commission_fond = None
        rapporteurs = collections.OrderedDict()
        acteur_roles = []

        for top in tl((dp.get("actesLegislatifs") or {}).get("acteLegislatif")):
            code = top.get("codeActe") or ""
            chamber = step_chamber(code)
            label = step_label(code, ((top.get("libelleActe") or {}).get("nomCanonique")))
            events = []
            com_dates, seance_dates = [], []
            last_date = None
            for a, depth in walk(top.get("actesLegislatifs")):
                ev = self.event(a, uid, chamber, flags, com_dates, seance_dates, vote_refs)
                if a.get("@xsi:type") == "DepotInitiative_Type" and not depot_doc:
                    depot_doc = a.get("texteAssocie")
                for key in ("texteAssocie", "texteAdopte"):
                    if isinstance(a.get(key), str) and a[key]:
                        documents.append((a[key], d10(a.get("dateActe")), chamber, key, a.get("@xsi:type")))
                if a.get("@xsi:type") == "SaisieComFond_Type" and not commission_fond:
                    commission_fond = ref.organe_libelle(a.get("organeRef"))
                if a.get("@xsi:type") == "NominRapporteurs_Type":
                    for r in tl((a.get("rapporteurs") or {}).get("rapporteur")):
                        if r.get("acteurRef"):
                            rapporteurs[r["acteurRef"]] = True
                            acteur_roles.append((r["acteurRef"], "rapporteur"))
                if a.get("@xsi:type") == "Promulgation_Type":
                    info = a.get("infoJO") or {}
                    prom = {"date": d10(a.get("dateActe")), "numero": a.get("codeLoi"), "titre": a.get("titreLoi"),
                            "jo": d10(info.get("dateJO")), "url": info.get("urlLegifrance")}
                if a.get("@xsi:type") == "ConclusionEtapeCC_Type":
                    cc = {"date": d10(a.get("dateActe")), "resultat": (a.get("statutConclusion") or {}).get("libelle"),
                          "url": a.get("urlConclusion"),
                          "numero": f"{a.get('anneeDecision')}-{a.get('numDecision')} DC" if a.get("numDecision") else None}
                if ev:
                    ev["_k"] = ev.get("date") or last_date or "0000"
                    events.append(ev)
                if d10(a.get("dateActe")):
                    last_date = d10(a.get("dateActe"))
                    all_dates.append(last_date)
            if com_dates:
                events.append({"type": "commission", "date": min(com_dates), "fin": max(com_dates),
                               "titre": f"Examen en commission ({len(com_dates)} réunion{'s' if len(com_dates) > 1 else ''})"})
            if seance_dates:
                ds = sorted(set(seance_dates))
                events.append({"type": "seance", "date": ds[0], "fin": ds[-1], "dates": ds,
                               "titre": "Débat en séance publique" + (f" ({len(ds)} jours)" if len(ds) > 1 else "")})
            events.sort(key=lambda e: (e.get("_k") or e.get("date") or "9999", EVENT_ORDER.get(e["type"], 5)))
            seen, uniq = set(), []
            for e in events:
                e.pop("_k", None)
                sig = (e["type"], e.get("date"), e["titre"])
                if sig in seen and not e.get("votes"):
                    continue
                seen.add(sig)
                uniq.append(e)
            events = uniq
            dates = [e["date"] for e in events if e.get("date")]
            decisions = [e for e in events if e["type"] == "decision"]
            step = {
                "code": code,
                "chambre": chamber,
                "label": label,
                "debut": min(dates) if dates else None,
                "fin": max(dates) if dates else None,
                "events": events,
                "seances": sorted(set(seance_dates)),
                "resultat": decisions[-1]["outcome"] if decisions else None,
                "resultatLabel": decisions[-1]["titre"] if decisions else None,
            }
            if code == "CMP":
                dec_an = next((e for e in decisions if e.get("chambreVote") == "AN"), None)
                dec_sn = next((e for e in decisions if e.get("chambreVote") == "SN"), None)
                cmp_dec = next((e for e in events if e["type"] == "cmp_decision"), None)
                step["cmp"] = cmp_dec["outcome"] if cmp_dec else None
                step["voteAN"] = dec_an["outcome"] if dec_an else None
                step["voteSN"] = dec_sn["outcome"] if dec_sn else None
                flags["cmp"] = step["cmp"] or "convoquee"
            if steps and steps[-1]["code"] == code:
                # Même étape éclatée en plusieurs actes (ex. deux AN1) : on fusionne.
                prev = steps[-1]
                prev["events"] = sorted(prev["events"] + events, key=lambda e: (e.get("date") or "9999", EVENT_ORDER.get(e["type"], 5)))
                prev["seances"] = sorted(set(prev["seances"]) | set(step["seances"]))
                prev["debut"] = min(filter(None, [prev["debut"], step["debut"]]), default=None)
                prev["fin"] = max(filter(None, [prev["fin"], step["fin"]]), default=None)
                if step["resultat"]:
                    prev["resultat"], prev["resultatLabel"] = step["resultat"], step["resultatLabel"]
                for k in ("cmp", "voteAN", "voteSN"):
                    if step.get(k):
                        prev[k] = step[k]
            else:
                steps.append(step)

        fix_final_votes(steps)
        doc = self.doc_info(depot_doc) if depot_doc else None
        if doc:
            for a in doc["auteurs"]:
                acteur_roles.append((a, "auteur"))
        status, status_label, stage, definitive = self.status(cat, typ, steps, prom, cc, flags)
        titre = titre_d.get("titre") or (doc or {}).get("titre") or uid
        titre_long = (doc or {}).get("titre")
        theme = classify_theme(f"{titre} {titre_long or ''}", commission_fond)
        past = [x for x in all_dates if x <= TODAY]
        derniere = max(past) if past else None
        depot = next((e["date"] for s in steps for e in s["events"] if e["type"] in ("depot", "transmission") and e.get("date")), None)             or min((s["debut"] for s in steps if s["debut"]), default=None)

        auteurs = []
        if gouv:
            auteurs = [p for p in initiateurs if p.get("gouv")]
        elif doc and doc["auteurs"]:
            auteurs = [self.personne(a) for a in doc["auteurs"]]
        elif initiateurs:
            auteurs = initiateurs
        auteurs = [a for a in auteurs if a]
        examine = any(s["seances"] or s["resultat"] for s in steps)
        origine = next((s["chambre"] for s in steps if s["chambre"] in ("AN", "SN")), None)

        summary = {
            "uid": uid,
            "titre": titre[:1].upper() + titre[1:] if titre else titre,
            "cat": cat,
            "type": typ,
            "typeLabel": typ_lib,
            "theme": theme,
            "statut": status,
            "statutLabel": status_label,
            "etape": stage,
            "origine": origine,
            "depot": depot,
            "maj": derniere,
            "definitive": definitive,
            "auteur": auteurs[0] if auteurs else None,
            "nbAuteurs": len(auteurs) + (len(doc["cosignataires"]) if doc else 0),
            "gouv": gouv,
            "procAcc": flags["procAcc"],
            "art493": flags["art493"],
            "cmp": flags["cmp"],
            "cc": (cc or {}).get("resultat"),
            "loi": (prom or {}).get("numero"),
            "examine": examine,
            "parcours": [[s["code"], s["chambre"], s["resultat"]] for s in steps
                         if s["chambre"] in ("AN", "SN", "CMP", "CC", "PROM") and not s["code"].startswith(("AN20", "AN21", "AN-APPLI"))],
        }
        detail = {
            **summary,
            "titreLong": titre_long,
            "urlAN": f"https://www.assemblee-nationale.fr/dyn/{LEGISLATURE}/dossiers/{titre_d['titreChemin']}" if titre_d.get("titreChemin") else None,
            "urlSenat": (titre_d.get("senatChemin") or "").replace("http://", "https://") or None,
            "procedure": proc_lib,
            "commission": commission_fond,
            "auteurs": auteurs[:12],
            "cosignataires": len(doc["cosignataires"]) if doc and not gouv else 0,
            "cosignatairesIds": [x for x in doc["cosignataires"] if x] if doc and not gouv else [],
            "organesInitiateurs": [o for o in organes_init if o],
            "rapporteurs": [self.personne(r) for r in rapporteurs],
            "steps": steps,
            "promulgation": prom,
            "conseilConstitutionnel": cc,
            "suite": self.next_steps(cat, typ, steps, status, flags),
            "documents": doc_list(documents),
        }
        return summary, detail, vote_refs, acteur_roles, (doc or {}).get("cosignataires", [])

    def event(self, a, uid, chamber, flags, com_dates, seance_dates, vote_refs):
        ref = self.ref
        t = a.get("@xsi:type")
        code = a.get("codeActe") or ""
        date = d10(a.get("dateActe"))
        lib = (a.get("libelleActe") or {}).get("nomCanonique")
        org = org_short(ref.organe_libelle(a.get("organeRef")))
        if t == "Etape_Type":
            return None
        if t == "DiscussionCommission_Type":
            if date:
                com_dates.append(date)
            return None
        if t == "DiscussionSeancePublique_Type":
            if date:
                seance_dates.append(date)
            return None
        ev = {"type": "info", "date": date, "titre": lib, "code": code}
        if t == "DepotInitiative_Type":
            ev.update(type="depot", titre="Dépôt du texte" + (" à l'Assemblée nationale" if chamber == "AN" else " au Sénat" if chamber == "SN" else ""))
        elif t == "DepotInitiativeNavette_Type":
            prov = org_short(ref.organe_libelle(a.get("provenance")))
            dest = "à l'Assemblée nationale" if chamber == "AN" else "au Sénat" if chamber == "SN" else "à la commission mixte paritaire"
            ev.update(type="transmission", titre=f"Texte transmis {dest}" + (f" par {'le Sénat' if prov == 'Sénat' else 'l’Assemblée nationale' if prov == 'Assemblée nationale' else prov}" if prov else ""))
        elif t == "ProcedureAccelere_Type":
            flags["procAcc"] = True
            ev.update(type="procacc", titre="Le Gouvernement engage la procédure accélérée")
        elif t == "DepotAvisConseilEtat_Type":
            ev.update(type="info", titre="Avis du Conseil d'État publié")
        elif t == "EtudeImpact_Type":
            ev.update(type="info", titre="Étude d'impact publiée")
        elif t == "DepotLettreRectificative_Type":
            ev.update(type="info", titre="Lettre rectificative du Gouvernement")
        elif t == "SaisieComFond_Type":
            ev.update(type="saisine", titre=f"Renvoyé à la {lower_first(org)}" if org else lib)
        elif t == "SaisieComAvis_Type":
            ev.update(type="saisine_avis", titre=f"Avis demandé à la {lower_first(org)}" if org else lib)
        elif t == "NominRapporteurs_Type":
            rs = [self.personne(r.get("acteurRef")) for r in tl((a.get("rapporteurs") or {}).get("rapporteur"))]
            rs = [r for r in rs if r]
            if not rs:
                return None
            ev.update(type="rapporteur", titre="Rapporteur" + ("s" if len(rs) > 1 else "") + " désigné" + ("s" if len(rs) > 1 else ""), personnes=rs)
        elif t == "DepotRapport_Type":
            ev.update(type="rapport", titre="Rapport de la commission" + (" mixte paritaire" if code.startswith("CMP") else "") + " publié")
        elif t == "Decision_Type":
            res = (a.get("statutConclusion") or {}).get("libelle")
            votes = [v for v in tl((a.get("voteRefs") or {}).get("voteRef")) if v]
            vote_refs.extend((v, uid) for v in votes)
            oc = outcome(res)
            if code == "CMP-DEC":
                ev.update(type="cmp_decision", outcome=oc, titre="Accord trouvé en CMP" if oc == "accord" else "Échec de la CMP (désaccord)" if oc == "desaccord" else f"CMP : {res}")
            else:
                if oc in ("adopte493", "rejete493"):
                    flags["art493"] += 1
                cv = "SN" if org == "Sénat" else "AN" if org == "Assemblée nationale" else chamber
                ev.update(type="decision", outcome=oc, titre=decision_label(res, cv), votes=votes, chambreVote=cv, brut=res)
        elif t == "MotionProcedure_Type":
            ev.update(type="motion", titre=lib)
        elif t == "RenvoiCMP_Type":
            ev.update(type="cmp_convocation", titre="Le Premier ministre convoque une commission mixte paritaire")
        elif t == "SaisineConseilConstit_Type":
            cas = (a.get("casSaisine") or {}).get("libelle")
            ev.update(type="cc_saisine", titre="Saisine du Conseil constitutionnel" + (f" par {lower_first(cas)}" if cas else ""))
        elif t == "ConclusionEtapeCC_Type":
            res = (a.get("statutConclusion") or {}).get("libelle")
            ev.update(type="cc_decision", outcome=outcome(res), titre=f"Décision du Conseil constitutionnel : {lower_first(res)}" if res else lib,
                      url=a.get("urlConclusion"))
        elif t == "Promulgation_Type":
            info = a.get("infoJO") or {}
            ev.update(type="promulgation", titre=f"Loi n° {a.get('codeLoi')} promulguée" if a.get("codeLoi") else "Loi promulguée",
                      url=info.get("urlLegifrance"), jo=d10(info.get("dateJO")))
        elif t == "RetraitInitiative_Type":
            flags["retire"] = True
            ev.update(type="retrait", titre="Texte retiré par son auteur")
        elif t == "DeclarationGouvernement_Type":
            flags["art493"] += 1 if "49" in (lib or "") or code.endswith("DGVT") else 0
            ev.update(type="art493", titre="Le Gouvernement engage sa responsabilité (article 49.3)")
        elif t == "DepotMotionCensure_Type":
            ev.update(type="censure_depot", titre="Dépôt d'une motion de censure")
        elif t == "DecisionMotionCensure_Type":
            res = (a.get("statutConclusion") or {}).get("libelle") or ""
            votes = [v for v in tl((a.get("voteRefs") or {}).get("voteRef")) if v]
            vote_refs.extend((v, uid) for v in votes)
            ev.update(type="censure", titre=f"Motion de censure {lower_first(res)}" if res else "Vote sur la motion de censure",
                      outcome="censure_adoptee" if "adopt" in res.lower() else "censure_rejetee", votes=votes)
        elif t == "CreationOrganeTemporaire_Type":
            ev.update(type="info", titre=lib)
        elif t == "DepotAccordInternational_Type":
            ev.update(type="depot", titre="Dépôt de l'accord international")
        if not ev.get("titre"):
            return None
        return ev

    @staticmethod
    def status(cat, typ, steps, prom, cc, flags):
        """Statut, libellé, étape actuelle, date d'adoption définitive."""
        reading = [s for s in steps if s["chambre"] in ("AN", "SN") and not s["code"].startswith(("AN20", "AN21", "AN-APPLI"))]
        last = steps[-1] if steps else None
        definitive = None

        for s in steps:
            if s["code"] == "CMP":
                if s.get("voteAN") in ADOPTED and s.get("voteSN") in ADOPTED:
                    definitive = s["fin"]
            elif s["code"] == "ANLDEF" and s["resultat"] in ADOPTED:
                definitive = s["fin"]
            elif s in reading and s is not reading[0]:
                prev = reading[reading.index(s) - 1]
                if s["resultat"] == "conforme":
                    definitive = s["fin"]
                elif (s["resultat"] == "adopte" and prev["chambre"] != s["chambre"] and prev["resultat"] in ADOPTED
                      and s["code"] not in ("ANNLEC", "SNNLEC")):
                    # La 2e assemblée adopte le texte transmis sans le modifier → adoption conforme
                    definitive = s["fin"]

        if prom:
            return "promulguee", "Promulguée", f"Loi n° {prom['numero']}", definitive or prom["date"]
        if flags["retire"]:
            return "retiree", "Retirée", "Retiré par son auteur", None
        if cc and outcome(cc["resultat"]) == "cc_non":
            return "censuree", "Censurée", "Censurée par le Conseil constitutionnel", definitive

        if cat == "resolution":
            if last and last["resultat"] in ADOPTED:
                return "adoptee", "Adoptée", "Résolution adoptée", last["fin"]
            if last and last["resultat"] in ("rejete", "motion_adoptee"):
                return "rejetee", "Rejetée", "Résolution rejetée", None
            return ("navette" if any(s["seances"] for s in steps) else "deposee"), \
                   ("En discussion" if any(s["seances"] for s in steps) else "Déposée"), \
                   "En attente d'examen", None
        if cat in ("controle", "gouv", "autre"):
            return "info", "", last["label"] if last else "", None

        if definitive:
            if typ == "CONST":
                return "adoptee", "Votée par les 2 chambres", "En attente du Congrès ou d'un référendum", definitive
            if any(s["chambre"] == "CC" for s in steps):
                return "adoptee", "Adoptée", "Examinée par le Conseil constitutionnel", definitive
            return "adoptee", "Adoptée", "Adoptée définitivement, en attente de promulgation", definitive

        if not reading:
            return "deposee", "Déposée", "Déposée", None
        cur = reading[-1] if last and last["chambre"] in ("AN", "SN") else last
        where = chamber_name(cur["chambre"]) if cur["chambre"] in ("AN", "SN") else None
        res = cur.get("resultat")
        if last["code"] == "CMP":
            if last.get("cmp") == "desaccord":
                return "navette", "En navette", "Échec de la CMP : nouvelle lecture attendue", None
            if last.get("cmp") == "accord":
                return "navette", "En navette", "Accord en CMP : vote final des deux chambres attendu", None
            return "navette", "En navette", "Commission mixte paritaire convoquée", None
        rejected = ("rejete", "motion_adoptee", "rejete493")
        if res in rejected and (cur is reading[0] or cur["code"] == "ANLDEF"):
            return "rejetee", "Rejetée", f"Rejetée par {where_article(cur['chambre'])}", None
        if res in rejected and len(reading) >= 2 and reading[-2]["resultat"] in rejected and reading[-2]["chambre"] != cur["chambre"]:
            return "rejetee", "Rejetée", "Rejetée par les deux assemblées", None
        if res in ADOPTED:
            nxt = "le Sénat" if cur["chambre"] == "AN" else "l'Assemblée"
            return "navette", "En navette", f"{cur['label']} : adoptée par {where_article(cur['chambre'])}, transmise {'au Sénat' if cur['chambre'] == 'AN' else 'à l’Assemblée'}" if cur["code"] not in ("ANNLEC", "SNNLEC") else f"Nouvelle lecture adoptée par {where_article(cur['chambre'])}", None
        if res in ("rejete", "motion_adoptee", "rejete493"):
            return "navette", "En navette", f"{cur['label']} : rejetée par {where_article(cur['chambre'])}", None
        if cur["seances"]:
            return "navette", "En discussion", f"{cur['label']} : en séance {'à l’Assemblée' if cur['chambre'] == 'AN' else 'au Sénat'}", None
        has_rapport = any(e["type"] == "rapport" for e in cur["events"])
        if cur is reading[0] and not has_rapport:
            return "deposee", "Déposée", f"En attente d'examen {'à l’Assemblée' if cur['chambre'] == 'AN' else 'au Sénat'}", None
        if has_rapport:
            return "navette", "En navette", f"{cur['label']} : examinée en commission {'à l’Assemblée' if cur['chambre'] == 'AN' else 'au Sénat'}, en attente de séance", None
        return "navette", "En navette", f"{cur['label']} : en commission {'à l’Assemblée' if cur['chambre'] == 'AN' else 'au Sénat'}", None

    @staticmethod
    def next_steps(cat, typ, steps, status, flags):
        """Prochaines étapes probables (affichées en pointillés)."""
        if cat != "loi" or status in ("promulguee", "rejetee", "retiree", "censuree"):
            return []
        reading = [s for s in steps if s["chambre"] in ("AN", "SN") and not s["code"].startswith(("AN20", "AN21", "AN-APPLI"))]
        if status == "adoptee":
            if typ == "CONST":
                return [{"chambre": "CONGRES", "label": "Congrès (3/5) ou référendum"}]
            if any(s["chambre"] == "CC" for s in steps):
                return [{"chambre": "PROM", "label": "Promulgation"}]
            return [{"chambre": "CC", "label": "Conseil constitutionnel (si saisi)", "optionnel": True},
                    {"chambre": "PROM", "label": "Promulgation"}]
        if not reading:
            return []
        last = steps[-1]
        other = lambda c: "SN" if c == "AN" else "AN"  # noqa: E731
        if last["code"] == "CMP":
            if last.get("cmp") == "desaccord" or last.get("voteAN") in ("rejete", "rejete493") or last.get("voteSN") == "rejete":
                return [{"chambre": "AN", "label": "Nouvelle lecture"}, {"chambre": "SN", "label": "Nouvelle lecture"},
                        {"chambre": "AN", "label": "Lecture définitive"}]
            return [{"chambre": "AN", "label": "Vote du texte de la CMP"}, {"chambre": "SN", "label": "Vote du texte de la CMP"}]
        cur = reading[-1]
        res = cur["resultat"]
        nb_readings = len([s for s in reading if re.match(r"^(AN|SN)\d$", s["code"])])
        if cur["code"] in ("ANNLEC",):
            return [{"chambre": "SN", "label": "Nouvelle lecture"}] if res in ADOPTED else []
        if cur["code"] in ("SNNLEC",):
            return [{"chambre": "AN", "label": "Lecture définitive"}]
        if res is None:
            out = [{"chambre": cur["chambre"], "label": "Vote en séance"}]
            if cur is reading[0]:
                out.append({"chambre": other(cur["chambre"]), "label": "1ère lecture"})
            return out
        if res in ADOPTED or res in ("rejete", "motion_adoptee"):
            if cur is reading[0] and res not in ADOPTED:
                return []
            if nb_readings == 1:
                return [{"chambre": other(cur["chambre"]), "label": "1ère lecture"}]
            if flags["procAcc"] or nb_readings >= 4:
                return [{"chambre": "CMP", "label": "Commission mixte paritaire"}]
            n = (nb_readings // 2) + 1
            return [{"chambre": other(cur["chambre"]), "label": f"{n}e lecture" if nb_readings % 2 == 0 else f"{(nb_readings + 1) // 2}e lecture"},
                    {"chambre": "CMP", "label": "ou commission mixte paritaire", "optionnel": True}]
        return []


EVENT_ORDER = {"depot": 0, "transmission": 0, "procacc": 1, "info": 1, "saisine": 2, "saisine_avis": 2, "rapporteur": 3,
               "commission": 4, "rapport": 5, "seance": 6, "motion": 7, "art493": 7, "decision": 8,
               "cmp_convocation": 2, "cmp_decision": 9}


def fix_final_votes(steps):
    """Un vote suivi directement du Conseil constitutionnel ou de la promulgation était
    forcément conforme (adoption définitive), même si la source le note « modifié »."""
    for i, s in enumerate(steps[:-1]):
        if s["chambre"] not in ("AN", "SN") or s["code"] in ("ANLDEF",) or s["code"].startswith(("AN20", "AN21")):
            continue
        nxt = steps[i + 1]
        if nxt["chambre"] in ("CC", "PROM") and s["resultat"] in ("modifie", "adopte") and i > 0:
            s["resultat"] = "conforme"
            dec = [e for e in s["events"] if e["type"] == "decision"]
            if dec:
                dec[-1]["outcome"] = "conforme"
                dec[-1]["titre"] = f"Adopté par {where_article(dec[-1]['chambreVote'])} dans les mêmes termes : adoption définitive"
            s["resultatLabel"] = dec[-1]["titre"] if dec else s["resultatLabel"]


def org_short(lib):
    """« Sénat ( 5ème République ) » → « Sénat », « Assemblée nationale de la 17ème législature » → « Assemblée nationale »."""
    if not lib:
        return lib
    if lib.startswith("Sénat"):
        return "Sénat"
    if lib.startswith("Assemblée nationale"):
        return "Assemblée nationale"
    return lib


def lower_first(s):
    return s[:1].lower() + s[1:] if s else s


def chamber_name(c):
    return {"AN": "Assemblée nationale", "SN": "Sénat"}.get(c, c)


def where_article(c):
    return {"AN": "l'Assemblée", "SN": "le Sénat"}.get(c, c)


def decision_label(res, chamber):
    who = where_article(chamber)
    oc = outcome(res)
    return {
        "adopte": f"Adopté par {who}",
        "conforme": f"Adopté par {who} sans modification (vote conforme)",
        "modifie": f"Adopté par {who} avec des modifications",
        "rejete": f"Rejeté par {who}",
        "adopte493": f"Considéré comme adopté par {who} (49.3, pas de censure)",
        "rejete493": f"Considéré comme rejeté par {who}",
        "motion_adoptee": f"Motion de rejet adoptée : texte rejeté par {who}",
    }.get(oc, f"{who[0].upper()}{who[1:]} : {res}" if res else "Décision")


# ─────────────────────────────────────────────────────────────── agenda


def build_agenda(ref, dossier_titles):
    events = []
    for _, obj in zjson(Z_AGENDA):
        r = obj.get("reunion") or {}
        start = (r.get("timeStampDebut") or "")
        if start[:10] < TODAY:
            continue
        etat = ((r.get("cycleDeVie") or {}).get("etat") or "")
        if etat.lower().startswith(("annul", "supprim")):
            continue
        typ = r.get("@xsi:type")
        odj = r.get("ODJ") or {}
        points = []
        for p in tl((odj.get("pointsODJ") or {}).get("pointODJ")):
            if ((p.get("cycleDeVie") or {}).get("etat") or "").lower().startswith(("supprim", "annul")):
                continue
            refs = [x for x in tl((p.get("dossiersLegislatifsRefs") or {}).get("dossierRef")) if x]
            points.append({"objet": p.get("objet"), "dossiers": refs})
        if not points:
            items = tl((odj.get("resumeODJ") or {}).get("item"))
            points = [{"objet": re.sub(r"\s+", " ", i).strip(), "dossiers": []} for i in items if isinstance(i, str)]
        if not points:
            continue
        organe = ref.organe_libelle(r.get("organeReuniRef"))
        events.append({
            "date": start[:16],
            "type": "seance" if typ == "seance_type" else "commission",
            "organe": "Séance publique" if typ == "seance_type" else organe,
            "points": points[:8],
        })
    events.sort(key=lambda e: e["date"])
    return events


# ─────────────────────────────────────────────────────────────── main


def main():
    for z in (Z_DOSSIERS, Z_SCRUTINS, Z_AMO, Z_AGENDA):
        if not z.exists():
            sys.exit(f"Archive manquante : {z}. Lancez d'abord : python pipeline/fetch.py")

    print("• Acteurs et organes")
    ref = Referentiel()
    groupes_an = build_groupes_an(ref)
    groupes_sn = build_groupes_sn(ref)
    groupes = {**groupes_an, **groupes_sn}
    unique_slugs(sorted(groupes.values(), key=lambda g: (bool(g.get("fin")), g["chambre"], g["ordre"])),
                 lambda g: f"{'an' if g['chambre'] == 'AN' else 'senat'}-{slugify(g['sigle'])}",
                 lambda g: g["id"], lambda g: (g.get("debut") or g["id"])[:4])
    deputes, dept_names = build_deputes(ref, groupes_an)
    senateurs = build_senateurs(ref, groupes_sn, dept_names)
    # Adresses lisibles : les élus en exercice d'abord, pour qu'ils gardent le slug le plus simple
    unique_slugs(sorted(deputes.values(), key=lambda d: (not d["actif"], d["tri"])),
                 lambda d: slugify(f"{d['prenom']} {d['nom']}"), lambda d: d["id"],
                 lambda d: slugify(d.get("departement") or d["id"]))
    unique_slugs(sorted(senateurs.values(), key=lambda d: d["tri"]),
                 lambda d: slugify(f"{d['prenom']} {d['nom']}"), lambda d: d["id"],
                 lambda d: slugify(d.get("departement") or d["id"]))
    gouv = build_gouvernement(ref, deputes, senateurs)
    presidences = build_presidences(ref)
    print(f"  {sum(d['actif'] for d in deputes.values())} députés en exercice ({len(deputes)} sur la législature), "
          f"{len(senateurs)} sénateurs, {len(gouv['membres'])} membres du Gouvernement")

    print("• Dossiers législatifs")
    D = Dossiers(ref, deputes, senateurs, groupes)
    summaries, details = {}, {}
    vote_to_dossier = {}
    roles = collections.defaultdict(lambda: collections.defaultdict(list))
    cosign = collections.Counter()
    for uid, dp in D.raw.items():
        try:
            s, det, vrefs, aroles, cos = D.parse(dp)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {uid}: {e}")
            raise
        summaries[uid] = s
        details[uid] = det
        for v, du in vrefs:
            vote_to_dossier[v] = du
        for a, role in aroles:
            if uid not in roles[a][role]:
                roles[a][role].append(uid)
        for c in cos:
            cosign[c] += 1
    print(f"  {len(summaries)} dossiers, {sum(1 for s in summaries.values() if s['statut'] == 'promulguee')} lois promulguées")
    rank = {"promulguee": 0, "adoptee": 1, "navette": 2, "rejetee": 3}
    unique_slugs(sorted(summaries.values(), key=lambda d: (rank.get(d["statut"], 5), d["uid"])),
                 lambda d: slugify(d["titre"], 70), lambda d: d["uid"],
                 lambda d: re.sub(r"\D", "", d["uid"])[-5:])
    for uid, det in details.items():
        det["slug"] = summaries[uid]["slug"]

    # Index des titres de textes pour rattacher les scrutins (amendements…) à leur dossier.
    title_index = collections.defaultdict(set)
    for d in D.docs.values():
        t = (d.get("titres") or {}).get("titrePrincipal")
        if t and d.get("dossierRef") in summaries:
            title_index[norm(t)].add(d["dossierRef"])
    prefix_index = collections.defaultdict(list)
    for t in title_index:
        prefix_index[t[:40]].append(t)
    seance_dates = collections.defaultdict(set)
    for uid, det in details.items():
        for st in det["steps"]:
            if st["chambre"] in ("AN", "CMP"):
                seance_dates[uid].update(st["seances"])

    dossier_words = collections.defaultdict(set)
    for t, refs in title_index.items():
        for r in refs:
            dossier_words[r] |= words(t)
    for uid, s in summaries.items():
        dossier_words[uid] |= words(norm(s["titre"]))
    by_day = collections.defaultdict(set)
    for uid, days in seance_dates.items():
        for d in days:
            by_day[d].add(uid)

    def match_dossier(titre, date):
        t = extract_text_title(titre)
        if not t:
            return None
        # Un amendement ne peut porter que sur un texte débattu en séance ce jour-là.
        day = by_day.get(date, set())
        tw = words(t)
        if day:
            scored = sorted(((len(tw & dossier_words[c]) / (len(tw | dossier_words[c]) or 1), c) for c in day), reverse=True)
            if scored and scored[0][0] >= 0.3 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
                return scored[0][1]
        cands = set(title_index.get(t, ()))
        if not cands:
            for key in prefix_index.get(t[:40], ()):
                if t.startswith(key) or key.startswith(t):
                    cands |= title_index[key]
        if not cands:
            return None
        if len(cands) == 1:
            return next(iter(cands))
        dated = [c for c in cands if date in seance_dates[c]]
        if len(dated) == 1:
            return dated[0]
        debated = [c for c in cands if seance_dates[c]]
        return debated[0] if len(debated) == 1 else None

    print("• Scrutins")
    raw_scrutins = [obj["scrutin"] for _, obj in zjson(Z_SCRUTINS)]
    raw_scrutins.sort(key=lambda s: int(s["numero"]))
    N = len(raw_scrutins)
    dep_ids = list(deputes)
    in_office = {}
    for uid in dep_ids:
        in_office[uid] = deputes[uid]["periodes"]
    votes = {uid: bytearray(b"-" * N) for uid in dep_ids}
    group_pos = collections.defaultdict(lambda: bytearray(b"-" * N))
    loyal = collections.Counter()
    loyal_n = collections.Counter()
    rebels = collections.defaultdict(list)
    cohesion = collections.defaultdict(list)
    index_rows = []
    (OUT / "scrutins").mkdir(parents=True, exist_ok=True)
    scrutins_by_dossier = collections.defaultdict(list)
    censure_g = collections.defaultdict(list)
    linked = collections.Counter()

    for i, s in enumerate(raw_scrutins):
        num = int(s["numero"])
        date = s["dateScrutin"][:10]
        for uid in dep_ids:
            for a, b in in_office[uid]:
                if a <= date and (b is None or date <= b):
                    votes[uid][i] = ord(".")
                    break
        code_type = (s.get("typeVote") or {}).get("codeTypeVote")
        titre = s.get("titre") or ""
        kind = scrutin_kind(code_type, titre)
        synth = s.get("syntheseVote") or {}
        dec = synth.get("decompte") or {}
        objet = s.get("objet") or {}
        dl = objet.get("dossierLegislatif") or {}
        dossier = (dl.get("dossierRef") if isinstance(dl, dict) else None) or vote_to_dossier.get(s["uid"])
        if dossier:
            linked["direct"] += 1
        else:
            dossier = match_dossier(titre, date)
            if dossier:
                linked["titre"] += 1
        if dossier not in summaries:
            dossier = None
        adopte = (s.get("sort") or {}).get("code") == "adopté"
        detail_groups = []
        for g in tl((((s.get("ventilationVotes") or {}).get("organe") or {}).get("groupes") or {}).get("groupe")):
            gid = g.get("organeRef")
            vote = g.get("vote") or {}
            pos = vote.get("positionMajoritaire")
            dv = vote.get("decompteVoix") or {}
            nom = vote.get("decompteNominatif") or {}
            gp = {"g": gid, "n": int(g.get("nombreMembresGroupe") or 0), "pos": POS_MAJ.get(pos, "n"),
                  "p": [], "c": [], "a": [], "nv": [], "d": []}
            group_pos[gid][i] = ord(POS_MAJ.get(pos, "n"))
            for sect, ch in POS_CHAR.items():
                for v in tl((nom.get(sect) or {}).get("votant")):
                    if not isinstance(v, dict):
                        continue
                    aid = v.get("acteurRef")
                    key = {"p": "p", "c": "c", "a": "a", "n": "nv"}[ch]
                    gp[key].append(aid)
                    if v.get("parDelegation") == "true":
                        gp["d"].append(aid)
                    if aid in votes:
                        votes[aid][i] = ord(ch)
                        if ch in "pca" and pos in POS_MAJ:
                            loyal_n[aid] += 1
                            if POS_MAJ[pos] == ch:
                                loyal[aid] += 1
                            elif kind in ("ensemble", "censure", "motion") or code_type == "SPS":
                                rebels[aid].append(num)
            exprimes = len(gp["p"]) + len(gp["c"]) + len(gp["a"])
            if exprimes >= 3 and pos in POS_MAJ:
                maj = len(gp[{"pour": "p", "contre": "c", "abstention": "a"}[pos]])
                cohesion[gid].append(maj / exprimes)
            if kind == "censure":
                censure_g[gid].append((len(gp["p"]), gp["n"]))
            if not gp["d"]:
                del gp["d"]
            detail_groups.append(gp)
        row = [num, date, kind, code_type, 1 if adopte else 0,
               int(dec.get("pour") or 0), int(dec.get("contre") or 0), int(dec.get("abstentions") or 0),
               int(synth.get("nombreVotants") or 0), titre[:1].upper() + titre[1:], dossier,
               int(synth.get("nbrSuffragesRequis") or 0)]
        index_rows.append(row)
        if dossier:
            scrutins_by_dossier[dossier].append(i)
        demandeur = (s.get("demandeur") or {}).get("texte")
        write(OUT / "scrutins" / f"{num}.json", {
            "num": num, "uid": s["uid"], "date": date, "titre": row[9], "kind": kind, "type": code_type,
            "typeLabel": (s.get("typeVote") or {}).get("libelleTypeVote"),
            "majorite": (s.get("typeVote") or {}).get("typeMajorite"),
            "adopte": adopte, "annonce": (s.get("sort") or {}).get("libelle"),
            "demandeur": demandeur, "dossier": dossier,
            "votants": row[8], "exprimes": int(synth.get("suffragesExprimes") or 0), "requis": row[11],
            "pour": row[5], "contre": row[6], "abstention": row[7], "nonVotants": int(dec.get("nonVotants") or 0),
            "groupes": detail_groups,
            "lieu": s.get("lieuVote"),
        })
    print(f"  {N} scrutins ; rattachés à un dossier : {linked['direct']} directement, {linked['titre']} via le titre")

    # Statistiques par député
    for uid, d in deputes.items():
        v = votes[uid].decode()
        present = sum(v.count(c) for c in ".pcan")
        exprim = sum(v.count(c) for c in "pca")
        d["stats"] = {
            "scrutins": present,
            "votes": exprim,
            "participation": round(100 * exprim / present, 1) if present else None,
            "loyaute": round(100 * loyal[uid] / loyal_n[uid], 1) if loyal_n[uid] >= 20 else None,
            "pour": v.count("p"), "contre": v.count("c"), "abstention": v.count("a"),
            "dissidences": len(rebels[uid]),
        }
        d["roles"] = {k: v2 for k, v2 in roles.get(uid, {}).items()}
        d["cosignatures"] = cosign.get(uid, 0)
        write(OUT / "votes" / f"{uid}.json", {"v": v, "dissidences": rebels[uid][-60:]})
    for uid, sn in senateurs.items():
        sn["roles"] = {k: v2 for k, v2 in roles.get(uid, {}).items()}
        sn["cosignatures"] = cosign.get(uid, 0)

    # Un groupe recréé sous un nouvel identifiant (AD → UDR → UDR) garde l'historique de ses prédécesseurs.
    lineage = {"UDR": {"AD", "UDR"}}
    for gid, g in groupes_an.items():
        if g.get("fin"):
            continue
        sigles = lineage.get(g["sigle"], {g["sigle"]})
        for old_id, old in groupes_an.items():
            if old_id == gid or old["sigle"] not in sigles or old_id not in group_pos:
                continue
            cur, prev = group_pos[gid], group_pos[old_id]
            for i, ch in enumerate(prev):
                if cur[i] == ord("-") and ch != ord("-"):
                    cur[i] = ch
        censure_g[gid] = [x for old_id, old in groupes_an.items() if old["sigle"] in sigles for x in censure_g.get(old_id, [])]

    # Groupes : effectifs, président, cohésion, proximité de vote
    for gid, g in groupes.items():
        pool = deputes if g["chambre"] == "AN" else senateurs
        members = [p for p in pool.values() if p.get("groupe") == gid and p.get("actif")]
        g["effectif"] = len(members)
        g["femmes"] = sum(1 for p in members if p["femme"])
        pres = next((p for p in members if p.get("presidentGroupe")), None)
        g["president"] = {"id": pres["id"], "nom": f"{pres['prenom']} {pres['nom']}"} if pres else None
        ages = [age(p["naissance"]) for p in members if p.get("naissance")]
        g["ageMoyen"] = round(sum(ages) / len(ages), 1) if ages else None
        if g["chambre"] == "AN":
            c = cohesion.get(gid, [])
            g["cohesion"] = round(100 * sum(c) / len(c), 1) if c else None
            parts = [p["stats"]["participation"] for p in members if p["stats"]["participation"] is not None]
            g["participation"] = round(sum(parts) / len(parts), 1) if parts else None
        enrich_group(g, members, pool, groupes, summaries, index_rows, group_pos.get(gid), censure_g.get(gid))
    active_an = [gid for gid, g in groupes_an.items() if g["effectif"] > 0]
    proximite = {}
    for a in active_an:
        proximite[a] = {}
        pa = group_pos[a]
        for b in active_an:
            pb = group_pos[b]
            same = tot = 0
            for x, y in zip(pa, pb):
                if x in b"pca" and y in b"pca":
                    tot += 1
                    same += x == y
            proximite[a][b] = round(100 * same / tot, 1) if tot >= 50 else None

    # Rattacher les scrutins aux dossiers et à leurs étapes
    for uid, idxs in scrutins_by_dossier.items():
        det = details[uid]
        rows = [index_rows[i] for i in idxs]
        det["scrutins"] = [[r[0], r[1], r[2], r[4], r[5], r[6], r[7], r[9]] for r in rows]
        summaries[uid]["nbScrutins"] = len(rows)
        for st in det["steps"]:
            if st["chambre"] not in ("AN", "CMP"):
                continue
            st_votes = set()
            for e in st["events"]:
                for v in e.get("votes", []):
                    m = re.search(r"V(\d+)$", v)
                    if m:
                        st_votes.add(int(m.group(1)))
            days = set(st["seances"]) | {e["date"] for e in st["events"] if e["type"] == "decision" and e.get("chambreVote") == "AN"}
            st["scrutins"] = sorted({r[0] for r in rows if r[1] in days} | st_votes)
            key = [r for r in rows if r[0] in st["scrutins"] and r[2] in ("ensemble", "censure")]
            if key:
                st["scrutinCle"] = key[-1][0]
            # Résumé du vote décisif, pour l'affichage en ligne
        for st in det["steps"]:
            for e in st["events"]:
                if e.get("votes"):
                    e["scrutins"] = [int(m.group(1)) for v in e["votes"] if (m := re.search(r"V(\d+)$", v))]
                    e.pop("votes")

    print("• Agenda")
    agenda = build_agenda(ref, {u: s["titre"] for u, s in summaries.items()})
    next_event = {}
    for ev in agenda:
        for p in ev["points"]:
            for d in p["dossiers"]:
                next_event.setdefault(d, {"date": ev["date"], "type": ev["type"], "organe": ev["organe"], "objet": p["objet"]})
    for uid, det in details.items():
        if uid in next_event:
            det["prochain"] = next_event[uid]
            summaries[uid]["prochain"] = next_event[uid]["date"]

    # Écriture
    print("• Écriture des fichiers")
    if (OUT / "dossiers").exists():
        shutil.rmtree(OUT / "dossiers")
    for uid, det in details.items():
        write(OUT / "dossiers" / f"{uid}.json", det)
    dossiers_list = sorted(summaries.values(), key=lambda s: s["maj"] or "", reverse=True)
    write(OUT / "dossiers.json", {"themes": THEME_INFO, "dossiers": dossiers_list})
    write(OUT / "scrutins.json", {
        "cols": ["num", "date", "kind", "type", "adopte", "pour", "contre", "abstention", "votants", "titre", "dossier", "requis"],
        "rows": index_rows[::-1],
    })
    people = {**deputes, **senateurs}
    for g in groupes.values():
        for lst in (g.get("postes") or [], g.get("arrivees") or [], g.get("departs") or [], list((g.get("tops") or {}).values())):
            for x in lst:
                if x.get("id") in people:
                    x["slug"] = people[x["id"]]["slug"]
        if g.get("president") and g["president"]["id"] in people:
            g["president"]["slug"] = people[g["president"]["id"]]["slug"]
    for k, v in presidences.items():
        if v.get("id") in people:
            v["slug"] = people[v["id"]]["slug"]
    for m in gouv["membres"]:
        if m["id"] in people:
            m["slug"] = people[m["id"]]["slug"]
    write(OUT / "slugs.json", {
        "loi": {u: s["slug"] for u, s in summaries.items()},
        "dep": {i: d["slug"] for i, d in deputes.items()},
        "sen": {i: d["slug"] for i, d in senateurs.items()},
        "grp": {i: g["slug"] for i, g in groupes.items()},
    })
    write(OUT / "groupes.json", {
        "groupes": sorted(groupes.values(), key=lambda g: (g["chambre"], g["ordre"])),
        "proximite": proximite,
        "positions": {gid: group_pos[gid].decode() for gid in active_an},
    })
    write(OUT / "deputes.json", sorted(deputes.values(), key=lambda d: d["tri"]))
    write(OUT / "senateurs.json", sorted(senateurs.values(), key=lambda d: d["tri"]))
    write(OUT / "agenda.json", agenda[:400])

    lois = [s for s in summaries.values() if s["cat"] == "loi"]
    censures = [r for r in index_rows if r[2] == "censure"]
    meta = {
        "genere": dt.datetime.now().isoformat(timespec="minutes"),
        "legislature": LEGISLATURE,
        "debutLegislature": LEG_START,
        "presidences": presidences,
        "gouvernement": gouv,
        "chiffres": {
            "deputes": sum(d["actif"] for d in deputes.values()),
            "deputesLegislature": len(deputes),
            "senateurs": len(senateurs),
            "textes": len(lois),
            "ppl": sum(1 for s in lois if s["type"] == "PPL" and not s["gouv"]),
            "pjl": sum(1 for s in lois if s["gouv"]),
            "examines": sum(1 for s in lois if s["examine"]),
            "promulguees": sum(1 for s in lois if s["statut"] == "promulguee"),
            "enNavette": sum(1 for s in lois if s["statut"] == "navette"),
            "adoptees": sum(1 for s in lois if s["statut"] == "adoptee"),
            "cmp": sum(1 for s in lois if s["cmp"]),
            "cmpAccord": sum(1 for s in lois if s["cmp"] == "accord"),
            "procAcc": sum(1 for s in lois if s["procAcc"]),
            "art493": sum(s["art493"] for s in lois),
            "cc": sum(1 for s in lois if s["cc"]),
            "scrutins": N,
            "censures": len(censures),
            "censuresAdoptees": sum(1 for r in censures if r[4]),
        },
    }
    write(OUT / "meta.json", meta)
    print("  ✓ terminé →", OUT)


GROUP_PITCH = {
    ("AN", "LFI-NFP"): "Les députés de La France insoumise, membres de l'alliance de gauche du Nouveau Front populaire.",
    ("AN", "GDR"): "Les communistes et des élus ultramarins de gauche, membres du Nouveau Front populaire.",
    ("AN", "ECOS"): "Les écologistes et leurs alliés, membres du Nouveau Front populaire.",
    ("AN", "SOC"): "Le Parti socialiste et ses apparentés, membres du Nouveau Front populaire.",
    ("AN", "LIOT"): "Un groupe charnière d'indépendants : centristes, régionalistes et élus d'outre-mer.",
    ("AN", "EPR"): "Le groupe du parti Renaissance, héritier de la majorité présidentielle d'Emmanuel Macron.",
    ("AN", "DEM"): "Le groupe du MoDem, le parti centriste fondé par François Bayrou.",
    ("AN", "HOR"): "Le groupe du parti Horizons d'Édouard Philippe, au centre droit.",
    ("AN", "DR"): "Les députés Les Républicains, la droite traditionnelle.",
    ("AN", "UDR"): "Les élus de droite ralliés à Éric Ciotti en 2024, alliés du Rassemblement national.",
    ("AN", "RN"): "Le groupe du Rassemblement national, mené par Marine Le Pen.",
    ("AN", "NI"): "Les députés qui n'appartiennent à aucun groupe.",
    ("SN", "CRCE-K"): "Les sénateurs communistes et leurs alliés, dont des élus kanaks.",
    ("SN", "GEST"): "Les sénateurs écologistes.",
    ("SN", "SER"): "Les sénateurs socialistes, premier groupe de gauche du Sénat.",
    ("SN", "RDSE"): "Le plus ancien groupe du Sénat, héritier de la tradition radicale.",
    ("SN", "RDPI"): "Les sénateurs proches d'Emmanuel Macron et de Renaissance.",
    ("SN", "UC"): "Les centristes, deuxième force du Sénat, alliés de la droite.",
    ("SN", "LIRT"): "Les Indépendants, au centre droit, proches d'Horizons.",
    ("SN", "LR"): "Les Républicains, premier groupe du Sénat.",
    ("SN", "UNT"): "Le groupe du Rassemblement national et de l'UDR, créé après les sénatoriales de 2026.",
    ("SN", "NI"): "Les sénateurs qui n'appartiennent à aucun groupe.",
}


def _plus_days(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def enrich_group(g, members, pool, groupes, summaries, index_rows, pos, censures=None):
    """Carte d'identité d'un groupe : partis, postes, mouvements, palmarès, attitude de vote."""
    g["pitch"] = GROUP_PITCH.get((g["chambre"], g["sigle"]))
    if not members:
        return
    partis = collections.Counter(p.get("parti") or "Sans parti déclaré" for p in members)
    g["partis"] = partis.most_common(6)
    coms = collections.Counter(c["nom"] for p in members for c in p.get("commissions", []) if c.get("nom"))
    g["commissions"] = coms.most_common(10)
    g["regions"] = collections.Counter(p.get("region") or p.get("departement") for p in members
                                       if p.get("region") or p.get("departement")).most_common(5)
    g["postes"] = [{"id": p["id"], "nom": f"{p['prenom']} {p['nom']}", "fonction": f} for p in members for f in p.get("fonctions", [])]
    g["apparentes"] = sum(1 for p in members if p.get("apparente") or p.get("rattache"))
    g["nouveaux"] = sum(1 for p in members if p.get("premiereElection"))
    g["textes"] = sum(len((p.get("roles") or {}).get("auteur", [])) for p in members)
    lois = [u for p in members for u in (p.get("roles") or {}).get("auteur", []) if summaries.get(u, {}).get("statut") == "promulguee"]
    g["loisPromulguees"] = list(dict.fromkeys(lois))[:12]

    def pick(p, v):
        return {"id": p["id"], "nom": f"{p['prenom']} {p['nom']}", "v": v}

    tops = {}
    aged = sorted((p for p in members if p.get("naissance")), key=lambda p: p["naissance"])
    if aged:
        tops["doyen"] = pick(aged[0], age(aged[0]["naissance"]))
        tops["benjamin"] = pick(aged[-1], age(aged[-1]["naissance"]))
    if g["chambre"] == "AN":
        st = [p for p in members if (p.get("stats") or {}).get("participation") is not None]
        if st:
            best = max(st, key=lambda p: p["stats"]["participation"])
            tops["assidu"] = pick(best, best["stats"]["participation"])
        rb = [p for p in members if (p.get("stats") or {}).get("loyaute") is not None]
        if rb:
            low = min(rb, key=lambda p: p["stats"]["loyaute"])
            tops["frondeur"] = pick(low, low["stats"]["loyaute"])
    au = max(members, key=lambda p: len((p.get("roles") or {}).get("auteur", [])))
    if (au.get("roles") or {}).get("auteur"):
        tops["plume"] = pick(au, len(au["roles"]["auteur"]))
    g["tops"] = tops

    if g["chambre"] == "AN":
        arrives, departs = [], []
        start = g.get("debut") or LEG_START
        for p in pool.values():
            hist = p.get("historiqueGroupes") or []
            mine = [h for h in hist if h[0] == g["sigle"]]
            if not mine:
                continue
            if p.get("groupe") == g["id"] and p.get("actif"):
                if mine[0][1] > _plus_days(start, 30):
                    prev = next((h[0] for h in reversed(hist) if h[1] < mine[0][1] and h[0] != g["sigle"]), None)
                    arrives.append({"id": p["id"], "nom": f"{p['prenom']} {p['nom']}", "date": mine[0][1], "de": prev})
            elif mine[-1][2]:
                cur = groupes.get(p.get("groupe"), {}).get("sigle") if p.get("actif") else None
                departs.append({"id": p["id"], "nom": f"{p['prenom']} {p['nom']}", "date": mine[-1][2], "vers": cur})
        g["arrivees"] = sorted(arrives, key=lambda x: x["date"], reverse=True)[:20]
        g["departs"] = sorted(departs, key=lambda x: x["date"], reverse=True)[:20]

    if pos:
        # index_rows et pos sont dans l'ordre chronologique
        ens = [i for i, r in enumerate(index_rows) if r[2] == "ensemble"]
        cs = censures or []
        g["censures"] = {"total": len(cs), "pour": sum(1 for v, n in cs if n and v > n / 2), "partiel": sum(1 for v, n in cs if n and 0 < v <= n / 2)}
        g["ensemble"] = {k: sum(1 for i in ens if pos[i] == ord(c)) for k, c in (("pour", "p"), ("contre", "c"), ("abstention", "a"))}


def age(d):
    b = dt.date.fromisoformat(d)
    t = dt.date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


if __name__ == "__main__":
    main()
