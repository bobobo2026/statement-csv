#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import parse_statement

ROOT = Path(__file__).resolve().parents[1] / "samples"
expect_pass = {
    "sample_us_checking.pdf": True,
    "sample_uk_current.pdf": True,
    "sample_iso_business.pdf": True,
    "sample_month_name.pdf": True,
    "sample_balance_mismatch.pdf": False,
}
failed = 0
for name, should_pass in expect_pass.items():
    data = parse_statement((ROOT / name).read_bytes())
    got = (data.get("balance_check") or {}).get("passed")
    ok = got is should_pass
    print(("OK " if ok else "FAIL"), name, "passed=", got, "expected=", should_pass)
    failed += not ok
scan = parse_statement((ROOT / "sample_scan_no_text.pdf").read_bytes())
scan_ok = scan.get("error") == "no_text_layer"
print(("OK " if scan_ok else "FAIL"), "sample_scan_no_text.pdf stub", scan.get("error"))
failed += not scan_ok
sys.exit(1 if failed else 0)
