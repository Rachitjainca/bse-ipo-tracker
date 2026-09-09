#!/usr/bin/env python3
"""
SEBI RHP Pipeline Tracker - Tracks companies filed with SEBI but not yet live on BSE/NSE
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SEBI_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=11"
PIPELINE_FILE = Path(__file__).parent / "sebi_pipeline_tracker.csv"
TRACKER_FILE = Path(__file__).parent / "ipo_tracker.csv"
GCHAT_WEBHOOK = os.environ.get("GCHAT_WEBHOOK_URL", "")

FIELDNAMES = ["company", "filing_date", "stage", "sebi_url", "discovered_at"]


def fetch_sebi_rhp_filings():
    """Fetch recent SEBI RHP filings"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.sebi.gov.in/",
        }
        response = requests.get(SEBI_URL, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        filings = []

        # Find ALL table elements
        tables = soup.find_all('table')
        print(f"DEBUG: Found {len(tables)} tables on SEBI page", file=sys.stderr)

        # Try to find filings in any table
        for table_idx, table in enumerate(tables):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    date_text = cells[0].get_text(strip=True)
                    title_text = cells[1].get_text(strip=True)

                    # Filter for RHP entries (exact match for RHP)
                    if date_text and 'RHP' in title_text and len(date_text) > 5:
                        # Extract company name
                        company = title_text.replace('RHP', '').replace('Red Herring Prospectus', '').strip()
                        company = company.replace('(Addendum)', '').replace('(Amendment)', '').strip()

                        # Get document link
                        link_elem = cells[1].find('a')
                        sebi_url = link_elem.get('href', '') if link_elem else ''

                        if company and len(company) > 3:  # Avoid empty/garbage entries
                            filings.append({
                                'company': company,
                                'filing_date': date_text,
                                'sebi_url': sebi_url
                            })
                            print(f"DEBUG: Found filing - {company} ({date_text})", file=sys.stderr)

        print(f"DEBUG: Total filings extracted: {len(filings)}", file=sys.stderr)
        return filings

    except Exception as e:
        print(f"ERROR: Could not fetch SEBI data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return []


def load_live_ipo_names():
    """Load companies already on BSE/NSE to avoid duplicates"""
    live_names = set()
    if not TRACKER_FILE.exists():
        return live_names

    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("name"):
                    live_names.add(row["name"].lower())
    except Exception as e:
        print(f"WARNING: Could not read live IPO tracker: {e}", file=sys.stderr)

    return live_names


def load_pipeline_tracking():
    """Load previously tracked pipeline companies"""
    tracked = {}
    if not PIPELINE_FILE.exists():
        return tracked

    try:
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("company"):
                    tracked[row["company"].lower()] = row
    except Exception as e:
        print(f"WARNING: Could not read pipeline tracker: {e}", file=sys.stderr)

    return tracked


def save_pipeline_ipo(company_data):
    """Append IPO to pipeline tracker"""
    company_data_copy = company_data.copy()
    company_data_copy["discovered_at"] = datetime.now().isoformat()

    try:
        file_exists = PIPELINE_FILE.exists()
        with open(PIPELINE_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(company_data_copy)
    except Exception as e:
        print(f"ERROR saving pipeline IPO: {e}", file=sys.stderr)


def send_gchat_alert(company, filing_date):
    """Send Google Chat notification for new pipeline IPO"""
    if not GCHAT_WEBHOOK:
        return False

    message = {
        "text": (
            f"📋 New SEBI IPO Filing Alert\n\n"
            f"*Company:* {company}\n"
            f"*Filed Date:* {filing_date}\n"
            f"*Stage:* Application (RHP filed with SEBI)\n"
            f"*Expected:* Should appear on BSE/NSE within 4-8 days\n"
            f"*Status:* Pipeline - Coming Soon"
        )
    }

    try:
        response = requests.post(GCHAT_WEBHOOK, json=message, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"ERROR sending Google Chat notification: {e}", file=sys.stderr)
        return False


def main():
    """Fetch SEBI filings and track new pipeline IPOs"""
    print(f"[{datetime.now().isoformat()}] Starting SEBI Pipeline Tracker...")

    # Fetch SEBI data
    print("Fetching SEBI RHP filings...")
    sebi_filings = fetch_sebi_rhp_filings()
    print(f"  Found {len(sebi_filings)} SEBI RHP filings")

    if not sebi_filings:
        print("No filings found or error occurred")
        return 0

    # Load tracking data
    live_names = load_live_ipo_names()
    tracked_pipeline = load_pipeline_tracking()

    print(f"Previously tracked live IPOs: {len(live_names)}")
    print(f"Previously tracked pipeline: {len(tracked_pipeline)}")

    # Find new pipeline filings
    new_pipeline = []
    for filing in sebi_filings:
        company_lower = filing['company'].lower()

        # Skip if already on live exchanges
        if company_lower in live_names:
            print(f"  ℹ️  {filing['company']} - already live on BSE/NSE (skip)")
            continue

        # Skip if already tracked in pipeline
        if company_lower in tracked_pipeline:
            continue

        # New pipeline filing!
        new_pipeline.append({
            "company": filing["company"],
            "filing_date": filing["filing_date"],
            "stage": "pipeline",
            "sebi_url": filing["sebi_url"]
        })

    print(f"\nNew Pipeline IPOs: {len(new_pipeline)}")

    # Process each new pipeline IPO
    for ipo in new_pipeline:
        print(f"  ➕ [{ipo['company']}] Filed: {ipo['filing_date']}")
        send_gchat_alert(ipo['company'], ipo['filing_date'])
        save_pipeline_ipo(ipo)

    if new_pipeline:
        print(f"✓ Processed {len(new_pipeline)} new pipeline IPO(s)")
    else:
        print("No new pipeline IPOs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
