# StatementCSV — Bank statement PDF → CSV / Excel (BOB-25 MVP)

Single-task tool: upload a **text-layer** bank statement PDF, preview transactions, download CSV/Excel, and run a balance check:

`opening + deposits − withdrawals = closing`

## Privacy

- Uploaded PDFs are read **in memory only** and are **not written to disk**.
- Download endpoints rebuild files from the JSON already in your browser; the original PDF is not stored.
- No accounts / no database in this MVP.

## Stack

- Python 3 + Flask
- `pdfplumber` (text extraction)
- `openpyxl` (Excel export)
- Vanilla HTML/CSS/JS UI (English)

## Run locally

```bash
cd /workspace/bob25/bank-statement-csv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_samples.py   # optional synthetic PDFs
python app.py                        # http://127.0.0.1:8765
```

Health check: `curl http://127.0.0.1:8765/health`

## What works

- Text-layer PDF upload → transaction table preview
- Balance check pass/fail with opening, deposits, withdrawals, closing, difference
- Download CSV and Excel
- Pricing page **copy scaffold** (Paddle buttons disabled — no live payment)
- Synthetic samples under `samples/` for local testing

## Stubbed / later

- **Scanned / image-only PDFs (OCR)** — detected and rejected with a clear message; OCR not implemented
- **Page-credit metering after purchase** — checkout UI wired; credits ledger not built yet
- **Per-bank layout templates** — generic heuristics; odd bank formats may need cleanup in Excel
- **Paid ads** — not started (no ad spend without explicit ask)

## Sample testing plan (5–10 statements)

Use the generated files in `samples/` first, then real PDFs you own:

| # | File | Expect |
|---|------|--------|
| 1 | `sample_us_checking.pdf` | 8 txs, balance **PASS** |
| 2 | `sample_uk_current.pdf` | 6 txs, balance **PASS**, DMY dates |
| 3 | `sample_iso_business.pdf` | 5 txs, signed amounts, **PASS** |
| 4 | `sample_month_name.pdf` | 4 txs (`Mar 02, 2025`), **PASS** |
| 5 | `sample_balance_mismatch.pdf` | 2 txs, balance **FAIL** (bad closing on purpose) |
| 6–7 | `*_copy2.pdf` | Same as originals (repeatability) |
| 8–10 | Your own text-layer statements (Chase/BoA/Monzo/etc.) | Record pass/fail + bank name; do **not** commit real statements |

Quick CLI check:

```bash
source .venv/bin/activate
python -c "from pathlib import Path; from parser import parse_statement; \
print(parse_statement(Path('samples/sample_us_checking.pdf').read_bytes())['balance_check'])"
```

## Pricing intent (not live)

Page packs (no subscription), Paddle as Merchant of Record for mainland CN individuals — see project notes. Placeholder packs on `/pricing`: $9/100 · $29/400 · $79/1500 pages.

## Project path

`/workspace/bob25/bank-statement-csv/`


## Deploy (public HTTPS)

See [DEPLOY.md](DEPLOY.md). Quick path:

```bash
bash scripts/deploy-tunnel.sh
cat tmp/live-url.txt
```

Paddle seller setup (you must do KYC): [PADDLE_SETUP.md](PADDLE_SETUP.md)
