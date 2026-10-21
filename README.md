# Hémicycle

Un site pour suivre simplement le travail de l'Assemblée nationale et du Sénat :
composition des deux chambres, groupes, députés et sénateurs, gouvernement,
agenda, votes nominatifs — et surtout **le parcours complet de chaque loi**
(dépôt, commission, séance, navette, CMP, nouvelle lecture, lecture définitive,
49.3, Conseil constitutionnel, promulgation), raconté en français clair.

## Lancer le site en local

Double-cliquez sur `lancer_site.bat`, ou :

```sh
python pipeline/fetch.py          # télécharge les données ouvertes (≈ 60 Mo, cache de 12 h)
python -X utf8 pipeline/build.py      # construit site/data/ (≈ 20 s)
python -X utf8 pipeline/prerender.py  # génère dist/ : une page par loi, député, vote… + sitemap
python pipeline/serve.py 8000         # sert dist/ comme GitHub Pages
```

puis ouvrez <http://localhost:8000>. Aucune dépendance : Python 3.10+ (bibliothèque standard) et un navigateur.

## Organisation

| Dossier | Rôle |
|---|---|
| `pipeline/fetch.py` | Télécharge les archives open data de l'Assemblée dans `data/raw/` |
| `pipeline/build.py` | Calcule statuts, parcours, rattachement des votes aux textes, statistiques ; écrit `site/data/` |
| `pipeline/prerender.py` | Génère `dist/` : pages HTML pour le référencement (titres, descriptions, données structurées), `sitemap.xml`, `robots.txt` |
| `pipeline/serve.py` | Serveur local qui imite GitHub Pages |
| `site/` | Site statique (HTML, CSS, JavaScript sans framework ni étape de build) |
| `site/js/pages/` | Une page par fichier : `loi.js` (parcours d'un texte), `votes.js`, `chambres.js`, `personnes.js`, `comprendre.js`… |
| `.github/workflows/site.yml` | Reconstruit les données chaque matin et publie sur GitHub Pages |

## Données

Tout provient de [data.assemblee-nationale.fr](https://data.assemblee-nationale.fr) (licence Etalab) :

- **AMO30** : députés, sénateurs, ministres, groupes, commissions (le Sénat y est à jour du renouvellement de 2026) ;
- **Dossiers législatifs** : toutes les étapes de la navette, y compris au Sénat, en CMP, au Conseil constitutionnel et la promulgation ;
- **Scrutins** : chaque scrutin public de l'Assemblée, député par député ;
- **Agenda** : séances et réunions de commission à venir.

Limites connues :

- les votes nominatifs du **Sénat** ne sont pas dans ces données (les serveurs de data.senat.fr refusaient la connexion pendant le développement) : le site suit les décisions du Sénat étape par étape, sans le détail individuel ;
- les scrutins d'amendements ne sont pas toujours reliés à leur texte dans la source : `build.py` les rattache par le titre et la date de séance (≈ 96 % de rattachement) ;
- le thème d'un texte est déduit de son titre et de sa commission : c'est une indication, pas une classification officielle.

## Publier sur GitHub Pages

Dans les paramètres du dépôt GitHub : *Settings → Pages → Source : GitHub Actions*.
Avec un nom de domaine, renseigner `SITE_URL` et `SITE_BASE` en tête de `.github/workflows/site.yml`.
Le workflow publie à chaque push sur `main` et tous les jours à 4 h 15 UTC.
