"""
Serveur local qui se comporte comme GitHub Pages : /loi/x sert dist/loi/x.html, et les
adresses inconnues renvoient 404.html (qui lance l'application).

    python pipeline/serve.py [port] [base]     # base : ex. /assemblee-nationale/ pour simuler github.io
"""

import http.server
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

DIST = Path(__file__).resolve().parent.parent / "dist"
BASE = sys.argv[2] if len(sys.argv) > 2 else "/"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if not path.startswith(BASE):
            self.send_error(404)
            return None
        path = "/" + path[len(BASE):]
        self.path = path
        target = (DIST / path.lstrip("/")).resolve()
        if DIST not in target.parents and target != DIST:
            self.send_error(403)
            return None
        if target.is_dir() and (target / "index.html").exists():
            self.path = path.rstrip("/") + "/index.html"
        elif not path.endswith("/") and target.with_suffix(target.suffix + ".html").exists():
            self.path = path + ".html"  # /europe → europe.html même s'il existe un dossier europe/
        elif not target.exists():
            f = open(DIST / "404.html", "rb")
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return f
        return super().send_head()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Site disponible sur http://localhost:{port}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
