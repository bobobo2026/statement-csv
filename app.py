"""Bank Statement → CSV/Excel MVP. Uploads are processed in memory and never retained on disk."""

from __future__ import annotations

import io
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from parser import parse_statement, transactions_to_csv, transactions_to_xlsx

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB


def paddle_config() -> dict:
    """Public Paddle.js config from env. Empty token → checkout buttons stay disabled."""
    env = (os.environ.get("PADDLE_ENV") or "sandbox").strip().lower()
    if env not in ("sandbox", "production"):
        env = "sandbox"
    token = (os.environ.get("PADDLE_CLIENT_TOKEN") or "").strip()
    prices = {
        "starter": (os.environ.get("PADDLE_PRICE_STARTER") or "").strip(),
        "pro": (os.environ.get("PADDLE_PRICE_PRO") or "").strip(),
        "bulk": (os.environ.get("PADDLE_PRICE_BULK") or "").strip(),
    }
    ready = bool(token) and any(prices.values())
    return {
        "env": env,
        "client_token": token,
        "prices": prices,
        "ready": ready,
    }


@app.after_request
def no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/pricing")
def pricing():
    return render_template("pricing.html", paddle=paddle_config())


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


@app.get("/api/config")
def api_config():
    cfg = paddle_config()
    # Never invent tokens; only expose what env provides (client token is public by design).
    return jsonify(
        {
            "paddle": {
                "env": cfg["env"],
                "ready": cfg["ready"],
                "client_token_set": bool(cfg["client_token"]),
                "prices_set": {k: bool(v) for k, v in cfg["prices"].items()},
            },
            "privacy": "uploads_not_retained",
        }
    )


@app.post("/api/parse")
def api_parse():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "No file uploaded."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "message": "Empty filename."}), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "message": "Only PDF files are accepted."}), 400

    pdf_bytes = f.read()
    result = parse_statement(pdf_bytes)
    del pdf_bytes  # drop as soon as parsing finishes
    return jsonify(result)


@app.post("/api/download/csv")
def download_csv():
    data = request.get_json(silent=True) or {}
    txs = data.get("transactions") or []
    csv_text = transactions_to_csv(txs)
    buf = io.BytesIO(csv_text.encode("utf-8"))
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
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="transactions.xlsx",
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "privacy": "uploads_not_retained", "paddle_ready": paddle_config()["ready"]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Bank Statement CSV — http://{host}:{port}")
    print("Privacy: uploaded PDFs are parsed in memory and not saved to disk.")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
