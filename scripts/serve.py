"""Serve site/ for local viewing, telling the browser not to cache, so edits show on reload."""

import functools
import http.server
import sys
from pathlib import Path


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8737
site = Path(__file__).resolve().parents[1] / "site"
http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(NoCache, directory=site)).serve_forever()
