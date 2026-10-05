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
    :root { font-family: Inter, ui-sans-serif, system-ui, sans-serif; color-scheme: light dark; }
    * { box-sizing: border-box; }
    body { max-width: 980px; margin: 0 auto; padding: 48px 20px 72px; }
    h1 { margin: 0 0 8px; font-size: clamp(2rem, 6vw, 3.6rem); letter-spacing: -.045em; }
    h2 { margin: 0 0 12px; font-size: 1rem; }
    p { line-height: 1.55; }
    textarea { width: 100%; min-height: 120px; resize: vertical; padding: 14px; border-radius: 12px; border: 1px solid #7776; font: inherit; }
    button { margin-top: 12px; padding: 11px 16px; border: 0; border-radius: 10px; font: inherit; font-weight: 700; cursor: pointer; }
    .muted { opacity: .68; }
    .grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); gap: 16px; margin-top: 22px; }
    .card { border: 1px solid #7775; border-radius: 14px; padding: 18px; min-width: 0; }
    .status { display: inline-block; padding: 5px 9px; border: 1px solid #7776; border-radius: 999px; font-size: .82rem; font-weight: 700; }
    .quote { border-left: 3px solid currentColor; padding-left: 12px; margin: 12px 0; }
    .mono { font: .82rem ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    #result[hidden] { display: none; }
    #answer { font-size: 1.08rem; }
    @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="status">Hack Apertus · Track 2B</div>
    <h1>Apertus Evidence Ledger</h1>
    <p class="muted">Local retrieval · Apertus reasoning · exact-quote verification · auditable evidence hashes.</p>
  </header>

  <main>
    <label for="q"><strong>Question</strong></label>
    <textarea id="q" placeholder="Ask a question grounded in your indexed evidence"></textarea>
    <button id="ask">Ask Apertus</button>

    <section id="result" hidden>
      <div class="grid">
        <article class="card">
          <div class="row">
            <h2>Verified answer</h2>
            <span id="status" class="status"></span>
          </div>
          <p id="answer"></p>
          <div id="citations"></div>
        </article>
        <aside class="card">
          <h2>Evidence ledger</h2>
          <p class="muted">Deterministic provenance emitted after verification.</p>
          <div id="ledger" class="mono"></div>
        </aside>
      </div>
    </section>
    <p id="message" class="muted">Ready. Documents and model traffic stay on the configured local infrastructure.</p>
  </main>

  <script>
    const result = document.getElementById("result");
    const message = document.getElementById("message");
    const answer = document.getElementById("answer");
    const status = document.getElementById("status");
    const citations = document.getElementById("citations");
    const ledger = document.getElementById("ledger");

    const addText = (parent, tag, text, cls) => {
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      el.textContent = text;
      parent.appendChild(el);
      return el;
    };

    document.getElementById("ask").onclick = async () => {
      const question = document.getElementById("q").value.trim();
      if (!question) return;
      result.hidden = true;
      message.textContent = "Running local retrieval and Apertus verification…";
      try {
        const r = await fetch("/api/ask", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({question})
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "request failed");

        answer.textContent = data.answer;
        status.textContent = data.abstain ? "ABSTAINED" : "VERIFIED";
        citations.replaceChildren();
        ledger.replaceChildren();

        if (data.citations.length) {
          addText(citations, "h2", "Verified citations");
          for (const citation of data.citations) {
            const block = document.createElement("div");
            block.className = "quote";
            addText(block, "div", citation.quote);
            addText(block, "div", "chunk_id=" + citation.chunk_id, "mono muted");
            citations.appendChild(block);
          }
        }

        const l = data.ledger;
        addText(ledger, "div", "model: " + l.model);
        addText(ledger, "div", "support gate: " + l.support_gate_supported);
        addText(ledger, "div", "retrieved chunks: " + l.retrieved.length);
        addText(ledger, "div", "evidence sha256:");
        addText(ledger, "div", l.evidence_digest_sha256, "mono");
        addText(ledger, "div", "model trace sha256:");
        addText(ledger, "div", l.model_output_digest_sha256, "mono");

        result.hidden = false;
        message.textContent = data.abstain
          ? "The evidence gate declined to answer without sufficient support."
          : "Answer accepted only after deterministic citation verification.";
      } catch (e) {
        message.textContent = "Request failed: " + e.message;
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
