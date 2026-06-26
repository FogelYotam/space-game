import http.server, json
from pathlib import Path

DIR    = Path(r"C:\Users\shlom\OneDrive\Documents\קלוד")
SCORES = DIR / "leaderboard.json"

# Listen only on the loopback interface so the leaderboard server is reachable
# from this machine alone, never from other devices on the LAN/Wi-Fi.
HOST = "127.0.0.1"
PORT = 9090

# Reject oversized score uploads early (the leaderboard is a small JSON array).
MAX_BODY_BYTES = 256 * 1024

# Only allow the browser pages we actually serve to call the API. A wildcard
# ("*") would let any website you visit POST to this local server.
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIR), **kw)

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/api/scores":
            data = SCORES.read_bytes() if SCORES.exists() else b"[]"
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/scores":
            self.send_response(404); self.end_headers()
            return

        # CORS response headers only stop a foreign site from *reading* the
        # reply — the write would still execute. So reject the write outright
        # when an Origin is present and not one of ours. A same-origin request
        # from game.html sends a matching Origin (or none for some clients).
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            self.send_response(403); self.end_headers()
            return

        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self.send_response(400); self.end_headers()
            return
        if n <= 0 or n > MAX_BODY_BYTES:
            self.send_response(413); self.end_headers()
            return

        body = self.rfile.read(n)
        try:
            parsed = json.loads(body)
            # The leaderboard is an array of score entries — reject anything else
            # so a malformed or hostile payload can't replace the file shape.
            if not isinstance(parsed, list):
                raise ValueError("leaderboard must be a JSON array")
            SCORES.write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except (ValueError, OSError):
            self.send_response(400); self.end_headers()

    def log_message(self, *a): pass


http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
