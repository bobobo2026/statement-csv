"""Extract transactions from text-layer bank-statement PDFs and run a balance check."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pdfplumber

DATE_PATTERNS = [
    re.compile(r"^(?P<a>\d{1,2})[/-](?P<b>\d{1,2})[/-](?P<y>\d{2,4})\b"),
    re.compile(r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b"),
    re.compile(
        r"^(?P<m>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"[.\s-]+(?P<d>\d{1,2})[,.\s-]+(?P<y>\d{2,4})\b",
        re.I,
    ),
]

# Require .XX cents. Allow 3200.00 (no commas) OR 3,200.00 (with commas).
MONEY_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
MONEY_TOKEN_RE = re.compile(
    rf"(?:"
    rf"\(\s*[$€£]?\s*{MONEY_NUM}\s*\)|"
    rf"[-+]?[$€£]?\s*{MONEY_NUM}\s*(?:CR|DR)?"
    rf")",
    re.I,
)

HEADER_HINTS = re.compile(
    r"date|description|particulars|details|debit|credit|withdrawal|deposit|"
    r"amount|balance|money\s*out|money\s*in|transaction",
    re.I,
)

SKIP_LINE = re.compile(
    r"^(page\s+\d|statement\s+(period|date)|account\s+(number|name|summary)|"
    r"opening\s+balance|closing\s+balance|total\s+(deposits|withdrawals|credits|debits)|"
    r"brought\s+forward|carried\s+forward|continued|please\s+note|"
    r"customer\s+service|www\.|http|date\s+description)",
    re.I,
)

OPENING_RE = re.compile(
    r"(opening\s+balance|balance\s+brought\s+forward|beginning\s+balance)"
    r"[^\d+\-]*([-+]?\s*[$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
    re.I,
)
CLOSING_RE = re.compile(
    r"(closing\s+balance|balance\s+carried\s+forward|ending\s+balance|"
    r"new\s+balance)"
    r"[^\d+\-]*([-+]?\s*[$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})",
    re.I,
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

TOLERANCE = Decimal("0.01")


@dataclass
class Transaction:
    date: str
    description: str
    deposit: float | None
    withdrawal: float | None
    balance: float | None
    raw: str


def _parse_amount(text: str) -> Decimal | None:
    text = text.strip()
    if not text:
        return None
    neg = False
    if text.startswith("(") and text.endswith(")"):
        neg = True
        text = text[1:-1].strip()
    text_compact = text.replace(" ", "")
    m = re.match(
        r"^([-+])?[$€£]?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(CR|DR)?$",
        text_compact,
        re.I,
    )
    if not m:
        return None
    try:
        val = Decimal(m.group(2).replace(",", ""))
    except InvalidOperation:
        return None
    if m.group(1) == "-" or (m.group(3) or "").upper() == "DR":
        neg = True
    if (m.group(3) or "").upper() == "CR":
        neg = False
    return -val if neg else val


def _normalize_date(raw: str, prefer_dmy: bool = False) -> str | None:
    raw = raw.strip()
    for pat in DATE_PATTERNS:
        m = pat.match(raw)
        if not m:
            continue
        gd = m.groupdict()
        try:
            year = int(gd["y"])
            if year < 100:
                year += 2000 if year < 70 else 1900

            if gd.get("m") and str(gd["m"]).isalpha():
                month = MONTHS[gd["m"][:3].lower()]
                day = int(gd["d"])
                return f"{year:04d}-{month:02d}-{day:02d}"

            if "m" in gd and "d" in gd and "a" not in gd:
                return f"{year:04d}-{int(gd['m']):02d}-{int(gd['d']):02d}"

            first, second = int(gd["a"]), int(gd["b"])
            if first > 12 and second <= 12:
                day, month = first, second
            elif second > 12 and first <= 12:
                month, day = first, second
            else:
                # Ambiguous numeric date: £ statements → DMY, else MDY
                if prefer_dmy:
                    day, month = first, second
                else:
                    month, day = first, second
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, KeyError):
            continue
    return None


def _extract_text(pdf_bytes: bytes) -> tuple[str, int, bool]:
    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")
    full = "\n".join(pages_text)
    return full, page_count, bool(full.strip())


def _find_labeled_balance(text: str, pattern: re.Pattern) -> Decimal | None:
    m = pattern.search(text)
    if not m:
        return None
    return _parse_amount(m.group(2))


def _split_amounts_from_tail(line: str) -> tuple[str, list[Decimal]]:
    amounts: list[Decimal] = []
    rest = line.rstrip()
    for _ in range(4):
        matches = list(MONEY_TOKEN_RE.finditer(rest))
        if not matches:
            break
        m = matches[-1]
        # Must be at end (only trailing whitespace after)
        if rest[m.end() :].strip():
            break
        val = _parse_amount(m.group(0))
        if val is None:
            break
        amounts.insert(0, val)
        rest = rest[: m.start()].rstrip()
    return rest, amounts


def _classify_against_balance(
    prev_balance: Decimal | None,
    amounts: list[Decimal],
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Return (deposit, withdrawal, balance) using running-balance delta when possible."""
    if not amounts:
        return None, None, None

    if len(amounts) == 1:
        only = amounts[0]
        if only < 0:
            return None, abs(only), None
        return only, None, None

    if len(amounts) == 2:
        a, bal = amounts[0], amounts[1]
        if prev_balance is not None:
            if abs(prev_balance + abs(a) - bal) <= TOLERANCE:
                return abs(a), None, bal
            if abs(prev_balance - abs(a) - bal) <= TOLERANCE:
                return None, abs(a), bal
            if abs(prev_balance + a - bal) <= TOLERANCE:
                # signed amount
                if a >= 0:
                    return a, None, bal
                return None, abs(a), bal
        # No previous balance: signed amount heuristic
        if a < 0:
            return None, abs(a), bal
        # Unknown direction without context — leave as deposit candidate;
        # caller may still fail balance check which is correct signal.
        return abs(a), None, bal

    # 3+: treat as debit, credit, balance (empty column often omitted → falls to 2)
    debit, credit, bal = amounts[0], amounts[1], amounts[-1]
    deposit = abs(credit) if credit != 0 else None
    withdrawal = abs(debit) if debit != 0 else None
    if prev_balance is not None and deposit and withdrawal:
        # Both non-zero rare; trust delta
        if abs(prev_balance + deposit - bal) <= TOLERANCE:
            return deposit, None, bal
        if abs(prev_balance - withdrawal - bal) <= TOLERANCE:
            return None, withdrawal, bal
    return deposit, withdrawal, bal


def _parse_lines(lines: list[str], opening: Decimal | None, prefer_dmy: bool = False) -> list[Transaction]:
    txs: list[Transaction] = []
    prev_balance = opening

    for ln in lines:
        if not ln or SKIP_LINE.search(ln):
            continue
        # Skip pure header rows
        if HEADER_HINTS.search(ln) and not MONEY_TOKEN_RE.search(ln):
            continue

        date_str = None
        remainder = ln
        for pat in DATE_PATTERNS:
            m = pat.match(ln)
            if m:
                date_str = _normalize_date(m.group(0), prefer_dmy=prefer_dmy)
                remainder = ln[m.end() :].strip(" -|")
                break
        if not date_str:
            continue

        head, amounts = _split_amounts_from_tail(remainder)
        if not amounts:
            continue

        description = re.sub(r"\s{2,}", " ", head).strip(" -|") or "(no description)"
        # Drop trailing invoice-like bare integers left in description if they are not money
        deposit, withdrawal, balance = _classify_against_balance(prev_balance, amounts)

        # If still ambiguous with 2 positive amounts and no prev, try next-line won't help;
        # attempt: larger number is usually balance
        if (
            deposit is not None
            and withdrawal is None
            and balance is not None
            and prev_balance is None
            and len(amounts) == 2
            and amounts[0] > 0
        ):
            # keep as-is; opening inference may fix subsequent rows
            pass

        tx = Transaction(
            date=date_str,
            description=description,
            deposit=float(deposit) if deposit is not None else None,
            withdrawal=float(withdrawal) if withdrawal is not None else None,
            balance=float(balance) if balance is not None else None,
            raw=ln,
        )
        txs.append(tx)
        if balance is not None:
            prev_balance = balance
        elif prev_balance is not None:
            delta = Decimal("0")
            if deposit:
                delta += deposit
            if withdrawal:
                delta -= withdrawal
            prev_balance = prev_balance + delta

    return txs


def _reclassify_with_opening(txs: list[Transaction], opening: Decimal | None) -> list[Transaction]:
    """Second pass: once opening is known, fix deposit/withdrawal using balance deltas."""
    if not txs:
        return txs
    prev = opening
    fixed: list[Transaction] = []
    for t in txs:
        if t.balance is None or prev is None:
            fixed.append(t)
            if t.balance is not None:
                prev = Decimal(str(t.balance))
            continue
        bal = Decimal(str(t.balance))
        # Collect candidate absolute amounts from original deposit/withdrawal
        candidates: list[Decimal] = []
        if t.deposit is not None:
            candidates.append(Decimal(str(t.deposit)))
        if t.withdrawal is not None:
            candidates.append(Decimal(str(t.withdrawal)))
        # Also parse from raw tail in case first pass mis-split direction only
        _, amounts = _split_amounts_from_tail(re.sub(r"^\S+\s+", "", t.raw, count=1))
        if len(amounts) >= 2:
            candidates = [abs(amounts[0])]
        elif len(amounts) == 1:
            candidates = [abs(amounts[0])]

        deposit = withdrawal = None
        for amt in candidates:
            if abs(prev + amt - bal) <= TOLERANCE:
                deposit = amt
                break
            if abs(prev - amt - bal) <= TOLERANCE:
                withdrawal = amt
                break
        if deposit is None and withdrawal is None:
            # keep original
            fixed.append(t)
        else:
            fixed.append(
                Transaction(
                    date=t.date,
                    description=t.description,
                    deposit=float(deposit) if deposit is not None else None,
                    withdrawal=float(withdrawal) if withdrawal is not None else None,
                    balance=t.balance,
                    raw=t.raw,
                )
            )
        prev = bal
    return fixed


def balance_check(
    opening: Decimal | None,
    closing: Decimal | None,
    txs: list[Transaction],
) -> dict[str, Any]:
    total_deposits = sum((Decimal(str(t.deposit)) for t in txs if t.deposit), Decimal("0"))
    total_withdrawals = sum(
        (Decimal(str(t.withdrawal)) for t in txs if t.withdrawal), Decimal("0")
    )
    if opening is None or closing is None:
        return {
            "passed": None,
            "opening": float(opening) if opening is not None else None,
            "closing": float(closing) if closing is not None else None,
            "total_deposits": float(total_deposits),
            "total_withdrawals": float(total_withdrawals),
            "computed_closing": None,
            "difference": None,
            "message": "Could not determine opening and/or closing balance from the PDF.",
        }
    computed = opening + total_deposits - total_withdrawals
    diff = computed - closing
    passed = abs(diff) <= TOLERANCE
    return {
        "passed": passed,
        "opening": float(opening),
        "closing": float(closing),
        "total_deposits": float(total_deposits),
        "total_withdrawals": float(total_withdrawals),
        "computed_closing": float(computed),
        "difference": float(diff),
        "message": (
            "Balance check PASSED: opening + deposits − withdrawals = closing."
            if passed
            else f"Balance check FAILED: difference {float(diff):.2f} (tolerance ±{TOLERANCE})."
        ),
    }


def parse_statement(pdf_bytes: bytes) -> dict[str, Any]:
    text, page_count, has_text = _extract_text(pdf_bytes)
    if not has_text:
        return {
            "ok": False,
            "error": "no_text_layer",
            "message": (
                "This PDF has no extractable text layer (likely a scan). "
                "OCR for scanned statements is planned for a later version. "
                "Please upload a text-based / digitally generated statement."
            ),
            "page_count": page_count,
            "transactions": [],
            "balance_check": None,
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    opening = _find_labeled_balance(text, OPENING_RE)
    closing = _find_labeled_balance(text, CLOSING_RE)

    prefer_dmy = ("£" in text) or ("Money out" in text) or ("Money in" in text)
    txs = _parse_lines(lines, opening, prefer_dmy=prefer_dmy)
    txs = _reclassify_with_opening(txs, opening)

    # Infer opening/closing from running balances if labels missing
    if opening is None and txs and txs[0].balance is not None:
        first = txs[0]
        delta = Decimal("0")
        if first.deposit:
            delta += Decimal(str(first.deposit))
        if first.withdrawal:
            delta -= Decimal(str(first.withdrawal))
        opening = Decimal(str(first.balance)) - delta
        txs = _reclassify_with_opening(txs, opening)

    if closing is None:
        for t in reversed(txs):
            if t.balance is not None:
                closing = Decimal(str(t.balance))
                break

    check = balance_check(opening, closing, txs)
    return {
        "ok": True,
        "error": None,
        "message": f"Extracted {len(txs)} transaction(s) from {page_count} page(s).",
        "page_count": page_count,
        "transactions": [asdict(t) for t in txs],
        "balance_check": check,
    }


def transactions_to_csv(transactions: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "description", "deposit", "withdrawal", "balance"])
    for t in transactions:
        writer.writerow(
            [
                t.get("date") or "",
                t.get("description") or "",
                t.get("deposit") if t.get("deposit") is not None else "",
                t.get("withdrawal") if t.get("withdrawal") is not None else "",
                t.get("balance") if t.get("balance") is not None else "",
            ]
        )
    return buf.getvalue()


def transactions_to_xlsx(transactions: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    ws.append(["date", "description", "deposit", "withdrawal", "balance"])
    for t in transactions:
        ws.append(
            [
                t.get("date") or "",
                t.get("description") or "",
                t.get("deposit"),
                t.get("withdrawal"),
                t.get("balance"),
            ]
        )
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
