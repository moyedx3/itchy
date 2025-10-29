#!/usr/bin/env python3
"""Quick test script to verify SEC API client works."""

from sec_client import SECClient
import json


def test_client():
    """Test SEC client basic functionality."""
    print("="*60)
    print("Testing SEC Client")
    print("="*60)
    
    client = SECClient("0000320193")
    
    # Test 1: Fetch submissions
    print("\n1. Fetching submissions...")
    submissions = client.get_submissions()
    if submissions:
        print(f"✅ Success! Entity: {submissions.get('name', 'Unknown')}")
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])[:5]
        print(f"   Recent forms: {forms}")
    else:
        print("❌ Failed to fetch submissions")
        return
    
    # Test 2: Fetch company facts
    print("\n2. Fetching company facts...")
    facts = client.get_company_facts()
    if facts:
        print(f"✅ Success! Entity: {facts.get('entityName', 'Unknown')}")
        print(f"   CIK: {facts.get('cik', 'Unknown')}")
    else:
        print("❌ Failed to fetch company facts")
        return
    
    # Test 3: Extract revenue
    print("\n3. Extracting latest revenue...")
    revenue = client.get_latest_metric(facts, ["Revenues"])
    if revenue:
        print(f"✅ Success!")
        print(f"   Tag:          {revenue['tag']}")
        print(f"   Value:        ${revenue['value']:,.0f}")
        print(f"   Period End:   {revenue['end']}")
        print(f"   Form:         {revenue['form']}")
        print(f"   Filed:        {revenue['filed']}")
        print(f"   Fiscal:       {revenue['fiscal_period']} {revenue['fiscal_year']}")
    else:
        print("❌ Failed to extract revenue")
        return
    
    # Test 4: Get recent filings
    print("\n4. Getting recent 10-Q/10-K filings...")
    filings = client.get_recent_filings(["10-Q", "10-K"])
    if filings:
        print(f"✅ Found {len(filings)} recent filings")
        for i, filing in enumerate(filings[:3], 1):
            print(f"   {i}. {filing['form']} - {filing['filing_date']} - {filing['accession']}")
    else:
        print("❌ No filings found")
    
    print("\n" + "="*60)
    print("All tests passed! ✅")
    print("="*60)


if __name__ == "__main__":
    test_client()

