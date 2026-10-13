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
        "upload_received",
        "parse_ok",
        "parse_fail",
        "download_csv",
        "download_xlsx",
        "balance_pass",
        "balance_fail",
        "balance_unknown",
    }
)
def _empty_stats() -> dict[str, int]:
    return {k: 0 for k in _ALLOWED_EVENTS}


def _read_stats_unlocked(fh) -> dict[str, int]:
    """Read counters from an open file handle (caller holds lock)."""
    out = _empty_stats()
    try:
        fh.seek(0)
        raw = fh.read()
        if not raw:
            return out
        data = json.loads(raw)
        if isinstance(data, dict):
            for k in _ALLOWED_EVENTS:
                if isinstance(data.get(k), int) and data[k] >= 0:
                    out[k] = data[k]
    except Exception:
        pass
    return out


def _write_stats_unlocked(fh, payload: dict[str, int]) -> None:
    fh.seek(0)
    fh.truncate()
    fh.write(json.dumps(payload, indent=2))
    fh.flush()


def _with_stats_file(write: bool = False):
    """Context manager: flock the stats file so multi-worker gunicorn stays consistent."""
    import fcntl
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        _STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        # a+ so file exists; binary-ish text mode for flock on POSIX
        fh = open(_STATS_PATH, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            yield fh
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            fh.close()

    return _cm()


def bump(event: str, n: int = 1) -> None:
    if event not in _ALLOWED_EVENTS:
        return
    with _STATS_LOCK:
        try:
            with _with_stats_file(write=True) as fh:
                payload = _read_stats_unlocked(fh)
                payload[event] = payload.get(event, 0) + n
                _write_stats_unlocked(fh, payload)
        except Exception:
            pass


def read_stats() -> dict[str, int]:
    with _STATS_LOCK:
        try:
            with _with_stats_file(write=False) as fh:
                return _read_stats_unlocked(fh)
        except Exception:
            return _empty_stats()


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


@app.get("/guides")
def guides_index():
    bump("page_view")
    return render_template("guides/index.html")


@app.get("/guides/bank-statement-to-csv")
def guide_bank_statement_to_csv():
    bump("page_view")
    return render_template("guides/bank-statement-to-csv.html")


@app.get("/guides/why-subscription-converters-frustrate-bookkeepers")
def guide_subscription_frustration():
    bump("page_view")
    return render_template("guides/why-subscription-converters-frustrate-bookkeepers.html")


@app.get("/guides/verify-bank-statement-balance")
def guide_verify_balance():
    return render_template("guides/verify-bank-statement-balance.html")


@app.get("/guides/bank-statement-pdf-to-excel-quickbooks")
def guide_quickbooks_excel():
    bump("page_view")
    return render_template("guides/bank-statement-pdf-to-excel-quickbooks.html")


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


@app.post("/api/e")
@app.post("/api/event")  # legacy path (kept for cached JS)
def api_event():
    """Client-side funnel pings. Aggregate counts only — no filenames or PDF data."""
    data = request.get_json(silent=True, force=True) or {}
    event = (data.get("event") or "").strip()
    if event not in _ALLOWED_EVENTS:
        return jsonify({"ok": False, "message": "unknown event"}), 400
    # page_view already counted on HTML routes; allow client duplicates only for UI events
    bump(event)
    return jsonify({"ok": True})


@app.get("/api/stats")
def api_stats():
    """Public aggregate counters for the free funnel dashboard."""
    return jsonify({"ok": True, "counters": read_stats(), "note": "aggregates only; no PII"})


@app.post("/api/parse")
def api_parse():
    # Server-side counter: independent of client JS / ad blockers.
    bump("upload_received")
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


@app.get("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "\n"
        "Sitemap: https://statementcsv.spacebit.qzz.io/sitemap.xml\n"
    )
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/sitemap.xml")
def sitemap_xml():
    # Keep in sync with public HTML routes.
    urls = [
        ("https://statementcsv.spacebit.qzz.io/", "1.0", "weekly"),
        ("https://statementcsv.spacebit.qzz.io/pricing", "0.6", "monthly"),
        ("https://statementcsv.spacebit.qzz.io/privacy", "0.4", "yearly"),
        ("https://statementcsv.spacebit.qzz.io/guides", "0.8", "weekly"),
        ("https://statementcsv.spacebit.qzz.io/guides/bank-statement-to-csv", "0.9", "weekly"),
        ("https://statementcsv.spacebit.qzz.io/guides/verify-bank-statement-balance", "0.8", "monthly"),
        (
            "https://statementcsv.spacebit.qzz.io/guides/why-subscription-converters-frustrate-bookkeepers",
            "0.7",
            "monthly",
        ),
        (
            "https://statementcsv.spacebit.qzz.io/guides/bank-statement-pdf-to-excel-quickbooks",
            "0.9",
            "weekly",
        ),
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, priority, changefreq in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append(f"    <changefreq>{changefreq}</changefreq>")
        parts.append(f"    <priority>{priority}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    return "\n".join(parts), 200, {"Content-Type": "application/xml; charset=utf-8"}


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
