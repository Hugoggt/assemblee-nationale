"""
Génère le site publiable dans dist/ : une vraie page HTML par loi, député, sénateur, groupe,
grand vote et partie du guide, lisible par les moteurs de recherche, + sitemap.xml et robots.txt.

    python pipeline/prerender.py

Variables d'environnement :
  SITE_URL   adresse publique du site, sans « / » final (ex. https://votes-assemblees.fr)
  SITE_BASE  chemin du site sur le domaine (« / » avec un domaine à soi,
             « /assemblee-nationale/ » sur hugoggt.github.io)
"""

import datetime as dt
import html
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
DIST = ROOT / "dist"
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
BASE = os.environ.get("SITE_BASE", "/")
if not BASE.endswith("/"):
    BASE += "/"
NOM = "Hémicycle"

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
KIND = {"ensemble": "Vote sur l'ensemble", "censure": "Motion de censure", "motion": "Motion de procédure",
        "article": "Vote d'un article", "amendement": "Amendement", "declaration": "Déclaration du Gouvernement",
        "resolution": "Résolution", "autre": "Vote"}
POS = {"p": "pour", "c": "contre", "a": "abstention"}
CH = {"AN": "Assemblée nationale", "SN": "Sénat", "CMP": "Commission mixte paritaire", "CC": "Conseil constitutionnel", "PROM": "Promulgation"}
RES = {"adopte": "adopté", "conforme": "adopté sans modification", "modifie": "modifié", "rejete": "rejeté",
       "adopte493": "adopté par le 49.3", "rejete493": "rejeté", "motion_adoptee": "rejeté (motion de rejet)"}

GUIDE = [
    ("chambres", "Assemblée nationale et Sénat : quelles différences ?", "Les deux chambres du Parlement : 577 députés élus au suffrage direct, 348 sénateurs élus par les grands électeurs, et leurs pouvoirs respectifs."),
    ("origine", "Projet de loi et proposition de loi : d'où viennent les lois ?", "La différence entre un projet de loi du Gouvernement et une proposition de loi des parlementaires, et qui fixe l'ordre du jour."),
    ("parcours", "Le parcours d'une loi, étape par étape", "Dépôt, commission, séance publique, navette, CMP, Conseil constitutionnel, promulgation : comment une loi est votée en France."),
    ("acceleree", "La procédure accélérée expliquée", "Comment le Gouvernement raccourcit la navette parlementaire avec la procédure accélérée."),
    ("cmp", "La commission mixte paritaire (CMP) expliquée simplement", "7 députés et 7 sénateurs cherchent un compromis quand les deux chambres ne sont pas d'accord : fonctionnement et bilan de la CMP."),
    ("dernier-mot", "Qui a le dernier mot, l'Assemblée ou le Sénat ?", "Nouvelle lecture, lecture définitive : quand l'Assemblée nationale tranche, et quand le Sénat garde un droit de veto."),
    ("cc", "Le Conseil constitutionnel et la promulgation d'une loi", "Saisine par 60 députés ou sénateurs, censure totale ou partielle, promulgation sous 15 jours."),
    ("arme", "Le 49.3 et la motion de censure : comment ça marche ?", "L'article 49 alinéa 3 permet d'adopter un texte sans vote ; la motion de censure, à 289 voix, peut renverser le Gouvernement."),
    ("vote", "Comment votent les députés ?", "Vote à main levée, scrutin public ordinaire, scrutin solennel, délégation de vote : les règles du vote à l'Assemblée."),
    ("groupes", "Groupes parlementaires et majorité absolue", "Comment se forment les groupes politiques et pourquoi il faut 289 députés pour la majorité absolue."),
    ("speciales", "Budget, Constitution, lois organiques : les lois à part", "Les règles particulières des lois de finances, des révisions constitutionnelles, des lois organiques et des traités."),
    ("quiz", "Quiz : testez vos connaissances sur le Parlement", "Huit questions pour vérifier que vous avez compris le fonctionnement de l'Assemblée nationale et du Sénat."),
    ("glossaire", "Glossaire du Parlement", "Navette, CMP, 49.3, lecture définitive, amendement, scrutin public : les mots du Parlement expliqués."),
]

e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


def fdate(d):
    if not d:
        return ""
    y, m, j = d[:10].split("-")
    return f"{'1er' if j == '01' else int(j)} {MOIS[int(m) - 1]} {y}"


def fr(x):
    return "–" if x is None else f"{x:g}".replace(".", ",")


def load(name):
    with open(DATA / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def clip(s, n=158):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


class Pages:
    def __init__(self):
        self.template = (SITE / "index.html").read_text(encoding="utf-8")
        self.urls = []  # (chemin, lastmod, priorité)

    def write(self, path, title, desc, body, lastmod=None, priority="0.5", jsonld=None, noindex=False, og_type="website"):
        url = SITE_URL + "/" + path if path else SITE_URL + "/"
        full_title = f"{title} · {NOM}" if path else f"{NOM} · {title}"
        head = [
            f'<meta name="description" content="{e(clip(desc))}">',
            f'<link rel="canonical" href="{e(url)}">',
            f'<meta property="og:type" content="{og_type}">',
            f'<meta property="og:site_name" content="{NOM}">',
            f'<meta property="og:title" content="{e(title)}">',
            f'<meta property="og:description" content="{e(clip(desc))}">',
            f'<meta property="og:url" content="{e(url)}">',
            f'<meta property="og:image" content="{e(SITE_URL + "/og.png")}">',
            '<meta property="og:locale" content="fr_FR">',
            '<meta name="twitter:card" content="summary_large_image">',
        ]
        if noindex:
            head.append('<meta name="robots" content="noindex">')
        for j in (jsonld or []):
            head.append('<script type="application/ld+json">' + json.dumps(j, ensure_ascii=False).replace("</", "<\\/") + "</script>")
        page = self.template
        page = page.replace('<base href="/">', f'<base href="{BASE}">')
        page = re.sub(r"<title>.*?</title>", f"<title>{e(full_title)}</title>", page, count=1)
        page = re.sub(r'<meta name="description" content="[^"]*">', "\n  ".join(head), page, count=1)
        page = page.replace('<div class="loading">Chargement…</div>', f'<div class="page prerender">{body}</div>')
        dest = DIST / ("index.html" if not path else f"{path}.html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        if not noindex:
            self.urls.append((path, lastmod, priority))


def breadcrumb(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE_URL}/{p}"} for i, (n, p) in enumerate(items)]}


def main():
    if not (DATA / "meta.json").exists():
        raise SystemExit("Lancez d'abord pipeline/build.py")
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(SITE, DIST, ignore=shutil.ignore_patterns("og-card.html"))

    meta = load("meta")
    today = meta["genere"][:10]
    k = meta["chiffres"]
    G = load("groupes")
    groupes = {g["id"]: g for g in G["groupes"]}
    D = load("dossiers")
    dossiers = {d["uid"]: d for d in D["dossiers"]}
    themes = D["themes"]
    deps = load("deputes")
    dep_by = {d["id"]: d for d in deps}
    sens = load("senateurs")
    S = load("scrutins")
    rows = [dict(zip(S["cols"], r)) for r in S["rows"]]
    chrono = sorted(rows, key=lambda r: r["num"])
    P = Pages()

    def gname(gid):
        g = groupes.get(gid)
        return g["sigle"] if g else ""

    def loi_link(d):
        return f'<a href="loi/{e(d["slug"])}">{e(d["titre"])}</a>'

    def person_link(p, chamber):
        if not p:
            return ""
        slug = p.get("slug") or p.get("id")
        name = p.get("nom") if "prenom" not in p else f"{p.get('prenom') or ''} {p.get('nom') or ''}".strip()
        return f'<a href="{"depute" if chamber == "AN" else "senateur"}/{e(slug)}">{e(name or slug)}</a>'

    # ── Accueil et pages de rubrique
    recent = sorted([d for d in D["dossiers"] if d["cat"] == "loi" and d["examine"]], key=lambda d: d["maj"] or "", reverse=True)[:15]
    P.write("", "les votes de l'Assemblée nationale et du Sénat",
            f"Suivez le Parlement simplement : {k['deputes']} députés, {k['senateurs']} sénateurs, {k['promulguees']} lois promulguées, "
            f"{k['scrutins']} votes nominatifs. Où en est chaque loi, qui a voté quoi, qui vote avec qui.",
            f"<h1>Suivre le Parlement</h1><p>Composition, lois et votes de l'Assemblée nationale et du Sénat.</p>"
            f"<h2>Textes en cours</h2><ul>{''.join(f'<li>{loi_link(d)}</li>' for d in recent)}</ul>"
            '<p><a href="lois">Toutes les lois</a> · <a href="votes">Tous les votes</a> · <a href="comparer">Comparer les votes</a> · '
            '<a href="assemblee">Assemblée nationale</a> · <a href="senat">Sénat</a> · <a href="guide">Guide du Parlement</a></p>',
            today, "1.0", [{"@context": "https://schema.org", "@type": "WebSite", "name": NOM, "url": SITE_URL + "/",
                             "potentialAction": {"@type": "SearchAction", "target": SITE_URL + "/recherche?q={q}", "query-input": "required name=q"}}])

    lois_ex = sorted([d for d in D["dossiers"] if d["cat"] == "loi" and d["examine"]], key=lambda d: d["maj"] or "", reverse=True)
    P.write("lois", "Toutes les lois en discussion au Parlement",
            f"{k['textes']} propositions et projets de loi, {k['promulguees']} lois promulguées : suivez la navette de chaque texte entre l'Assemblée nationale et le Sénat.",
            "<h1>Lois</h1><ul>" + "".join(f"<li>{loi_link(d)} — {e(d['statutLabel'])}</li>" for d in lois_ex[:300]) + "</ul>", today, "0.9")
    grands = [r for r in rows if r["kind"] in ("ensemble", "censure", "motion", "declaration") or r["type"] == "SPS"]
    P.write("votes", "Les votes de l'Assemblée nationale, député par député",
            f"Les {k['scrutins']} scrutins publics de la législature : résultat, vote de chaque groupe et de chaque député.",
            "<h1>Votes</h1><ul>" + "".join(f'<li><a href="vote/{r["num"]}">{e(r["titre"])}</a> — {fdate(r["date"])}</li>' for r in grands[:200]) + "</ul>", today, "0.9")
    P.write("comparer", "Comparer les votes des groupes et des députés",
            "Qui vote quoi, sur quel sujet ? Comparez les votes des groupes politiques et des députés thème par thème, et voyez qui vote avec qui.",
            "<h1>Comparer les votes</h1><p>Choisissez un sujet, puis les groupes ou les députés à comparer.</p>", today, "0.8")
    for ch, path, nom, n in (("AN", "assemblee", "Assemblée nationale", 577), ("SN", "senat", "Sénat", 348)):
        gs = sorted([g for g in G["groupes"] if g["chambre"] == ch and g["effectif"]], key=lambda g: g["ordre"])
        P.write(path, f"{nom} : composition et groupes politiques",
                f"La composition de l'{nom.lower() if ch == 'AN' else 'Sénat'} : {n} élus répartis en {len(gs)} groupes. " + ", ".join(f"{g['sigle']} {g['effectif']}" for g in gs) + ".",
                f"<h1>{e(nom)}</h1><ul>" + "".join(f'<li><a href="groupe/{e(g["slug"])}">{e(g["nom"])} ({e(g["sigle"])})</a> : {g["effectif"]} sièges</li>' for g in gs) + "</ul>", today, "0.8")
    P.write("deputes", "Les 577 députés : votes, présence et groupe",
            "Retrouvez votre député : son groupe, sa circonscription, ses votes, sa participation et les textes qu'il a déposés.",
            "<h1>Députés</h1><ul>" + "".join(f'<li><a href="depute/{e(d["slug"])}">{e(d["prenom"])} {e(d["nom"])}</a> — {e(gname(d["groupe"]))}, {e(d.get("departement"))}</li>' for d in deps if d["actif"]) + "</ul>", today, "0.8")
    P.write("senateurs", "Les 348 sénateurs : groupe, département, commission",
            "La liste des sénateurs en exercice, avec leur groupe politique, leur département et les textes qu'ils ont portés.",
            "<h1>Sénateurs</h1><ul>" + "".join(f'<li><a href="senateur/{e(d["slug"])}">{e(d["prenom"])} {e(d["nom"])}</a> — {e(gname(d["groupe"]))}, {e(d.get("departement"))}</li>' for d in sens) + "</ul>", today, "0.7")
    pm = next((m for m in meta["gouvernement"]["membres"] if m["fonction"] == "Premier ministre"), None)
    P.write("gouvernement", "Le Gouvernement, le 49.3 et les motions de censure",
            f"La composition du Gouvernement{(' de ' + pm['prenom'] + ' ' + pm['nom']) if pm else ''}, les {k['art493']} recours au 49.3 et les {k['censures']} motions de censure de la législature.",
            "<h1>Gouvernement</h1><ul>" + "".join(f"<li>{e(m['prenom'])} {e(m['nom'])} — {e(m['portefeuille'])}</li>" for m in meta["gouvernement"]["membres"]) + "</ul>", today, "0.7")
    P.write("agenda", "Agenda de l'Assemblée nationale : séances et commissions",
            "Ce qui est programmé à l'Assemblée nationale dans les prochains jours : séances publiques et réunions de commission.",
            "<h1>Agenda</h1>", today, "0.6")
    P.write("a-propos", "À propos, sources et mentions légales",
            "Hémicycle est un site indépendant qui rend lisibles les données publiques du Parlement. Sources, méthode, mentions légales.",
            "<h1>À propos</h1><p>Site indépendant, données de l'open data de l'Assemblée nationale (Licence Ouverte).</p>", today, "0.3")
    P.write("guide", "Guide du Parlement : comprendre comment une loi est votée",
            "Le jeu parlementaire expliqué simplement : navette, CMP, 49.3, motion de censure, Conseil constitutionnel, illustré par les vrais textes.",
            "<h1>Guide du Parlement</h1><ul>" + "".join(f'<li><a href="guide/{sid}">{e(t)}</a></li>' for sid, t, _ in GUIDE) + "</ul>", today, "0.8")
    for sid, t, desc in GUIDE:
        P.write(f"guide/{sid}", t, desc, f"<h1>{e(t)}</h1><p>{e(desc)}</p><p><a href=\"guide\">Tout le guide</a></p>", today, "0.7",
                [breadcrumb([("Guide", "guide"), (t, f"guide/{sid}")])], og_type="article")
    P.write("recherche", "Recherche", "Rechercher un député, un sénateur ou une loi.", "<h1>Recherche</h1>", noindex=True)

    # ── Lois
    for uid, s in dossiers.items():
        try:
            det = json.loads((DATA / "dossiers" / f"{uid}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        th = themes.get(s["theme"], {}).get("label", "")
        is_loi = s["cat"] == "loi"
        title = f"{s['titre']} : parcours et votes" if is_loi and s.get("examine") else s["titre"]
        auteur = "le Gouvernement" if s.get("gouv") else (s.get("auteur") or {}).get("nom", "")
        desc = (f"{s['typeLabel']}" + (f" · {s['statutLabel'].lower()}" if s.get("statutLabel") else "") +
                (f". Texte déposé par {auteur}" if auteur else (". Texte déposé" if s.get("depot") else "")) +
                (f" le {fdate(s['depot'])}" if s.get("depot") else "") +
                (f". Étape actuelle : {s['etape']}" if s.get("etape") and s["statut"] != "promulguee" else "") +
                (f". Loi n° {s['loi']}" if s.get("loi") else "") +
                ". Le parcours complet entre l'Assemblée et le Sénat et les votes de chaque groupe.")
        steps = []
        for st in det.get("steps", []):
            if st["chambre"] not in CH:
                continue
            r = RES.get(st.get("resultat") or "", "")
            if st["chambre"] == "CMP":
                r = {"accord": "accord", "desaccord": "échec"}.get(st.get("cmp"), "")
            steps.append(f"<li><b>{e(CH[st['chambre']])}</b> — {e(st['label'])}{(' : ' + e(r)) if r else ''}{(' (' + fdate(st['fin']) + ')') if st.get('fin') else ''}</li>")
        scr = sorted(det.get("scrutins") or [], key=lambda x: -x[0])
        key = [x for x in scr if x[2] in ("ensemble", "motion", "censure")][:10]
        body = (f"<h1>{e(s['titre'])}</h1><p>{e(s['statutLabel'])} · {e(s['typeLabel'])}" + (f" · {e(th)}" if th else "") + "</p>"
                + (f"<p>{e(det.get('titreLong') or '')}</p>" if det.get("titreLong") else "")
                + (f"<p>Auteur : {person_link(s['auteur'], s['auteur'].get('chambre'))}</p>" if s.get("auteur") and not s.get("gouv") else "")
                + (f"<h2>Parcours</h2><ol>{''.join(steps)}</ol>" if steps else "")
                + (f"<h2>Votes</h2><ul>{''.join(f'<li><a href=\"vote/{x[0]}\">{e(x[7])}</a> : {x[4]} pour, {x[5]} contre</li>' for x in key)}</ul>" if key else "")
                + '<p><a href="lois">Toutes les lois</a></p>')
        jl = [breadcrumb([("Lois", "lois"), (s["titre"], f"loi/{s['slug']}")])]
        if s["statut"] == "promulguee" and s.get("loi"):
            jl.append({"@context": "https://schema.org", "@type": "Legislation", "name": s["titre"],
                       "legislationIdentifier": f"Loi n° {s['loi']}", "legislationJurisdiction": "FR",
                       "legislationDate": (det.get("promulgation") or {}).get("date"), "url": f"{SITE_URL}/loi/{s['slug']}"})
        prio = "0.8" if s.get("examine") else "0.4"
        P.write(f"loi/{s['slug']}", title, desc, body, s.get("maj") or today, prio, jl, og_type="article")

    # ── Députés
    num_index = {r["num"]: i for i, r in enumerate(chrono)}
    for d in deps:
        g = groupes.get(d["groupe"])
        st = d.get("stats") or {}
        fem = d.get("femme")
        role = ("Députée" if fem else "Député") + ("" if d["actif"] else (" (ancienne)" if fem else " (ancien)"))
        circ = f"{d['circo']}e circonscription · {d.get('departement')}" if d.get("circo") else d.get("departement") or ""
        title = f"{d['prenom']} {d['nom']} : votes et activité" + (f" ({g['sigle']})" if g else "")
        desc = (f"{role} {g['nom'] if g else ''} de la {circ}. Comment vote {d['prenom']} {d['nom']} ? "
                f"Présence aux scrutins {fr(st.get('participation'))} %, vote avec son groupe à {fr(st.get('loyaute'))} %, "
                f"{len((d.get('roles') or {}).get('auteur', []))} textes déposés.")
        try:
            v = json.loads((DATA / "votes" / f"{d['id']}.json").read_text(encoding="utf-8"))["v"]
        except FileNotFoundError:
            v = ""
        lst = []
        for i in range(len(chrono) - 1, -1, -1):
            if i < len(v) and v[i] in POS:
                r = chrono[i]
                if r["kind"] in ("ensemble", "censure", "motion") or r["type"] == "SPS":
                    lst.append(f'<li><a href="vote/{r["num"]}">{e(r["titre"])}</a> : <b>{POS[v[i]]}</b> ({fdate(r["date"])})</li>')
            if len(lst) >= 15:
                break
        auteur = [dossiers[u] for u in (d.get("roles") or {}).get("auteur", []) if u in dossiers][:15]
        body = (f"<h1>{e(d['prenom'])} {e(d['nom'])}</h1><p>{e(role)} de la {e(circ)}" + (f" · {e(g['nom'])}" if g else "") + "</p>"
                f"<p>Présence aux votes : {fr(st.get('participation'))} % · vote comme son groupe : {fr(st.get('loyaute'))} %</p>"
                + (f"<h2>Ses derniers grands votes</h2><ul>{''.join(lst)}</ul>" if lst else "")
                + (f"<h2>Ses textes</h2><ul>{''.join(f'<li>{loi_link(x)}</li>' for x in auteur)}</ul>" if auteur else "")
                + '<p><a href="deputes">Tous les députés</a></p>')
        jl = [breadcrumb([("Députés", "deputes"), (f"{d['prenom']} {d['nom']}", f"depute/{d['slug']}")]),
              {"@context": "https://schema.org", "@type": "Person", "name": f"{d['prenom']} {d['nom']}",
               "jobTitle": role, "memberOf": {"@type": "Organization", "name": g["nom"]} if g else None,
               "image": f"https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/{d['id'][2:]}.jpg",
               "url": f"{SITE_URL}/depute/{d['slug']}"}]
        P.write(f"depute/{d['slug']}", title, desc, body, today, "0.8" if d["actif"] else "0.4", jl, og_type="profile")

    # ── Sénateurs
    for d in sens:
        g = groupes.get(d["groupe"])
        role = "Sénatrice" if d.get("femme") else "Sénateur"
        title = f"{d['prenom']} {d['nom']}, {role.lower()} {d.get('departement') or ''}" + (f" ({g['sigle']})" if g else "")
        desc = f"{role} {('du groupe ' + g['nom']) if g else ''}, {d.get('departement') or ''}. Commission, textes portés et parcours au Sénat."
        rap = [dossiers[u] for u in (d.get("roles") or {}).get("rapporteur", []) if u in dossiers][:15]
        body = (f"<h1>{e(d['prenom'])} {e(d['nom'])}</h1><p>{e(role)} · {e(d.get('departement'))}" + (f" · {e(g['nom'])}" if g else "") + "</p>"
                + (f"<h2>Textes dont il ou elle est rapporteur</h2><ul>{''.join(f'<li>{loi_link(x)}</li>' for x in rap)}</ul>" if rap else "")
                + '<p><a href="senateurs">Tous les sénateurs</a></p>')
        P.write(f"senateur/{d['slug']}", title, desc, body, today, "0.5",
                [breadcrumb([("Sénateurs", "senateurs"), (f"{d['prenom']} {d['nom']}", f"senateur/{d['slug']}")])], og_type="profile")

    # ── Groupes
    for g in G["groupes"]:
        if not g.get("effectif"):
            continue
        chamber = "l'Assemblée nationale" if g["chambre"] == "AN" else "le Sénat"
        title = f"{g['nom']} ({g['sigle']}) : membres et votes"
        desc = (f"Le groupe {g['nom']} à {chamber} : {g['effectif']} membres" + (f", présidé par {g['president']['nom']}" if g.get("president") else "") +
                ". " + (g.get("pitch") or "") + " Membres, positions de vote, alliés et adversaires.")
        pool = deps if g["chambre"] == "AN" else sens
        mem = [p for p in pool if p.get("groupe") == g["id"] and p.get("actif")]
        body = (f"<h1>{e(g['nom'])} ({e(g['sigle'])})</h1><p>{e(g.get('pitch'))}</p><p>{g['effectif']} membres · {e(g.get('bloc'))}</p>"
                f"<h2>Membres</h2><ul>{''.join(f'<li>' + person_link(p, g['chambre']) + '</li>' for p in mem)}</ul>")
        P.write(f"groupe/{g['slug']}", title, desc, body, today, "0.7",
                [breadcrumb([("Assemblée nationale" if g["chambre"] == "AN" else "Sénat", "assemblee" if g["chambre"] == "AN" else "senat"), (g["nom"], f"groupe/{g['slug']}")])])

    # ── Grands votes
    for r in grands:
        try:
            sd = json.loads((DATA / "scrutins" / f"{r['num']}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        res = "adopté" if r["adopte"] else "rejeté"
        d = dossiers.get(r["dossier"]) if r["dossier"] else None
        short = clip(r["titre"], 90)
        title = f"Scrutin n° {r['num']} : {short}"
        desc = (f"{res.capitalize()} le {fdate(r['date'])} par {r['pour']} voix pour et {r['contre']} contre. "
                "Le vote de chaque groupe politique et de chaque député.")
        gs = sorted([x for x in sd["groupes"] if x["g"] in groupes], key=lambda x: groupes[x["g"]]["ordre"])
        table = "".join(f"<tr><td>{e(groupes[x['g']]['sigle'])}</td><td>{POS.get(x['pos'], '—')}</td><td>{len(x['p'])}</td><td>{len(x['c'])}</td><td>{len(x['a'])}</td></tr>" for x in gs)
        body = (f"<h1>{e(r['titre'])}</h1><p><b>{res.capitalize()}</b> · {fdate(r['date'])} · {e(KIND.get(r['kind'], ''))}</p>"
                f"<p>{r['pour']} pour · {r['contre']} contre · {r['abstention']} abstentions</p>"
                + (f"<p>Texte : {loi_link(d)}</p>" if d else "")
                + f"<table><thead><tr><th>Groupe</th><th>Position</th><th>Pour</th><th>Contre</th><th>Abst.</th></tr></thead><tbody>{table}</tbody></table>")
        P.write(f"vote/{r['num']}", title, desc, body, r["date"], "0.6",
                [breadcrumb([("Votes", "votes"), (f"Scrutin n° {r['num']}", f"vote/{r['num']}")])], og_type="article")

    # ── Page 404 (sert aussi de point d'entrée pour les pages non pré-générées)
    shell = P.template.replace('<base href="/">', f'<base href="{BASE}">').replace('<meta name="description"', '<meta name="robots" content="noindex">\n  <meta name="description"', 1)
    (DIST / "404.html").write_text(shell, encoding="utf-8")

    # ── Plan du site et robots.txt
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, lastmod, prio in P.urls:
        loc = SITE_URL + "/" + path if path else SITE_URL + "/"
        sm.append(f"<url><loc>{e(loc)}</loc>" + (f"<lastmod>{lastmod[:10]}</lastmod>" if lastmod else "") + f"<priority>{prio}</priority></url>")
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: {BASE}recherche\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    host = re.sub(r"^https?://", "", SITE_URL).split("/")[0]
    if BASE == "/" and not re.match(r"^(localhost|127\.|\d+\.)", host):
        (DIST / "CNAME").write_text(host + "\n", encoding="utf-8")  # domaine personnalisé GitHub Pages
    print(f"  ✓ {len(P.urls)} pages générées dans {DIST} (base {BASE}, {SITE_URL})")


if __name__ == "__main__":
    main()
