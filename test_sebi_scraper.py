#!/usr/bin/env python3
"""
Test SEBI RHP filings scraper - shows output before adding to main codebase
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json

SEBI_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=11"

def fetch_sebi_rhp_filings(limit=20):
    """Fetch recent SEBI RHP filings"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(SEBI_URL, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for table rows with filing data
        filings = []

        # Find all table rows (SEBI uses various table structures)
        rows = soup.find_all('tr')

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                # Try to extract date and company name
                date_text = cells[0].get_text(strip=True)
                title_text = cells[1].get_text(strip=True)

                # Filter for actual filing entries (skip headers, empty rows)
                if date_text and title_text and len(date_text) > 5 and 'RHP' in title_text:
                    filings.append({
                        'date': date_text,
                        'company': title_text,
                        'raw_html': str(cells[1])
                    })

            if len(filings) >= limit:
                break

        return filings

    except Exception as e:
        print(f"ERROR fetching SEBI data: {e}")
        return []

def format_output(filings):
    """Format filings for display"""
    if not filings:
        print("❌ No filings found")
        return

    print(f"\n{'='*80}")
    print(f"SEBI RHP FILINGS - Latest {len(filings)} Entries")
    print(f"{'='*80}\n")

    for i, filing in enumerate(filings, 1):
        print(f"{i}. Date: {filing['date']}")
        print(f"   Company: {filing['company']}")
        print()

    print(f"{'='*80}")
    print(f"Sample JSON output:\n")
    print(json.dumps(filings[:3], indent=2))
    print(f"{'='*80}\n")

if __name__ == "__main__":
    print("Fetching SEBI RHP filings...")
    filings = fetch_sebi_rhp_filings(limit=20)
    format_output(filings)
