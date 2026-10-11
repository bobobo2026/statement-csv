"""Generate synthetic text-layer bank statement PDFs for local testing."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "samples"


def draw_header(c: canvas.Canvas, title: str, opening: str, period: str):
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, title)
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, f"Statement period: {period}")
    c.drawString(50, 715, f"Opening balance: {opening}")
    c.drawString(50, 695, "Date       Description                          Withdrawal    Deposit     Balance")
    c.line(50, 690, 560, 690)


def sample_us_checking():
    path = OUT / "sample_us_checking.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    draw_header(c, "Demo National Bank — Checking ****4217", "$1,250.00", "2025-01-01 to 2025-01-31")
    rows = [
        ("01/03/2025", "ACH PAYROLL ACME CORP", "", "3200.00", "4450.00"),
        ("01/05/2025", "POS COFFEE ROASTERS", "6.50", "", "4443.50"),
        ("01/08/2025", "RENT ACH LANDLORD LLC", "1800.00", "", "2643.50"),
        ("01/12/2025", "TRANSFER FROM SAVINGS", "", "500.00", "3143.50"),
        ("01/15/2025", "UTILITIES ELECTRIC CO", "124.30", "", "3019.20"),
        ("01/18/2025", "POS GROCERY MARKET", "87.45", "", "2931.75"),
        ("01/22/2025", "CLIENT WIRE INVOICE 1042", "", "950.00", "3881.75"),
        ("01/28/2025", "ATM WITHDRAWAL", "200.00", "", "3681.75"),
    ]
    y = 670
    for r in rows:
        c.setFont("Courier", 9)
        line = f"{r[0]:<11}{r[1]:<38}{r[2]:>10}{r[3]:>12}{r[4]:>12}"
        c.drawString(50, y, line)
        y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 10, "Closing balance: $3,681.75")
    c.drawString(50, y - 26, "Total deposits: $4,650.00    Total withdrawals: $2,218.25")
    c.showPage()
    c.save()
    return path


def sample_uk_current():
    path = OUT / "sample_uk_current.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Demo High Street Bank — Current Account")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Statement period: 01/02/2025 - 28/02/2025")
    c.drawString(50, 715, "Opening balance: £820.00")
    c.drawString(50, 695, "Date         Description                       Money out   Money in    Balance")
    c.line(50, 690, 560, 690)
    rows = [
        ("03/02/2025", "SALARY ACME UK LTD", "", "2100.00", "2920.00"),
        ("05/02/2025", "TESCO STORES 3847", "54.20", "", "2865.80"),
        ("10/02/2025", "TRANSPORT FOR LONDON", "80.00", "", "2785.80"),
        ("14/02/2025", "FASTER PAYMENT RENT", "1450.00", "", "1335.80"),
        ("20/02/2025", "CLIENT PAYMENT INV-88", "", "600.00", "1935.80"),
        ("25/02/2025", "NETFLIX.COM", "15.99", "", "1919.81"),
    ]
    y = 670
    for r in rows:
        c.setFont("Courier", 9)
        # Use day-first dates with day > 12 so parser picks DMY
        c.drawString(50, y, f"{r[0]:<12}{r[1]:<36}{r[2]:>10}{r[3]:>10}{r[4]:>10}")
        y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 10, "Closing balance: £1,919.81")
    c.showPage()
    c.save()
    return path


def sample_iso_dated():
    path = OUT / "sample_iso_business.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Demo Business Account — USD")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Opening balance $10,000.00")
    c.drawString(50, 710, "Date         Description                              Amount      Balance")
    rows = [
        ("2025-03-01", "VENDOR PAYMENT AWS", "-420.55", "9579.45"),
        ("2025-03-04", "CUSTOMER STRIPE PAYOUT", "1820.00", "11399.45"),
        ("2025-03-09", "SOFTWARE SUBSCRIPTION", "-49.00", "11350.45"),
        ("2025-03-15", "CONTRACTOR WISE TRANSFER", "-1200.00", "10150.45"),
        ("2025-03-22", "CUSTOMER INVOICE 2201", "2500.00", "12650.45"),
    ]
    y = 690
    for r in rows:
        c.setFont("Courier", 9)
        c.drawString(50, y, f"{r[0]:<12}{r[1]:<40}{r[2]:>10}{r[3]:>12}")
        y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 10, "Closing balance $12,650.45")
    c.showPage()
    c.save()
    return path


def sample_month_name():
    path = OUT / "sample_month_name.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Demo Credit Union")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Opening balance: $500.00")
    rows = [
        ("Mar 02, 2025", "MOBILE DEPOSIT", "", "250.00", "750.00"),
        ("Mar 07, 2025", "POS CAFE", "12.00", "", "738.00"),
        ("Mar 18, 2025", "DIVIDEND INTEREST", "", "1.25", "739.25"),
        ("Mar 25, 2025", "CARD PURCHASE HARDWARE", "89.99", "", "649.26"),
    ]
    y = 700
    c.drawString(50, 715, "Date            Description                     Withdrawal   Deposit    Balance")
    for r in rows:
        c.setFont("Courier", 9)
        c.drawString(50, y, f"{r[0]:<15}{r[1]:<32}{r[2]:>10}{r[3]:>10}{r[4]:>10}")
        y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 10, "Closing balance: $649.26")
    c.showPage()
    c.save()
    return path


def sample_failing_balance():
    """Intentionally inconsistent numbers to verify FAILED balance check UI."""
    path = OUT / "sample_balance_mismatch.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Demo Mismatch Bank")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Opening balance: $100.00")
    c.drawString(50, 710, "01/10/2025  DEPOSIT                         50.00       150.00")
    c.drawString(50, 694, "01/12/2025  PURCHASE                        20.00       130.00")
    # Claim wrong closing on purpose
    c.drawString(50, 670, "Closing balance: $999.00")
    c.showPage()
    c.save()
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [
        sample_us_checking(),
        sample_uk_current(),
        sample_iso_dated(),
        sample_month_name(),
        sample_failing_balance(),
    ]
    # Thin wrappers as additional named samples for the 5–10 testing plan
    extra = [
        ("sample_us_checking_copy2.pdf", paths[0]),
        ("sample_iso_business_copy2.pdf", paths[2]),
    ]
    for name, src in extra:
        dest = OUT / name
        dest.write_bytes(src.read_bytes())
        paths.append(dest)
    print("Wrote:")
    for p in paths:
        print(" ", p)


if __name__ == "__main__":
    main()
