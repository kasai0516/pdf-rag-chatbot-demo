"""A tiny local web chat (standard library only). Open http://127.0.0.1:8000"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .answer import answer
from .index import BM25Index

MAX_BODY = 10_000  # bytes
MAX_QUESTION = 500  # characters

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PDF Q&amp;A demo</title>
<style>
body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#0a2540}
h1{font-size:1.4rem}form{display:flex;gap:8px}input{flex:1;padding:10px;font-size:1rem;border:1px solid #cfd7df;border-radius:8px}
button{padding:10px 16px;border:0;border-radius:8px;background:#635bff;color:#fff;font-size:1rem;cursor:pointer}
.msg{margin:16px 0;padding:14px;border-radius:10px;background:#f6f9fc;white-space:pre-wrap}
.q{background:#f2f1ff}.src{font-size:.85rem;color:#425466;margin-top:8px}
</style></head><body>
<h1>Ask the documents</h1><p>Answers come only from the indexed PDFs, with the page they came from.</p>
<form id="f"><input id="q" placeholder="e.g. What is the refund period for annual plans?" autofocus><button>Ask</button></form>
<div id="log"></div>
<script>
const log=document.getElementById('log');
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const q=document.getElementById('q').value.trim();if(!q)return;
const qa=document.createElement('div');qa.className='msg q';qa.textContent=q;log.prepend(qa);
const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
const d=await r.json();const a=document.createElement('div');a.className='msg';a.textContent=d.answer||('Error: '+d.error);
if(d.sources&&d.sources.length){const s=document.createElement('div');s.className='src';s.textContent='Sources: '+d.sources.join(', ');a.appendChild(s);}
qa.after(a);};
</script></body></html>"""


def serve(index: BM25Index, host: str = "127.0.0.1", port: int = 8000) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")

        def _error(self, code: int, message: str) -> None:
            self._send(code, json.dumps({"error": message}).encode(), "application/json")

        def do_POST(self):  # noqa: N802
            if self.path != "/api/ask":
                return self._error(404, "not found")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._error(400, "invalid Content-Length")
            if length < 0:
                return self._error(400, "invalid Content-Length")
            if length > MAX_BODY:
                return self._error(413, "request too large")
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError, RecursionError):  # bad JSON, huge ints, deep nesting
                return self._error(400, "body must be JSON")
            question = payload.get("question") if isinstance(payload, dict) else None
            if not isinstance(question, str) or not question.strip():
                return self._error(400, "'question' must be a non-empty string")
            if len(question) > MAX_QUESTION:
                return self._error(400, f"question longer than {MAX_QUESTION} characters")
            try:
                result = answer(index, question.strip())
            except Exception as exc:  # e.g. the optional Claude call failed
                return self._error(502, f"could not answer: {type(exc).__name__}")
            if result.mode == "claude":  # Claude cites passages as [1], [2] ...
                sources = [f"[{i}] {p.cite}" for i, p in enumerate(result.sources, start=1)]
            else:
                sources = [p.cite for p in result.sources]
            body = json.dumps({"answer": result.text, "refused": result.refused, "sources": sources}).encode()
            self._send(200, body, "application/json")

        def log_message(self, *args):  # keep the console quiet
            pass

    print(f"Open http://{host}:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
