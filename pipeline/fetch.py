"""
Télécharge les archives open data de l'Assemblée nationale dans data/raw/.

Les archives AN contiennent aussi les sénateurs (AMO30) et toutes les étapes
de la navette au Sénat (dossiers législatifs) : une seule source suffit.

Usage :
    python pipeline/fetch.py            # retélécharge si l'archive a plus de 12 h
    python pipeline/fetch.py --force    # retélécharge tout
"""

import argparse
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BASE = "https://data.assemblee-nationale.fr/static/openData/repository/17"

ARCHIVES = {
    "Dossiers_Legislatifs.json.zip": f"{BASE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip",
    "Scrutins.json.zip": f"{BASE}/loi/scrutins/Scrutins.json.zip",
    "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip":
        f"{BASE}/amo/tous_acteurs_mandats_organes_xi_legislature/"
        "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip",
    "Agenda.json.zip": f"{BASE}/vp/reunions/Agenda.json.zip",
}


def download(name: str, url: str) -> None:
    dest = RAW / name
    tmp = dest.with_suffix(".part")
    print(f"  ↓ {name}")
    req = urllib.request.Request(url, headers={"User-Agent": "parlement-en-clair/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            zipfile.ZipFile(tmp).testzip()  # rejette les pages d'erreur HTML
            tmp.replace(dest)
            print(f"    {dest.stat().st_size / 1e6:.1f} Mo")
            return
        except Exception as e:  # noqa: BLE001
            print(f"    tentative {attempt + 1} échouée : {e}")
            time.sleep(5)
    raise RuntimeError(f"Impossible de télécharger {url}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-age", type=float, default=12, help="heures")
    args = p.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in ARCHIVES.items():
        dest = RAW / name
        if dest.exists() and not args.force:
            age_h = (time.time() - dest.stat().st_mtime) / 3600
            if age_h < args.max_age:
                print(f"  ✓ {name} (en cache, {age_h:.1f} h)")
                continue
        download(name, url)


if __name__ == "__main__":
    sys.exit(main())
