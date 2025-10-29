#!/usr/bin/env python3
"""Quick smoke test for the OpenDART client.

Run with:

    uv run python resolvers/dart/test_dart_client.py

The script prints a few sample queries using Samsung Electronics as the
reference company. Set ``DART_API_KEY`` in your environment before running.
"""

from __future__ import annotations

import json

from config import DART_API_KEY
from dart_client import OpenDartClient, OpenDartError


def main() -> None:
    if not DART_API_KEY:
        print("⚠️  Set DART_API_KEY in your environment to exercise the DART client.")
        return

    try:
        client = OpenDartClient(corp_name="삼성전자")
    except OpenDartError as exc:
        print(f"Failed to initialise client: {exc}")
        return

    print("=" * 60)
    print("Testing OpenDART Client")
    print("=" * 60)

    # Company overview -------------------------------------------------
    print("\n1. Company overview")
    company = client.get_company()
    print(json.dumps({
        "corp_code": client.corp_code,
        "corp_name": company.get("corp_name"),
        "ceo_nm": company.get("ceo_nm"),
        "industry": company.get("corp_cls"),
    }, ensure_ascii=False, indent=2))

    # Recent filings ---------------------------------------------------
    print("\n2. Recent filings (kind=A)")
    filings = client.list_filings(kind="A", limit=5)
    for idx, filing in enumerate(filings, start=1):
        print(f"  {idx}. {filing.get('report_nm')} — {filing.get('rcept_dt')} ({filing.get('rcp_no')})")

    # Financial metric -------------------------------------------------
    print("\n3. Latest revenue metric")
    period = _infer_period(filings)
    metric = client.get_financial_metric([
        "매출액",  # primary Korean label
        "영업수익",
        "Revenue",
    ], year=_infer_latest_year(filings), period=period)

    if metric:
        print(json.dumps(metric, ensure_ascii=False, indent=2))
    else:
        print("  → Could not locate revenue metric in finstate response")

    print("\nDone ✅")


def _infer_latest_year(filings):  # type: ignore[no-untyped-def]
    for filing in filings:
        date = filing.get("rcept_dt")
        if date and len(date) >= 4:
            try:
                return int(date[:4])
            except ValueError:
                continue
    return _fallback_year()


def _infer_period(filings):  # type: ignore[no-untyped-def]
    if not filings:
        return "annual"
    report_nm = filings[0].get("report_nm", "") or ""
    if "반기" in report_nm:
        return "half"
    if "1분기" in report_nm or "1/4" in report_nm or "1Q" in report_nm:
        return "q1"
    if "3분기" in report_nm or "3/4" in report_nm or "3Q" in report_nm:
        return "q3"
    if "사업보고서" in report_nm or "연간" in report_nm:
        return "annual"
    return "annual"


def _fallback_year() -> int:
    from datetime import date

    return date.today().year - 1


if __name__ == "__main__":
    main()


