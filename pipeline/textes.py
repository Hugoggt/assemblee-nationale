"""
Ajoute à chaque loi l'exposé des motifs de son texte initial (la présentation écrite par ses auteurs)
et les liens vers les documents officiels.

Le texte intégral n'est pas dans les données ouvertes JSON : on le lit dans la version HTML publiée
par l'Assemblée (https://www.assemblee-nationale.fr/dyn/opendata/<identifiant>.html).
Les textes déposés au Sénat n'y sont pas : la fiche renvoie alors vers senat.fr.

À lancer après pipeline/build.py. Les extraits sont mis en cache dans data/cache/exposes.json.

    python -X utf8 pipeline/textes.py            # lit les textes manquants (≈ 1 par seconde)
    python -X utf8 pipeline/textes.py --offline  # n'utilise que le cache
"""

import argparse
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "data" / "cache" / "exposes.json"
AN_DOC = "https://www.assemblee-nationale.fr/dyn/opendata/{}.html"
UA = {"User-Agent": "hemicycles.fr (site independant, contact@hemicycles.fr)"}
MAX_CHARS = 6000  # au-delà, on renvoie vers le texte officiel

_lock = threading.Lock()
_next = [0.0]


def throttle(interval=0.4):
    with _lock:
        wait = _next[0] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _next[0] = max(_next[0], time.monotonic()) + interval


def fetch(uid):
    for k in range(4):
        throttle()
        try:
            req = urllib.request.Request(AN_DOC.format(uid), headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (k + 1))
        except Exception:  # noqa: BLE001
            time.sleep(5 * (k + 1))
    raise RuntimeError("injoignable")


END = re.compile(r"^(projet de loi|proposition de loi|proposition de résolution|article (1er|premier|unique|1)\b|"
                 r"le premier ministre|décret de présentation|texte de la commission|étude d.impact)", re.I)
NOISE = re.compile(r"^(mesdames,? messieurs,?|– ?\d+ ?–|\d+)$", re.I)


def paragraphs(page):
    page = re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", page)
    out = []
    for m in re.finditer(r"(?is)<(p|h[1-6]|li)\b[^>]*>(.*?)</\1>", page):
        t = re.sub(r"(?s)<sup\b.*?</sup>", "", m[2])
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        t = re.sub(r"\(\s*\[\d+\]\s*\)|\[\d+\]", "", t)
        t = re.sub(r"\s+", " ", t.replace(" ", " ")).strip()
        if t:
            out.append(t)
    return out


def expose(page):
    """Paragraphes de l'exposé des motifs, sans formule d'adresse ni texte de loi."""
    ps = paragraphs(page)
    start = next((i for i, p in enumerate(ps) if re.match(r"^expos[ée] (des|général des) motifs", p, re.I)), None)
    if start is None:
        return None
    out, n = [], 0
    for p in ps[start + 1:]:
        if END.match(p) and out:
            break
        if NOISE.match(p) or len(p) < 3:
            continue
        out.append(p)
        n += len(p)
        if n > MAX_CHARS:
            break
    return out or None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max", type=int, default=400, help="textes lus au plus par passage (le reste au suivant)")
    args = ap.parse_args(argv)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    index = json.loads((DATA / "dossiers.json").read_text(encoding="utf-8"))
    targets, prio = {}, {}
    for s in index["dossiers"]:
        if s["cat"] != "loi":
            continue
        p = DATA / "dossiers" / f"{s['uid']}.json"
        if not p.exists():
            continue
        det = json.loads(p.read_text(encoding="utf-8"))
        first = next((d for d in det.get("documents", []) if d.get("an") and d["kind"] == "depot"), None)
        if first:
            targets[s["uid"]] = first["uid"]
            # d'abord les lois débattues, puis les plus récentes
            prio[first["uid"]] = (not s.get("examine"), s["statut"] != "promulguee", -(int((s.get("maj") or "0").replace("-", "")[:8] or 0)))

    todo = [] if args.offline else sorted({u for u in targets.values() if u not in cache}, key=lambda u: prio[u])
    reste = max(0, len(todo) - args.max)
    todo = todo[:args.max]
    print(f"  exposés des motifs : {len(targets)} lois, {len(todo)} textes à lire" + (f" ({reste} au prochain passage)" if reste else ""))

    def one(uid):
        try:
            page = fetch(uid)
        except Exception:  # noqa: BLE001
            return uid, "erreur"
        return uid, {"p": expose(page) if page else None, "vu": date.today().isoformat()}

    done = 0
    with ThreadPoolExecutor(4) as ex:
        for uid, val in (f.result() for f in as_completed([ex.submit(one, u) for u in todo])):
            if val != "erreur":
                cache[uid] = val
            done += 1
            if done % 100 == 0:
                print(f"    {done}/{len(todo)}")
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    n = 0
    for dossier, doc in targets.items():
        ps = (cache.get(doc) or {}).get("p")
        p = DATA / "dossiers" / f"{dossier}.json"
        det = json.loads(p.read_text(encoding="utf-8"))
        det["expose"] = {"doc": doc, "p": ps} if ps else None
        p.write_text(json.dumps(det, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n += bool(ps)
    print(f"  ✓ exposé des motifs disponible pour {n} lois")


if __name__ == "__main__":
    sys.exit(main())
