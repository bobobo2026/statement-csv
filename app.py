"""Bank Statement → CSV/Excel MVP. Uploads are processed in memory and never retained on disk."""

from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from parser import parse_statement, transactions_to_csv, transactions_to_xlsx

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB

# --- Lightweight aggregate analytics (no PII, no file contents) ---
_STATS_LOCK = threading.Lock()
_STATS_PATH = Path(os.environ.get("STATS_PATH") or Path(__file__).resolve().parent / "tmp" / "stats.json")
_ALLOWED_EVENTS = frozenset(
    {
        "page_view",
        "file_selected",
        "parse_ok",
        "parse_fail",
        "download_csv",
        "download_xlsx",
        "balance_pass",
        "balance_fail",
        "balance_unknown",
    }
)
_stats: dict[str, int] = {k: 0 for k in _ALLOWED_EVENTS}


def _load_stats() -> None:
    global _stats
    try:
        if _STATS_PATH.is_file():
            data = json.loads(_STATS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                with _STATS_LOCK:
                    for k in _ALLOWED_EVENTS:
                        if isinstance(data.get(k), int) and data[k] >= 0:
                            _stats[k] = data[k]
    except Exception:
        pass


def _persist_stats() -> None:
    try:
        _STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _STATS_LOCK:
            payload = dict(_stats)
        tmp = _STATS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(_STATS_PATH)
    except Exception:
        pass


def bump(event: str, n: int = 1) -> None:
    if event not in _ALLOWED_EVENTS:
        return
    with _STATS_LOCK:
        _stats[event] = _stats.get(event, 0) + n
    _persist_stats()


_load_stats()


def paddle_config() -> dict:
    """Public Paddle.js config from env. Checkout is intentionally off in marketing phase."""
    env = (os.environ.get("PADDLE_ENV") or "sandbox").strip().lower()
    if env not in ("sandbox", "production"):
        env = "sandbox"
    token = (os.environ.get("PADDLE_CLIENT_TOKEN") or "").strip()
    prices = {
        "starter": (os.environ.get("PADDLE_PRICE_STARTER") or "").strip(),
        "pro": (os.environ.get("PADDLE_PRICE_PRO") or "").strip(),
        "bulk": (os.environ.get("PADDLE_PRICE_BULK") or "").strip(),
    }
    # Force checkout off until user re-enables billing (marketing free phase).
    checkout_enabled = (os.environ.get("PADDLE_CHECKOUT_ENABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    ready = bool(checkout_enabled) and bool(token) and any(prices.values())
    return {
        "env": env,
        "client_token": token if checkout_enabled else "",
        "prices": prices if checkout_enabled else {"starter": "", "pro": "", "bulk": ""},
        "ready": ready,
        "checkout_enabled": checkout_enabled,
    }


@app.after_request
def no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.get("/")
def index():
    bump("page_view")
    return render_template("index.html")


@app.get("/pricing")
def pricing():
    bump("page_view")
    return render_template("pricing.html", paddle=paddle_config())


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


@app.get("/api/config")
def api_config():
    cfg = paddle_config()
    return jsonify(
        {
            "paddle": {
                "env": cfg["env"],
                "ready": cfg["ready"],
                "checkout_enabled": cfg["checkout_enabled"],
                "client_token_set": bool(cfg["client_token"]),
                "prices_set": {k: bool(v) for k, v in cfg["prices"].items()},
            },
            "privacy": "uploads_not_retained",
            "billing": "paused_free_tool",
        }
    )


@app.post("/api/event")
def api_event():
    """Client-side funnel pings. Aggregate counts only — no filenames or PDF data."""
    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    if event not in _ALLOWED_EVENTS:
        return jsonify({"ok": False, "message": "unknown event"}), 400
    # page_view already counted on HTML routes; allow client duplicates only for UI events
    bump(event)
    return jsonify({"ok": True})


@app.get("/api/stats")
def api_stats():
    """Public aggregate counters for the free funnel dashboard."""
    with _STATS_LOCK:
        out = dict(_stats)
    return jsonify({"ok": True, "counters": out, "note": "aggregates only; no PII"})


@app.post("/api/parse")
def api_parse():
    if "file" not in request.files:
        bump("parse_fail")
        return jsonify({"ok": False, "message": "No file uploaded."}), 400
    f = request.files["file"]
    if not f.filename:
        bump("parse_fail")
        return jsonify({"ok": False, "message": "Empty filename."}), 400
    if not f.filename.lower().endswith(".pdf"):
        bump("parse_fail")
        return jsonify({"ok": False, "message": "Only PDF files are accepted."}), 400

    pdf_bytes = f.read()
    result = parse_statement(pdf_bytes)
    del pdf_bytes  # drop as soon as parsing finishes

    if result.get("error") == "no_text_layer" or (not result.get("ok") and not result.get("transactions")):
        bump("parse_fail")
    else:
        bump("parse_ok")
        bc = result.get("balance_check") or {}
        passed = bc.get("passed")
        if passed is True:
            bump("balance_pass")
        elif passed is False:
            bump("balance_fail")
        else:
            bump("balance_unknown")

    return jsonify(result)


@app.post("/api/download/csv")
def download_csv():
    data = request.get_json(silent=True) or {}
    txs = data.get("transactions") or []
    csv_text = transactions_to_csv(txs)
    buf = io.BytesIO(csv_text.encode("utf-8"))
    bump("download_csv")
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name="transactions.csv",
    )


@app.post("/api/download/xlsx")
def download_xlsx():
    data = request.get_json(silent=True) or {}
    txs = data.get("transactions") or []
    xlsx_bytes = transactions_to_xlsx(txs)
    buf = io.BytesIO(xlsx_bytes)
    bump("download_xlsx")
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="transactions.xlsx",
    )


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "privacy": "uploads_not_retained",
            "billing": "paused_free_tool",
            "paddle_ready": paddle_config()["ready"],
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Bank Statement CSV — http://{host}:{port}")
    print("Privacy: uploaded PDFs are parsed in memory and not saved to disk.")
    print("Billing: free tool phase — Paddle checkout disabled unless PADDLE_CHECKOUT_ENABLED=1")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
