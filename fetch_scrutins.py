"""
Download and store voting records (scrutins) from Assemblée Nationale (17th legislature).

Outputs in data/:
  scrutins.json              — full scrutin data (one object per vote)
  scrutins_summary.csv       — one row per scrutin: title, date, result, totals
  scrutins_votes_groupe.csv  — one row per (scrutin × groupe politique): pour/contre/abstention
  scrutins_votes_depute.csv  — one row per (scrutin × député): individual vote
"""

import urllib.request
import zipfile
import json
import csv
import os
import io

BASE_URL = "https://data.assemblee-nationale.fr/static/openData/repository/17"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

SCRUTINS_ZIP = f"{BASE_URL}/loi/scrutins/Scrutins.json.zip"


def download(url: str) -> bytes:
    print(f"  Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Python/fetch-an-data"})
    with urllib.request.urlopen(req, timeout=120) as r:
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


def to_int(val):
    try:
        v = val.get("#text", val) if isinstance(val, dict) else val
        return int(v)
    except (TypeError, ValueError, AttributeError):
        return None


def parse_groupe_votes(ventilation: dict) -> list:
    """
    Returns one dict per groupe with:
      groupe_ref, pour, contre, abstention,
      pours_deputes, contres_deputes, abstentions_deputes, non_votants_deputes
    """
    rows = []
    groupes = ventilation.get("organe", {}).get("groupes", {}).get("groupe", [])
    for g in to_list(groupes):
        vote = g.get("vote", {})
        decompte = vote.get("decompteVoix", {})
        nominatif = vote.get("decompteNominatif", {})

        def refs(section_key: str) -> list:
            section = nominatif.get(section_key)
            if not section or not isinstance(section, dict):
                return []
            return [
                v.get("acteurRef", "") if isinstance(v, dict) else str(v)
                for v in to_list(section.get("votant"))
                if v
            ]

        rows.append({
            "groupe_ref": g.get("organeRef", ""),
            "pour": to_int(decompte.get("pour")),
            "contre": to_int(decompte.get("contre")),
            "abstention": to_int(decompte.get("abstentions")),
            "pours_deputes": refs("pours"),
            "contres_deputes": refs("contres"),
            "abstentions_deputes": refs("abstentions"),
            "non_votants_deputes": refs("nonVotants") + refs("nonVotantsVolontaires"),
        })
    return rows


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Fetching scrutins ZIP...")
    files = open_zip(download(SCRUTINS_ZIP))

    json_files = {k: v for k, v in files.items() if k.endswith(".json")}
    if not json_files:
        raise RuntimeError("No JSON files found in scrutins ZIP")

    # Each file contains one scrutin: {"scrutin": {...}}
    scrutins_raw = []
    for content in json_files.values():
        raw = json.loads(content)
        s = raw.get("scrutin")
        if isinstance(s, dict):
            scrutins_raw.append(s)
        elif isinstance(s, list):
            scrutins_raw.extend(s)
    scrutins_raw.sort(key=lambda s: s.get("dateScrutin", ""))
    print(f"  Found {len(scrutins_raw)} scrutins")

    scrutins_summary = []
    votes_groupe_rows = []
    votes_depute_rows = []

    for s in scrutins_raw:
        uid = s.get("uid", "")
        titre = s.get("titre", "")
        date_scrutin = s.get("dateScrutin", "")
        sort_code = s.get("sort", {}).get("code", "")
        type_vote = s.get("typeVote", {}).get("libelleTypeVote", "")
        objet = s.get("objet") or {}
        dos_leg = objet.get("dossierLegislatif") or {}
        dossier_ref = dos_leg.get("dossierRef", "") if isinstance(dos_leg, dict) else ""

        synthese = s.get("syntheseVote", {})
        decompte = synthese.get("decompte", {}) if isinstance(synthese, dict) else {}
        scrutins_summary.append({
            "uid": uid,
            "date": date_scrutin,
            "titre": titre,
            "type_vote": type_vote,
            "adopte": sort_code,
            "dossier_ref": dossier_ref,
            "nb_votants": to_int(synthese.get("nombreVotants")),
            "pour": to_int(decompte.get("pour")),
            "contre": to_int(decompte.get("contre")),
            "abstention": to_int(decompte.get("abstentions")),
        })

        for g in parse_groupe_votes(s.get("ventilationVotes", {})):
            votes_groupe_rows.append({
                "scrutin_uid": uid,
                "scrutin_date": date_scrutin,
                "adopte": sort_code,
                "groupe_ref": g["groupe_ref"],
                "pour": g["pour"],
                "contre": g["contre"],
                "abstention": g["abstention"],
            })
            for dep in g["pours_deputes"]:
                votes_depute_rows.append({
                    "scrutin_uid": uid,
                    "scrutin_date": date_scrutin,
                    "depute_ref": dep,
                    "groupe_ref": g["groupe_ref"],
                    "vote": "pour",
                })
            for dep in g["contres_deputes"]:
                votes_depute_rows.append({
                    "scrutin_uid": uid,
                    "scrutin_date": date_scrutin,
                    "depute_ref": dep,
                    "groupe_ref": g["groupe_ref"],
                    "vote": "contre",
                })
            for dep in g["abstentions_deputes"]:
                votes_depute_rows.append({
                    "scrutin_uid": uid,
                    "scrutin_date": date_scrutin,
                    "depute_ref": dep,
                    "groupe_ref": g["groupe_ref"],
                    "vote": "abstention",
                })
            for dep in g["non_votants_deputes"]:
                votes_depute_rows.append({
                    "scrutin_uid": uid,
                    "scrutin_date": date_scrutin,
                    "depute_ref": dep,
                    "groupe_ref": g["groupe_ref"],
                    "vote": "non_votant",
                })

    # Save full JSON
    json_path = os.path.join(DATA_DIR, "scrutins.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scrutins_summary, f, ensure_ascii=False, indent=2)
    print(f"  Saved {json_path}")

    # Save summary CSV
    summary_path = os.path.join(DATA_DIR, "scrutins_summary.csv")
    summary_fields = ["uid", "date", "titre", "type_vote", "adopte", "dossier_ref",
                      "nb_votants", "pour", "contre", "abstention"]
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(scrutins_summary)
    print(f"  Saved {summary_path}")

    # Save per-groupe votes CSV
    groupe_path = os.path.join(DATA_DIR, "scrutins_votes_groupe.csv")
    groupe_fields = ["scrutin_uid", "scrutin_date", "adopte", "groupe_ref",
                     "pour", "contre", "abstention"]
    with open(groupe_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=groupe_fields)
        writer.writeheader()
        writer.writerows(votes_groupe_rows)
    print(f"  Saved {groupe_path}")

    # Save per-deputy votes CSV
    depute_path = os.path.join(DATA_DIR, "scrutins_votes_depute.csv")
    depute_fields = ["scrutin_uid", "scrutin_date", "depute_ref", "groupe_ref", "vote"]
    with open(depute_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=depute_fields)
        writer.writeheader()
        writer.writerows(votes_depute_rows)
    print(f"  Saved {depute_path} ({len(votes_depute_rows):,} rows)")


if __name__ == "__main__":
    main()
