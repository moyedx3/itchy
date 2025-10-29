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
        print(f"  {idx}. {filing.get('report_nm')} — {filing.get('rcept_dt')} ({filing.get('rcept_no')})")

    # Financial metric -------------------------------------------------
    print("\n3. Latest revenue metric")
    metric = client.get_latest_metric([
        "매출액",
        "매출총액",
        "영업수익",
        "Revenue",
    ])

    if metric:
        print(json.dumps(metric, ensure_ascii=False, indent=2))
    else:
        print("  → Could not locate revenue metric in finstate response")


    # Test with multiple companies
    print("\n4. Testing with multiple companies")
    companies = [
        "222800", # 심텍 (KOSDAQ : 222800)
        "005930", # 삼성전자 (KOSPI : 005930)
        "138040", # 메리츠금융지주 (KOSPI : 138040)
    ]
    for company in companies:
        client = OpenDartClient(corp_code=company)

        # filings = client.list_filings(kind="A", limit=5)
        # for filing in filings:
        #     print(f"  {filing.get('report_nm')} — {filing.get('rcept_dt')} ({filing.get('rcept_no')})")

        company = client.get_company()
        metric = client.get_latest_metric([
            "매출액",
            "매출총액",
            "영업수익",
            "Revenue",
        ])

        print(f"Company: {company.get('corp_name')} ({company.get('corp_code')})")
        print(json.dumps(metric, ensure_ascii=False, indent=2))

    print("\nDone ✅")

if __name__ == "__main__":
    main()
