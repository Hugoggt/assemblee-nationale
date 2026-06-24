"""
Download and store legislative dossiers (propositions/projets de loi) from
Assemblée Nationale (17th legislature).

Outputs in data/:
  dossiers.json  — one object per dossier
  dossiers.csv   — same data as CSV

Each dossier links to scrutins via the dossier_ref field in scrutins_summary.csv.
"""

import urllib.request
import zipfile
import json
import csv
import os
import io

BASE_URL = "https://data.assemblee-nationale.fr/static/openData/repository/17"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

DOSSIERS_ZIP = f"{BASE_URL}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip"

FIELDS = ["uid", "titre", "type_dossier", "date_depot", "legislature", "statut", "url_an"]


def download(url: str) -> bytes:
    print(f"  Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Python/fetch-an-data"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def open_zip(data: bytes) -> dict:
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if not name.endswith("/"):
                result[name] = z.read(name)
    return result


def to_list(val) -> list:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def first_str(val) -> str:
    """Return first non-empty string from a value that may be str, list, or dict."""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return next((v for v in val if isinstance(v, str) and v), "")
    if isinstance(val, dict):
        return val.get("#text", "") or next((str(v) for v in val.values() if v), "")
    return str(val) if val else ""


def libelle_str(v) -> str:
    """Extract human-readable string from a libelleActe field (may be dict or str)."""
    if isinstance(v, dict):
        return v.get("nomCanonique") or v.get("libelleCourt") or ""
    return str(v) if v else ""


def walk_actes(actes_node: dict) -> list:
    """Recursively collect all acteLegislatif dicts in the tree."""
    result = []
    items = to_list(actes_node.get("acteLegislatif") if isinstance(actes_node, dict) else None)
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(item)
        nested = item.get("actesLegislatifs")
        if nested:
            result.extend(walk_actes(nested))
    return result


def parse_dossier(dossier: dict) -> dict:
    uid = first_str(dossier.get("uid"))

    titre_dos = dossier.get("titreDossier") or {}
    titre = titre_dos.get("titre", "") if isinstance(titre_dos, dict) else first_str(titre_dos)
    if not titre:
        titre = first_str(dossier.get("titre"))
    titre_chemin = titre_dos.get("titreChemin", "") if isinstance(titre_dos, dict) else ""
    url_an = (
        f"https://www.assemblee-nationale.fr/dyn/17/dossiers/{titre_chemin}"
        if titre_chemin else ""
    )

    proc = dossier.get("procedureParlementaire") or {}
    type_dossier = proc.get("libelle", "") if isinstance(proc, dict) else ""

    legislature = first_str(dossier.get("legislature"))

    # Walk ALL nested actes to find date_depot (first DEPOT sub-acte) and statut (last top-level acte)
    actes_root = dossier.get("actesLegislatifs") or {}
    top_actes = to_list(actes_root.get("acteLegislatif") if isinstance(actes_root, dict) else None)
    all_actes = walk_actes(actes_root)

    date_depot = ""
    for acte in all_actes:
        code = (acte.get("codeActe") or "").upper()
        if "DEPOT" in code:
            raw_date = acte.get("dateActe") or ""
            if raw_date:
                date_depot = str(raw_date)[:10]  # keep YYYY-MM-DD only
                break

    statut = ""
    if top_actes:
        last_top = next((a for a in reversed(top_actes) if isinstance(a, dict)), {})
        statut = libelle_str(last_top.get("libelleActe"))

    return {
        "uid": uid,
        "titre": titre,
        "type_dossier": type_dossier,
        "date_depot": date_depot,
        "legislature": legislature,
        "statut": statut,
        "url_an": url_an,
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Fetching dossiers législatifs ZIP (this may take a moment)...")
    files = open_zip(download(DOSSIERS_ZIP))
    print(f"  ZIP contains {len(files)} files")

    # Each file is json/dossierParlementaire/DLR*.json with one {"dossierParlementaire": {...}}
    print("  Parsing dossiers...")
    dossiers_raw = []
    for name, content in files.items():
        if not name.endswith(".json"):
            continue
        try:
            raw = json.loads(content)
        except Exception:
            continue
        dp = raw.get("dossierParlementaire")
        if isinstance(dp, dict):
            dossiers_raw.append(dp)
    print(f"  Found {len(dossiers_raw)} dossiers")

    dossiers = []
    for d in dossiers_raw:
        if not isinstance(d, dict):
            continue
        try:
            dossiers.append(parse_dossier(d))
        except Exception:
            continue

    # Sort by date_depot descending (most recent first)
    dossiers.sort(key=lambda d: d["date_depot"], reverse=True)

    # Save JSON
    json_path = os.path.join(DATA_DIR, "dossiers.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dossiers, f, ensure_ascii=False, indent=2)
    print(f"  Saved {json_path}")

    # Save CSV
    csv_path = os.path.join(DATA_DIR, "dossiers.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(dossiers)
    print(f"  Saved {csv_path}")


if __name__ == "__main__":
    main()
