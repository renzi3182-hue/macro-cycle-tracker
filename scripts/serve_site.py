"""Anteprima locale del sito statico (public/): come su Vercel, un percorso senza file (/paese, /asset...) risponde con
index.html. Prima: python -m src.scheduler.export_site. Uso (da code/macro-cycle-tracker): python scripts/serve_site.py [porta]."""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"


class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        if not (PUBLIC / self.path.split("?")[0].lstrip("/")).exists():
            self.path = "/index.html"
        return super().send_head()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8610
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(PUBLIC))).serve_forever()
