"""
Classify legislative dossiers into themes using keyword matching on their titles.
Adds 'theme' and 'theme_emoji' columns to dossiers.csv → output/dossiers_themes.csv

Run after fetch_dossiers.py.
"""

import csv
from collections import Counter
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"

# (theme_name, emoji, keywords_fr)  — first match wins, order matters
THEMES = [
    ("Budget & Finances", "💰", [
        "budget", "fiscal", "impôt", "taxe", "finances publiques", "PLF",
        "PLFSS", "recette", "dépense", "dette", "déficit", "financement",
        "crédit", "cotisation", "trésor", "loi de finances",
    ]),
    ("Santé & Social", "🏥", [
        "santé", "médecin", "hôpital", "soin", "maladie", "infirmier",
        "pharmacie", "solidarité", "handicap", "retraite", "pension",
        "famille", "enfant", "allocat", "aide social", "protection sociale",
        "maternité", "dépendance",
    ]),
    ("Travail & Emploi", "💼", [
        "travail", "emploi", "chômage", "salarié", "syndicat", "licenciem",
        "apprentissage", "prud", "SMIC", "rémunérat", "convention collective",
        "fonction publique", "fonctionnaire",
    ]),
    ("Éducation & Recherche", "🎓", [
        "éducation", "école", "université", "enseignement", "étudiant",
        "lycée", "collège", "baccalauréat", "recherche", "science",
        "formation professionnelle",
    ]),
    ("Justice & Sécurité", "⚖️", [
        "justice", "pénal", "crime", "tribunal", "juge", "procureur",
        "prison", "police", "gendarmerie", "sécurité", "terrorisme",
        "violence", "délinquance", "détention", "garde à vue",
        "cybercriminalité", "immigration", "asile", "étranger",
    ]),
    ("Environnement & Énergie", "🌿", [
        "environnement", "énergie", "climatique", "biodiversité",
        "nucléaire", "renouvelable", "carbone", "écologie",
        "transition énergétique", "eau", "déchet", "pollution",
        "zéro artificialisation", "forêt",
    ]),
    ("Logement & Urbanisme", "🏗️", [
        "logement", "habitat", "immobilier", "loyer", "locataire",
        "bailleur", "urbanisme", "construction", "HLM",
        "rénovation", "copropriété", "foncier",
    ]),
    ("Transport & Mobilité", "🚆", [
        "transport", "ferroviaire", "aérien", "SNCF", "autoroute",
        "mobilité", "aviation", "port", "véhicule électrique",
    ]),
    ("Agriculture & Alimentation", "🌾", [
        "agricult", "alimentat", "élevage", "pêche", "viticulture",
        "pesticide", "semence", "agroalimentaire", "rural", "paysan",
    ]),
    ("Défense & International", "🌍", [
        "défense", "armée", "militaire", "traité international",
        "convention internationale", "accord bilatéral", "coopération internationale",
        "OTAN", "aide au développement", "Affaires étrangères",
    ]),
    ("Institutions & Démocratie", "🏛️", [
        "constitution", "référendum", "élection", "parlement", "sénat",
        "loi organique", "décentralisation", "collectivité territoriale",
        "commune", "démocratie", "représentation", "suffrage",
    ]),
    ("Numérique & Tech", "📡", [
        "numérique", "digital", "internet", "données personnelles",
        "intelligence artificielle", "cybersécurité", "plateforme",
        "télécom", "technologie",
    ]),
    ("Outre-mer", "🏝️", [
        "outre-mer", "Guadeloupe", "Martinique", "Réunion",
        "Mayotte", "Guyane", "Nouvelle-Calédonie", "Polynésie",
        "Saint-Pierre", "Saint-Martin",
    ]),
]

FALLBACK = ("Autre", "📌")


def classify(titre: str) -> tuple[str, str]:
    if not isinstance(titre, str):
        return FALLBACK
    low = titre.lower()
    for name, emoji, keywords in THEMES:
        if any(kw.lower() in low for kw in keywords):
            return name, emoji
    return FALLBACK


def main():
    src = OUTPUT_DIR / "dossiers.csv"
    if not src.exists():
        print("dossiers.csv not found — run fetch_dossiers.py first.")
        return

    rows = []
    with open(src, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            theme, emoji = classify(row.get("titre", ""))
            row["theme"] = theme
            row["theme_emoji"] = emoji
            rows.append(row)

    if not rows:
        print("dossiers.csv is empty.")
        return

    dst = OUTPUT_DIR / "dossiers_themes.csv"
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(r["theme"] for r in rows)
    print(f"Classified {len(rows)} dossiers into {len(counts)} themes:")
    for name, n in sorted(counts.items(), key=lambda x: -x[1]):
        emoji = next((e for nm, e, _ in THEMES if nm == name), "📌")
        print(f"  {n:4d}  {emoji} {name}")
    print(f"\nSaved → {dst}")


if __name__ == "__main__":
    main()
