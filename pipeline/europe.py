"""
Parlement européen : les eurodéputés élus en France, leurs votes, les textes européens et le calendrier.

Sources :
  - HowTheyVote.eu (votes nominatifs en plénière), Open Database License :
    https://github.com/HowTheyVote/data — « Data source: HowTheyVote.eu (Open Database License) »
  - Open data du Parlement européen (titres en français, parcours des textes, rapporteurs,
    commissions et fonctions des eurodéputés) : https://data.europarl.europa.eu

Ne garde que la 10e législature (depuis le 16 juillet 2024) et les votes finaux (« is_main »),
pour rester lisible : un vote par texte et par étape, pas les milliers d'amendements.

Usage :
    python pipeline/europe.py            # retélécharge l'export s'il a plus de 24 h
    python pipeline/europe.py --offline  # n'interroge aucune API (cache uniquement)
"""

import argparse
import collections
import csv
import io
import json
import re
import sys
import threading
import time
import unicodedata
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "europe"
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "site" / "data" / "europe"
EXPORT_URL = "https://github.com/HowTheyVote/data/releases/latest/download/export.zip"
EP = "https://data.europarl.europa.eu/api/v2"
HTV = "https://howtheyvote.eu/api"
UA = {"User-Agent": "hemicycles.fr (site independant, contact@hemicycles.fr)"}
TERM_START = "2024-07-16"
TERM = "10"

# Groupes politiques, de la gauche vers la droite de l'hémicycle
GROUPES = {
    "GUE_NGL": ("La Gauche", "La Gauche au Parlement européen", "#a3212c"),
    "SD": ("S&D", "Socialistes et Démocrates", "#e4405a"),
    "GREEN_EFA": ("Verts/ALE", "Les Verts / Alliance libre européenne", "#3a9a4b"),
    "RENEW": ("Renew", "Renew Europe", "#e3b21c"),
    "EPP": ("PPE", "Parti populaire européen", "#3d8fd6"),
    "ECR": ("CRE", "Conservateurs et réformistes européens", "#1b5aa0"),
    "PFE": ("PfE", "Patriotes pour l'Europe", "#2b2f6b"),
    "ESN": ("ENS", "Europe des nations souveraines", "#5b4630"),
    "NI": ("NI", "Non-inscrits", "#9097a3"),
}

# Partis français : couleurs proches des groupes de l'Assemblée nationale
PARTIS = {
    "LFI": ("LFI", "La France insoumise", "#cc2443"),
    "PS": ("PS", "Parti socialiste", "#e2739a"),
    "Place publique": ("Place publique", "Place publique", "#d8577f"),
    "Les Écologistes": ("Écologistes", "Les Écologistes", "#4ba35b"),
    "Ren": ("Renaissance", "Renaissance", "#e7b416"),
    "MoDem": ("MoDem", "Mouvement démocrate", "#f08a24"),
    "Hor": ("Horizons", "Horizons", "#2fa6c9"),
    "UDI": ("UDI", "Union des démocrates et indépendants", "#6fb6e0"),
    "Les Républicains": ("LR", "Les Républicains", "#2c55a8"),
    "UDR": ("UDR", "Union des droites pour la République", "#47508f"),
    "RN": ("RN", "Rassemblement national", "#1d2a63"),
    "IDL": ("Identité-Libertés", "Identité-Libertés", "#5c4a82"),
    "R": ("Reconquête", "Reconquête", "#5b3a29"),
    "Sans parti": ("Sans parti", "Sans parti", "#9097a3"),
}

# Commission responsable → thème (mêmes clés et couleurs que les lois françaises)
THEMES = {
    "agriculture": "Agriculture et pêche", "budget": "Budget de l'Union", "culture": "Culture et éducation",
    "economie": "Économie, industrie et commerce", "environnement": "Environnement et climat",
    "international": "Affaires étrangères et défense", "justice": "Libertés, justice et migrations",
    "institutions": "Institutions et démocratie", "sante": "Santé", "social": "Droits des femmes et égalité",
    "transports": "Transports", "travail": "Emploi et affaires sociales", "logement": "Logement",
    "numerique": "Numérique et marché intérieur", "autre": "Autres sujets",
}
COMMISSIONS = {
    "AFCO": ("Affaires constitutionnelles", "institutions"), "AFET": ("Affaires étrangères", "international"),
    "AGRI": ("Agriculture et développement rural", "agriculture"), "BUDG": ("Budgets", "budget"),
    "CONT": ("Contrôle budgétaire", "budget"), "CULT": ("Culture et éducation", "culture"),
    "DEVE": ("Développement", "international"), "ECON": ("Affaires économiques et monétaires", "economie"),
    "EMPL": ("Emploi et affaires sociales", "travail"), "ENVI": ("Environnement, climat et sécurité alimentaire", "environnement"),
    "FEMM": ("Droits des femmes et égalité des genres", "social"), "IMCO": ("Marché intérieur et protection des consommateurs", "numerique"),
    "INTA": ("Commerce international", "economie"), "ITRE": ("Industrie, recherche et énergie", "economie"),
    "JURI": ("Affaires juridiques", "justice"), "LIBE": ("Libertés civiles, justice et affaires intérieures", "justice"),
    "PECH": ("Pêche", "agriculture"), "PETI": ("Pétitions", "institutions"), "REGI": ("Développement régional", "economie"),
    "SANT": ("Santé publique", "sante"), "SEDE": ("Sécurité et défense", "international"),
    "TRAN": ("Transports et tourisme", "transports"), "HOUS": ("Crise du logement", "logement"),
    "EUDS": ("Bouclier européen de la démocratie", "institutions"),
}

TYPES = {
    "COD": ("Législation", "Règlement ou directive, adopté avec le Conseil (procédure législative ordinaire)"),
    "RSP": ("Résolution", "Prise de position du Parlement sur un sujet d'actualité"),
    "INI": ("Rapport d'initiative", "Position du Parlement préparée par une commission, sans effet contraignant"),
    "INL": ("Initiative législative", "Le Parlement demande à la Commission de proposer une loi"),
    "NLE": ("Approbation", "Le Parlement approuve ou rejette un accord international ou un acte du Conseil"),
    "APP": ("Approbation", "Le Parlement approuve ou rejette un acte du Conseil"),
    "CNS": ("Consultation", "Avis du Parlement, la décision revient au Conseil"),
    "BUD": ("Budget", "Budget annuel de l'Union et ses modifications"),
    "BUI": ("Budget", "Procédure budgétaire interne"),
    "DEC": ("Décharge", "Contrôle de l'exécution du budget par les institutions"),
    "DEA": ("Acte délégué", "Objection à un acte délégué de la Commission"),
    "RPS": ("Acte d'exécution", "Contrôle d'une mesure d'exécution"),
    "RSO": ("Organisation interne", "Composition et fonctionnement du Parlement"),
    "REG": ("Règlement intérieur", "Règles de fonctionnement du Parlement"),
    "INS": ("Organisation interne", "Décision institutionnelle du Parlement"),
    "ACI": ("Accord interinstitutionnel", "Accord entre le Parlement, le Conseil et la Commission"),
    "IMM": ("Immunité", "Levée ou défense de l'immunité d'un eurodéputé"),
}

# Étapes des parcours (API du Parlement) → libellé, acteur
ETAPES = {
    "REFERRAL": ("Texte transmis au Parlement et renvoyé en commission", "commission"),
    "COMMITTEE_REFERRAL_ANNOUNCED": ("Renvoi en commission annoncé en séance", "commission"),
    "COMMITTEE_ADOPTING_REPORT": ("Rapport adopté en commission", "commission"),
    "COMMITTEE_TABLING_REPORT": ("Projet de rapport déposé en commission", "commission"),
    "COMMITTEE_APPROVE_PROVISIONAL_AGREEMENT": ("Accord provisoire approuvé en commission", "commission"),
    "PLENARY_ENDORSE_COMMITTEE_INTERINSTITUTIONAL_NEGOTIATIONS": ("Mandat de négociation confirmé en plénière", "pe"),
    "INTERINSTITUTIONAL_NEGOTIATION": ("Négociations avec le Conseil (trilogue)", "trilogue"),
    "TABLING_PLENARY": ("Texte déposé pour la séance plénière", "pe"),
    "PLENARY_DEBATE": ("Débat en séance plénière", "pe"),
    "PLENARY_ADOPT_POSITION": ("Position adoptée en séance plénière", "pe"),
    "PLENARY_VOTE": ("Vote en séance plénière", "pe"),
    "PLENARY_DECISION": ("Décision en séance plénière", "pe"),
    "PLENARY_REJECT": ("Rejeté en séance plénière", "pe"),
    "PLENARY_AMEND": ("Amendements votés en séance plénière", "pe"),
    "PLENARY_AMEND_PROPOSAL": ("Amendements votés en séance plénière", "pe"),
    "PLENARY_REFER_COMMITTEE_INTERINSTITUTIONAL_NEGOTIATIONS": ("Renvoyé en commission pour négocier avec le Conseil", "pe"),
    "PLENARY_APPROVE_COUNCIL_POSITION": ("Position du Conseil approuvée en deuxième lecture", "pe"),
    "PLENARY_AMEND_COUNCIL_POSITION": ("Position du Conseil amendée en deuxième lecture", "pe"),
    "PLENARY_ADOPT_JOINT_TEXT": ("Texte commun adopté après conciliation", "pe"),
    "SIGNATURE": ("Acte signé par le Parlement et le Conseil", "fin"),
    "COUNCIL_POSITION": ("Position du Conseil", "conseil"),
    "COUNCIL_ADOPTION": ("Adopté par le Conseil", "conseil"),
    "FINAL_ACT_SIGNED": ("Acte final signé", "fin"),
    "PUBLICATION_OFFICIAL_JOURNAL": ("Publié au Journal officiel de l'UE", "fin"),
    "FINAL_ACT_PUBLICATION_OFFICIAL_JOURNAL": ("Publié au Journal officiel de l'UE", "fin"),
}

# Préfixe du sujet OEIL → thème (du plus précis au plus général)
OEIL = [
    ("3.10", "agriculture"), ("3.15", "agriculture"), ("3.20", "transports"), ("3.30", "numerique"), ("3.40", "economie"),
    ("3.50", "economie"), ("3.60", "environnement"), ("3.70", "environnement"), ("4.10", "travail"), ("4.15", "travail"),
    ("4.20", "sante"), ("4.40", "culture"), ("4.45", "culture"), ("4.60", "numerique"), ("4.70", "economie"),
    ("1.20", "institutions"), ("1.10", "justice"), ("1.", "institutions"), ("2.", "numerique"), ("5.", "economie"),
    ("6.", "international"), ("7.", "justice"), ("8.70", "budget"), ("8.", "institutions"),
]

POS = {"FOR": "p", "AGAINST": "c", "ABSTENTION": "a", "DID_NOT_VOTE": "."}


# ─────────────────────────────────────────── Utilitaires
def slugify(text, max_len=80):
    t = re.sub(r"[’'‘]", " ", text or "")
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > max_len:
        t = t[:max_len].rsplit("-", 1)[0]
    return t or "page"


def unique(items, base_fn, suffix_fn):
    seen = set()
    for it in items:
        s = base_fn(it)
        if s in seen:
            s = f"{s}-{suffix_fn(it)}"
        n = 2
        while s in seen:
            s = f"{base_fn(it)}-{n}"
            n += 1
        seen.add(s)
        it["slug"] = s


_lock = threading.Lock()
_next = [0.0]


def _throttle(interval):
    """Espace les requêtes de tous les fils : l'API du Parlement limite le débit (erreur 429)."""
    with _lock:
        wait = _next[0] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _next[0] = max(_next[0], time.monotonic()) + interval


def safe(fn):
    """Une fiche mal formée ne doit pas interrompre tout le téléchargement."""
    def run(x):
        try:
            return fn(x)
        except Exception as err:  # noqa: BLE001
            print(f"    ! {x} : {err}")
            return x, None
    return run


def get_json(url, tries=6, timeout=90, interval=0):
    for k in range(tries):
        if interval:
            _throttle(interval)
        try:
            req = urllib.request.Request(url, headers={**UA, "Accept": "application/ld+json, application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            return json.loads(body) if body.strip() else None
        except urllib.error.HTTPError as e:
            if e.code in (404, 204):
                return None
            if e.code == 429:
                pause = int(e.headers.get("Retry-After") or 60)
                with _lock:  # tout le monde attend
                    _next[0] = max(_next[0], time.monotonic() + pause)
                continue
            time.sleep(2 + 3 * k)
        except Exception:  # noqa: BLE001
            time.sleep(2 + 3 * k)
    return None


def load_cache(name):
    p = CACHE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_cache(name, data):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")


def tail(uri):
    if isinstance(uri, list):  # l'API renvoie parfois une liste de valeurs
        uri = uri[0] if uri else None
    return str(uri or "").rsplit("/", 1)[-1]


# ─────────────────────────────────────────── Sources
def fetch_export(max_age_h):
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / "export.zip"
    if dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < max_age_h:
        print(f"  ✓ export HowTheyVote (en cache)")
        return dest
    print("  ↓ export HowTheyVote")
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(EXPORT_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=900) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    zipfile.ZipFile(tmp).testzip()
    tmp.replace(dest)
    return dest


def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", newline=""))


def fetch_procedures(refs, last_vote, offline):
    """Titre français, parcours, rapporteurs et commission responsable de chaque procédure (avec cache)."""
    cache = load_cache("europe_procedures.json")
    todo = [r for r in refs if r not in cache or (last_vote.get(r, "") > cache[r].get("vu", ""))]
    if offline:
        todo = []
    print(f"  procédures : {len(refs)} dont {len(todo)} à interroger")

    def one(ref):
        m = re.match(r"(\d{4})/(\d{4})\((\w+)\)", ref)
        if not m:
            return ref, None
        d = get_json(f"{EP}/procedures/{m[1]}-{m[2]}?format=application%2Fld%2Bjson&language=fr", interval=1.2)
        if not d or not d.get("data"):
            return ref, None
        p = d["data"][0]
        titre = (p.get("process_title") or {})
        titre = titre.get("fr") or titre.get("en") if isinstance(titre, dict) else titre
        etapes = []
        for e in p.get("consists_of") or []:
            if not isinstance(e, dict):
                continue
            t = tail(e.get("had_activity_type"))
            if t and e.get("activity_date"):
                etapes.append([e["activity_date"][:10], t])
        rapp, lead = [], None
        for x in p.get("had_participation") or []:
            if not isinstance(x, dict):
                continue
            role = tail(x.get("participation_role"))
            if role == "COMMITTEE_LEAD":
                lead = tail((x.get("had_participant_organization") or [""])[0])
            if role in ("RAPPORTEUR", "RAPPORTEUR_CO", "RAPPORTEUR_SHADOW") and x.get("had_participant_person"):
                rapp.append([tail(x["had_participant_person"][0]), role, tail(x.get("politicalGroup"))])
        return ref, {"titre": titre, "etapes": sorted(set(map(tuple, etapes))), "rapporteurs": rapp,
                     "commission": lead, "stade": tail(p.get("current_stage")), "vu": date.today().isoformat()}

    done = 0
    with ThreadPoolExecutor(8) as ex:
        for ref, val in ex.map(safe(one), todo):
            if val:
                cache[ref] = val
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(todo)}")
                save_cache("europe_procedures.json", cache)
    save_cache("europe_procedures.json", cache)
    return cache


def fetch_meps(ids, offline):
    """Genre, lieu de naissance, commissions et fonctions (API du Parlement, avec cache)."""
    cache = load_cache("europe_meps.json")
    today = date.today().isoformat()
    semaine = date.fromordinal(date.today().toordinal() - 7).isoformat()  # fonctions : rafraîchies chaque semaine
    todo = [] if offline else [i for i in ids if cache.get(i, {}).get("vu", "") < semaine or "nom" not in cache[i]]

    def one(i):
        d = get_json(f"{EP}/meps/{i}?format=application%2Fld%2Bjson", interval=1.2)
        if not d or not d.get("data"):
            return i, None
        p = d["data"][0]
        mem = []
        for m in p.get("hasMembership") or []:
            per = m.get("memberDuring") or {}
            if (per.get("endDate") or "9999") < TERM_START:
                continue
            mem.append([tail(m.get("organization")), tail(m.get("role")), tail(m.get("membershipClassification")),
                        per.get("startDate"), per.get("endDate")])
        return i, {"genre": tail(p.get("hasGender")), "lieu": p.get("placeOfBirth"), "naissance": p.get("bday"),
                   "nom": p.get("familyName"), "prenom": p.get("givenName"), "membres": mem, "vu": today}

    with ThreadPoolExecutor(8) as ex:
        for i, val in ex.map(safe(one), todo):
            if val:
                cache[i] = val
    save_cache("europe_meps.json", cache)
    return cache


def fetch_bodies(org_ids, offline):
    """Libellé français des commissions, délégations et organes (avec cache)."""
    cache = load_cache("europe_organes.json")
    todo = [] if offline else [o for o in org_ids if o not in cache]

    def one(o):
        d = get_json(f"{EP}/corporate-bodies/{o}?format=application%2Fld%2Bjson&language=fr", interval=1.2)
        if not d or not d.get("data"):
            return o, None
        b = d["data"][0]
        lab = (b.get("prefLabel") or {}).get("fr") or (b.get("altLabel") or {}).get("fr") or b.get("label")
        return o, {"nom": lab, "code": b.get("label"), "type": tail(b.get("classification"))}

    with ThreadPoolExecutor(8) as ex:
        for o, val in ex.map(safe(one), todo):
            if val:
                cache[o] = val
    save_cache("europe_organes.json", cache)
    return cache


def fetch_sessions(offline):
    cache = load_cache("europe_sessions.json")
    if offline:
        return cache.get("sessions", [])
    out, page = [], 1
    while page < 30:
        d = get_json(f"{HTV}/sessions?page={page}&page_size=100")
        if not d or not d.get("results"):
            break
        out += d["results"]
        if not d.get("has_next"):
            break
        page += 1
    if out:
        cache = {"sessions": out}
        save_cache("europe_sessions.json", cache)
    return cache.get("sessions", [])


# ─────────────────────────────────────────── Construction
def majority(c):
    """Position majoritaire parmi pour / contre / abstention (None si personne n'a voté)."""
    best = max(("p", "c", "a"), key=lambda k: c.get(k, 0))
    return best if c.get(best, 0) else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max-age", type=float, default=24)
    args = ap.parse_args(argv)

    z = zipfile.ZipFile(fetch_export(args.max_age))
    maj_htv = z.read("last_updated.txt").decode().strip()

    # Eurodéputés français de la législature
    members = {r["id"]: r for r in rows(z, "members.csv")}
    gm = collections.defaultdict(list)
    sieges = collections.Counter()
    for r in rows(z, "group_memberships.csv"):
        if r["term"] != TERM:
            continue
        if not r["end_date"]:
            sieges[r["group_code"]] += 1
        if members.get(r["member_id"], {}).get("country_code") == "FRA":
            gm[r["member_id"]].append(r)
    fr_ids = set(gm)
    nparties = {r["id"]: r for r in rows(z, "national_parties.csv") if r["country_code"] == "FRA"}
    npm = collections.defaultdict(list)
    for r in rows(z, "national_party_memberships.csv"):
        if r["member_id"] in fr_ids and r["national_party_id"] in nparties and (r["end_date"] or "9999") >= TERM_START:
            npm[r["member_id"]].append(r)

    # Votes finaux de la législature
    votes = {}
    for r in rows(z, "votes.csv"):
        if r["timestamp"] >= TERM_START and r["is_main"] == "True":
            votes[r["id"]] = r
    subj = collections.defaultdict(list)
    for r in rows(z, "oeil_subject_votes.csv"):
        if r["vote_id"] in votes:
            subj[r["vote_id"]].append(r["oeil_subject_code"])
    comm = collections.defaultdict(list)
    for r in rows(z, "responsible_committee_votes.csv"):
        if r["vote_id"] in votes:
            comm[r["vote_id"]].append(r["committee_code"])

    # Votes individuels : groupes (tous pays) et eurodéputés français
    print("  lecture des votes individuels…")
    gcount = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    fr_pos = collections.defaultdict(dict)       # vote → membre → position
    fr_party = collections.defaultdict(dict)     # vote → membre → parti au moment du vote
    fr_group = collections.defaultdict(dict)
    with z.open("member_votes.csv") as f:
        rd = csv.reader(io.TextIOWrapper(f, encoding="utf-8", newline=""))
        next(rd)
        for vid, mid, pos, cc, gcode, _, npid, _ in rd:
            if vid not in votes:
                continue
            k = POS.get(pos, ".")
            gcount[vid][gcode][k] += 1
            if cc == "FRA":
                fr_pos[vid][mid] = k
                fr_party[vid][mid] = npid
                fr_group[vid][mid] = gcode
                fr_ids.add(mid)

    # Ordre chronologique des votes, positions de groupe
    order = sorted(votes, key=lambda v: (votes[v]["timestamp"], int(v)))
    vindex = {v: i for i, v in enumerate(order)}
    gmaj = {v: {g: majority(c) for g, c in gcount[v].items()} for v in order}

    # Procédures (titres français, parcours)
    refs = sorted({votes[v]["procedure_reference"] for v in order if votes[v]["procedure_reference"]})
    last_vote = {}
    for v in order:
        ref = votes[v]["procedure_reference"]
        if ref:
            last_vote[ref] = max(last_vote.get(ref, ""), votes[v]["timestamp"][:10])
    procs = fetch_procedures(refs, last_vote, args.offline)

    # Partis : position majoritaire des élus français du parti, vote par vote
    party_maj = {}
    for v in order:
        c = collections.defaultdict(collections.Counter)
        for mid, k in fr_pos[v].items():
            c[fr_party[v].get(mid)][k] += 1
        party_maj[v] = {pid: majority(cnt) for pid, cnt in c.items() if pid}

    # Regroupe les identifiants de partis (un même parti change d'identifiant à chaque législature)
    def party_key(pid):
        p = nparties.get(pid)
        return p["short_label"] if p else None

    # ── Eurodéputés
    mep_info = fetch_meps(sorted(fr_ids), args.offline)
    meps = []
    for mid in sorted(fr_ids, key=lambda i: (members[i]["last_name"], members[i]["first_name"])):
        m = members[mid]
        groups = sorted(gm.get(mid, []), key=lambda r: r["start_date"])
        parties = sorted(npm.get(mid, []), key=lambda r: r["start_date"])
        cur_g = groups[-1] if groups else None
        cur_p = parties[-1] if parties else None
        actif = bool(cur_g and not cur_g["end_date"])
        s = collections.Counter()
        chain = []
        for v in order:
            k = fr_pos[v].get(mid)
            chain.append(k or "-")
            if k is None:
                continue
            s["total"] += 1
            if k == "." :
                continue
            s["votes"] += 1
            s[k] += 1
            g = gmaj[v].get(fr_group[v].get(mid))
            if g:
                s["g_n"] += 1
                s["g_ok"] += g == k
            pm = party_maj[v].get(fr_party[v].get(mid))
            if pm:
                s["p_n"] += 1
                s["p_ok"] += pm == k
        info = mep_info.get(mid, {})
        nom = info.get("nom") or (m["last_name"].title() if m["last_name"].isupper() else m["last_name"])
        meps.append({
            "id": mid, "prenom": info.get("prenom") or m["first_name"], "nom": nom, "naissance": m["date_of_birth"] or info.get("naissance"),
            "lieuNaissance": info.get("lieu"), "femme": info.get("genre") == "FEMALE",
            "groupe": cur_g["group_code"] if cur_g else None,
            "parti": party_key(cur_p["national_party_id"]) if cur_p else None,
            "actif": actif, "debut": groups[0]["start_date"] if groups else None,
            "fin": None if actif else (cur_g["end_date"] if cur_g else None),
            "historiqueGroupes": [[r["group_code"], r["start_date"], r["end_date"] or None] for r in groups] if len(groups) > 1 else [],
            "email": m["email"] or None, "twitter": m["twitter"] or None, "facebook": m["facebook"] or None,
            "stats": {
                "votes": s["votes"], "total": s["total"], "pour": s["p"], "contre": s["c"], "abstention": s["a"],
                "participation": round(100 * s["votes"] / s["total"], 1) if s["total"] else None,
                "loyauteGroupe": round(100 * s["g_ok"] / s["g_n"], 1) if s["g_n"] else None,
                "loyautePartie": round(100 * s["p_ok"] / s["p_n"], 1) if s["p_n"] else None,
            },
            "_chain": "".join(chain), "_membres": info.get("membres", []),
        })
    unique(meps, lambda d: slugify(f"{d['prenom']} {d['nom']}"), lambda d: d["id"])

    # Commissions et fonctions
    orgs = {o for d in meps for o, role, cls, *_ in d["_membres"]
            if cls in ("COMMITTEE_PARLIAMENTARY_STANDING", "COMMITTEE_PARLIAMENTARY_SUB", "COMMITTEE_PARLIAMENTARY_SPECIAL",
                       "COMMITTEE_PARLIAMENTARY_TEMPORARY", "GOVERNING_BODY", "DELEGATION_PARLIAMENTARY",
                       "DELEGATION_JOINT_COMMITTEE", "DELEGATION_PARLIAMENTARY_ASSEMBLY")}
    bodies = fetch_bodies(sorted(orgs), args.offline)
    ROLE = {"CHAIR": "Président", "CHAIR_VICE": "Vice-président", "CHAIR_CO": "Coprésident", "MEMBER": "Membre",
            "MEMBER_SUBSTITUTE": "Suppléant", "QUAESTOR": "Questeur", "PRESIDENT": "Président", "PRESIDENT_VICE": "Vice-président"}
    fem_role = {"Président": "Présidente", "Vice-président": "Vice-présidente", "Coprésident": "Coprésidente",
                "Suppléant": "Suppléante", "Questeur": "Questrice"}
    for d in meps:
        com, fonctions = [], []
        for o, role, cls, debut, fin in d.pop("_membres"):
            if fin:
                continue
            lab = ROLE.get(role, role.replace("_", " ").lower())
            if d["femme"]:
                lab = fem_role.get(lab, lab)
            b = bodies.get(o) or {}
            if cls.startswith("COMMITTEE_PARLIAMENTARY"):
                if b.get("nom"):
                    com.append({"nom": b["nom"], "code": b.get("code"), "role": lab, "titulaire": role != "MEMBER_SUBSTITUTE"})
            elif cls == "EU_POLITICAL_GROUP" and role not in ("MEMBER",):
                fonctions.append(f"{lab} du groupe {GROUPES.get(d['groupe'], ('',))[0]}".strip())
            elif cls == "GOVERNING_BODY" and role not in ("MEMBER",):
                fonctions.append(f"{lab} — {b.get('nom') or 'Parlement européen'}")
            elif cls.startswith("DELEGATION") and role in ("CHAIR", "CHAIR_VICE") and b.get("nom"):
                fonctions.append(f"{lab} — {b['nom']}")
            elif cls == "EU_INSTITUTION" and role in ("PRESIDENT_VICE", "QUAESTOR", "PRESIDENT"):
                fonctions.append(f"{lab} du Parlement européen")
        com.sort(key=lambda c: (not c["titulaire"], c["role"] == "Membre", c["nom"]))
        d["commissions"] = com
        d["fonctions"] = sorted(set(fonctions))
    by_id = {d["id"]: d for d in meps}

    # ── Votes
    def theme_of(v):
        for c in comm.get(v, []):
            if c in COMMISSIONS:
                return COMMISSIONS[c][1]
        ref = votes[v]["procedure_reference"]
        c = (procs.get(ref) or {}).get("commission")
        if c in COMMISSIONS:
            return COMMISSIONS[c][1]
        for code in sorted(subj.get(v, [])):
            for pre, th in OEIL:
                if code.startswith(pre):
                    return th
        return "autre"

    vlist = []
    for v in reversed(order):
        r = votes[v]
        ref = r["procedure_reference"]
        p = procs.get(ref) or {}
        fr = collections.Counter(fr_pos[v].values())
        vlist.append({
            "id": int(v), "date": r["timestamp"][:10], "heure": r["timestamp"][11:16],
            "titre": p.get("titre") or r["display_title"] or r["procedure_title"], "titreEn": r["display_title"],
            "ref": ref or None, "type": r["procedure_type"] or None, "lecture": r["procedure_stage"] or None,
            "reference": r["reference"] or None, "adopte": r["result"] == "ADOPTED", "ta": r["texts_adopted_reference"] or None,
            "p": int(r["count_for"] or 0), "c": int(r["count_against"] or 0), "a": int(r["count_abstention"] or 0),
            "nv": int(r["count_did_not_vote"] or 0), "theme": theme_of(v),
            "commission": next((c for c in comm.get(v, []) if c in COMMISSIONS), None),
            "fr": [fr["p"], fr["c"], fr["a"], fr["."]],
            "g": {g: [c["p"], c["c"], c["a"], c["."]] for g, c in gcount[v].items() if g in GROUPES},
            "partis": {party_key(pid): k for pid, k in party_maj[v].items() if party_key(pid) and k},
        })

    # ── Textes (procédures)
    by_ref = collections.defaultdict(list)
    for x in vlist:
        if x["ref"]:
            by_ref[x["ref"]].append(x)
    textes = []
    for ref, vs in by_ref.items():
        p = procs.get(ref) or {}
        vs.sort(key=lambda x: (x["date"], x["heure"]))
        typ = vs[-1]["type"]
        lead = p.get("commission") or vs[-1]["commission"]
        rapp = []
        for pid, role, grp in p.get("rapporteurs", []):
            if role == "RAPPORTEUR_SHADOW" and pid not in by_id:
                continue
            rapp.append({"id": pid, "role": "rapporteur fictif" if role == "RAPPORTEUR_SHADOW" else "rapporteur",
                         "fr": pid in by_id, "groupe": {"PPE": "EPP", "VERTS/ALE": "GREEN_EFA", "S-D": "SD", "GUE/NGL": "GUE_NGL", "PFE": "PFE"}.get(grp, grp)})
        etapes = []
        seen = set()
        for d_, t in p.get("etapes", []):
            if t not in ETAPES or (t, d_) in seen:
                continue
            lab, acteur = ETAPES[t]
            if (lab, d_) in seen:
                continue
            seen.add((t, d_)); seen.add((lab, d_))
            etapes.append([d_, lab, acteur])
        textes.append({
            "ref": ref, "titre": vs[-1]["titre"], "titreEn": vs[-1]["titreEn"], "type": typ,
            "theme": vs[-1]["theme"], "commission": lead, "adopte": vs[-1]["adopte"], "date": vs[-1]["date"],
            "votes": [x["id"] for x in vs], "etapes": etapes, "rapporteurs": rapp,
            "lecture": vs[-1]["lecture"],
        })
    textes.sort(key=lambda t: t["date"], reverse=True)
    unique(textes, lambda t: slugify(t["titre"], 70), lambda t: slugify(t["ref"]))
    tslug = {t["ref"]: t["slug"] for t in textes}
    for x in vlist:
        x["texte"] = tslug.get(x["ref"])
    # Rapporteurs français : rôle sur la fiche du député
    for t in textes:
        for r in t["rapporteurs"]:
            if r["fr"]:
                by_id[r["id"]].setdefault("rapports", []).append([t["slug"], r["role"]])
        t["rapporteurs"] = [{**r, "nom": f"{by_id[r['id']]['prenom']} {by_id[r['id']]['nom']}" if r["fr"] else
                             (lambda m: f"{m['first_name']} {m['last_name'].title()}" if m else None)(members.get(r["id"]))}
                            for r in t["rapporteurs"]]

    # ── Partis français et accords entre eux
    partis = collections.OrderedDict()
    for key, (sigle, nom, couleur) in PARTIS.items():
        elus = [d for d in meps if d["actif"] and d["parti"] == key]
        if not elus:
            continue
        grp = collections.Counter(d["groupe"] for d in elus).most_common(1)[0][0]
        partis[key] = {"id": key, "sigle": sigle, "nom": nom, "couleur": couleur, "groupe": grp, "n": len(elus)}
    for d in meps:
        if d["parti"] and d["parti"] not in partis and d["parti"] in PARTIS:
            sigle, nom, couleur = PARTIS[d["parti"]]
            partis[d["parti"]] = {"id": d["parti"], "sigle": sigle, "nom": nom, "couleur": couleur, "groupe": d["groupe"], "n": 0}
    keys = [k for k, p in partis.items() if p["n"] >= 1 and k != "Sans parti"]
    accord = []
    for a in keys:
        row = []
        for b in keys:
            same = tot = 0
            for x in vlist:
                pa, pb = x["partis"].get(a), x["partis"].get(b)
                if pa and pb:
                    tot += 1
                    same += pa == pb
            row.append(round(100 * same / tot) if tot >= 20 else None)
        accord.append(row)
    # Cohésion de la délégation et votes contre le groupe européen
    for k in keys:
        n = ok = 0
        for x in vlist:
            pm = x["partis"].get(k)
            gm_ = gmaj[str(x["id"])].get(partis[k]["groupe"])
            if pm and gm_:
                n += 1
                ok += pm == gm_
        partis[k]["avecGroupe"] = round(100 * ok / n, 1) if n else None

    # ── Groupes
    groupes = []
    for i, (code, (sigle, nom, couleur)) in enumerate(GROUPES.items()):
        fr_n = sum(1 for d in meps if d["actif"] and d["groupe"] == code)
        groupes.append({"code": code, "sigle": sigle, "nom": nom, "couleur": couleur, "ordre": i,
                        "sieges": sieges.get(code, 0), "fr": fr_n})

    # ── Calendrier des sessions plénières
    nb = collections.Counter(x["date"] for x in vlist)
    sessions = []
    for s in fetch_sessions(args.offline):
        a, b = s.get("start_date"), s.get("end_date") or s.get("start_date")
        if not a or b < TERM_START:
            continue
        n = sum(c for d_, c in nb.items() if a <= d_ <= b)
        lieu = {"SXB": "Strasbourg", "BRU": "Bruxelles"}.get(s.get("location") or "")
        if not lieu:  # pas encore précisé : les sessions de 4 jours se tiennent à Strasbourg
            lieu = "Strasbourg" if (date.fromisoformat(b) - date.fromisoformat(a)).days >= 3 else None
        sessions.append({"debut": a, "fin": b, "lieu": lieu,
                         "votes": n, "avenir": b >= date.today().isoformat()})
    sessions.sort(key=lambda s: s["debut"])

    # ── Écriture
    OUT.mkdir(parents=True, exist_ok=True)
    positions = {"votes": [int(v) for v in order], "meps": {d["id"]: d.pop("_chain") for d in meps}}
    meta = {
        "genere": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "sourceMaj": maj_htv, "legislature": 10, "debut": TERM_START,
        "sieges": sum(sieges.values()), "fr": sum(1 for d in meps if d["actif"]),
        "attribution": "Data source: HowTheyVote.eu (Open Database License)",
    }
    def dump(name, data):
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    dump("europe.json", {"meta": meta, "groupes": groupes, "partis": list(partis.values()), "meps": meps,
                         "themes": THEMES, "types": TYPES, "commissions": {k: v[0] for k, v in COMMISSIONS.items()},
                         "sessions": sessions, "accord": {"partis": keys, "m": accord}})
    dump("votes.json", vlist)
    dump("textes.json", textes)
    dump("positions.json", positions)
    print(f"  ✓ {meta['fr']} eurodéputés français en exercice ({len(meps)} sur la législature), "
          f"{len(vlist)} votes, {len(textes)} textes, {len(sessions)} sessions")


if __name__ == "__main__":
    sys.exit(main())
