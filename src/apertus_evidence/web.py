from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .model import ApertusClient, ModelError
from .service import EvidenceService, EvidenceVerificationError
from .store import EvidenceStore

MAX_BODY_BYTES = 32_768

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Apertus Evidence Ledger</title>
  <style>
    :root { font-family: system-ui, sans-serif; color-scheme: light dark; }
    body { max-width: 900px; margin: 3rem auto; padding: 0 1rem; }
    textarea { width: 100%; min-height: 7rem; box-sizing: border-box; }
    button { margin-top: .75rem; padding: .65rem 1rem; cursor: pointer; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 1rem; border: 1px solid #7775; border-radius: .5rem; }
    .muted { opacity: .72; }
  </style>
</head>
<body>
  <h1>Apertus Evidence Ledger</h1>
  <p class="muted">Local retrieval, Apertus synthesis, exact-quote citation verification.</p>
  <textarea id="q" placeholder="Ask a question grounded in your indexed evidence"></textarea>
  <br><button id="ask">Ask Apertus</button>
  <pre id="out">Ready.</pre>
  <script>
    const out = document.getElementById("out");
    document.getElementById("ask").onclick = async () => {
      const question = document.getElementById("q").value.trim();
      if (!question) return;
      out.textContent = "Running…";
      try {
        const r = await fetch("/api/ask", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({question})
        });
        const data = await r.json();
        out.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        out.textContent = "Request failed: " + e;
      }
    };
  </script>
</body>
</html>
"""


class EvidenceRequestHandler(BaseHTTPRequestHandler):
    server_version = "ApertusEvidence/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_bytes(HTTPStatus.OK, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ask":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid content length"})
            return

        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid request size"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = payload.get("question")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
            return

        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "question must be 1-4000 characters"})
            return

        db_path = os.getenv("APERTUS_EVIDENCE_DB", "evidence.db")
        client = ApertusClient(
            base_url=os.getenv("APERTUS_BASE_URL", "http://localhost:8000/v1"),
            model=os.getenv("APERTUS_MODEL", "swiss-ai/Apertus-v1.5-8B"),
            api_key=os.getenv("APERTUS_API_KEY"),
        )

        try:
            with EvidenceStore(db_path) as store:
                result = EvidenceService(store, client).answer(question.strip())
            self._send_json(
                HTTPStatus.OK,
                {
                    "answer": result.answer,
                    "abstain": result.abstain,
                    "citations": list(result.citations),
                    "ledger": result.ledger,
                },
            )
        except (ModelError, EvidenceVerificationError) as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        self._send_bytes(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("x-frame-options", "DENY")
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    host = os.getenv("APERTUS_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("APERTUS_WEB_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), EvidenceRequestHandler)
    print(f"Apertus Evidence Ledger UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
