"""
Download and store data about French deputies (Assemblée Nationale, 17th legislature).

Outputs in data/:
  deputes.json  — full data, one object per deputy
  deputes.csv   — same data as CSV
  organes.json  — political groups (groupe politique)
"""

import urllib.request
import zipfile
import json
import csv
import os
import io
from datetime import date, datetime

BASE_URL = "https://data.assemblee-nationale.fr/static/openData/repository/17"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

DEPUTIES_ZIP = (
    f"{BASE_URL}/amo/deputes_actifs_mandats_actifs_organes/"
    "AMO10_deputes_actifs_mandats_actifs_organes.json.zip"
)

FIELDS = [
    "id", "prenom", "nom", "date_naissance", "age",
    "profession", "groupe", "groupe_abrev",
    "departement", "circonscription",
]


def download(url: str) -> bytes:
    print(f"  Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Python/fetch-an-data"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def open_zip(data: bytes) -> dict:
    """Returns {filename: bytes} for all non-directory entries in the ZIP."""
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if not name.endswith("/"):
                result[name] = z.read(name)
    return result


def parse_uid(val) -> str:
    """UID may be a plain string or {"#text": "...", "@xmlns": "..."}."""
    return val.get("#text", "") if isinstance(val, dict) else str(val or "")


def to_list(val) -> list:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def age_from_dob(dob: str):
    try:
        bd = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except (ValueError, TypeError):
        return None


def parse_organes(files: dict) -> dict:
    """Parse political group (GP) organe files. Returns {uid: {...}}."""
    organes = {}
    for fname, content in files.items():
        if "/organe/" not in fname:
            continue
        try:
            org = json.loads(content).get("organe", {})
        except json.JSONDecodeError:
            continue
        if org.get("codeType") != "GP":
            continue
        uid = parse_uid(org.get("uid"))
        if uid:
            organes[uid] = {
                "uid": uid,
                "libelle": org.get("libelle", ""),
                "libelle_abrev": org.get("libelleAbrev", "") or org.get("libelleAbrege", ""),
            }
    return organes


def parse_acteurs(files: dict, organes: dict) -> list:
    """Parse acteur files and enrich with groupe politique info."""
    deputes = []
    for fname, content in files.items():
        if "/acteur/" not in fname:
            continue
        try:
            acteur = json.loads(content).get("acteur", {})
        except json.JSONDecodeError:
            continue

        uid = parse_uid(acteur.get("uid"))
        if not uid:
            continue

        etat = acteur.get("etatCivil", {})
        ident = etat.get("ident", {})
        naissance = etat.get("infoNaissance", {})
        profession = acteur.get("profession", {})
        dob = naissance.get("dateNais", "")

        groupe_libelle = ""
        groupe_abrev = ""
        departement = ""
        circonscription = ""

        for mandat in to_list(acteur.get("mandats", {}).get("mandat")):
            type_org = mandat.get("typeOrgane", "")

            org_ref = mandat.get("organes", {}).get("organeRef", "") if isinstance(mandat.get("organes"), dict) else ""

            if type_org == "GP" and not groupe_libelle:
                if org_ref in organes:
                    groupe_libelle = organes[org_ref]["libelle"]
                    groupe_abrev = organes[org_ref]["libelle_abrev"]

            elif type_org == "ASSEMBLEE":
                lieu = mandat.get("election", {}).get("lieu", {})
                departement = departement or lieu.get("departement", "") or lieu.get("libelle", "")
                circonscription = circonscription or str(lieu.get("numCirco", ""))

        deputes.append({
            "id": uid,
            "prenom": ident.get("prenom", ""),
            "nom": ident.get("nom", ""),
            "date_naissance": dob,
            "age": age_from_dob(dob),
            "profession": profession.get("libelleCourant", ""),
            "groupe": groupe_libelle,
            "groupe_abrev": groupe_abrev,
            "departement": departement,
            "circonscription": circonscription,
        })

    deputes.sort(key=lambda d: (d["nom"], d["prenom"]))
    return deputes


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Fetching deputies ZIP...")
    files = open_zip(download(DEPUTIES_ZIP))
    print(f"  ZIP contains {len(files)} files")

    organes = parse_organes(files)
    print(f"  Parsed {len(organes)} political groups")

    organes_path = os.path.join(DATA_DIR, "organes.json")
    with open(organes_path, "w", encoding="utf-8") as f:
        json.dump(list(organes.values()), f, ensure_ascii=False, indent=2)
    print(f"  Saved {organes_path}")

    deputes = parse_acteurs(files, organes)
    print(f"  Parsed {len(deputes)} deputies")

    json_path = os.path.join(DATA_DIR, "deputes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(deputes, f, ensure_ascii=False, indent=2)
    print(f"  Saved {json_path}")

    csv_path = os.path.join(DATA_DIR, "deputes.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(deputes)
    print(f"  Saved {csv_path}")


if __name__ == "__main__":
    main()
