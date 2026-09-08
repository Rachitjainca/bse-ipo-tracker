#!/usr/bin/env python3
"""
BSE + NSE IPO Tracker - Fetch live and upcoming IPOs from both exchanges,
detect new ones, send Google Chat notifications. Deduplicates by IPO name
across exchanges.

APIs:
- BSE Live:     https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&status=L...
- BSE Upcoming: https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&status=F...
- NSE:          https://www.nseindia.com/api/all-upcoming-issues?category=ipo
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# API endpoints
BSE_LIVE_API = "https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&status=L&exchange=&ir_flag="
BSE_UPCOMING_API = "https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&scrip_Name=&ir_flag=&status=F&exchange="
NSE_API = "https://www.nseindia.com/api/all-upcoming-issues?category=ipo"

TRACKER_FILE = Path(__file__).parent / "ipo_tracker.csv"
GCHAT_WEBHOOK = os.environ.get("GCHAT_WEBHOOK_URL", "")

# CSV columns to track
FIELDNAMES = ["exchange", "status", "name", "open_date", "close_date", "ipo_type", "fetched_at"]

# Session with retry headers to avoid NSE blocking
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def fetch_bse_ipos() -> list[dict]:
    """Fetch IPOs from BSE Live and Upcoming APIs.

    BSE returns: {"Table": [{...}, {...}]}
    Filters for: IR_flag == "IPO" only (excludes FPO, RI, BuyBack, CMN, OTB, DPI, etc.)
    """
    results = []

    for api_url, status_label in [
        (BSE_LIVE_API, "LIVE"),
        (BSE_UPCOMING_API, "UPCOMING"),
    ]:
        try:
            response = SESSION.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"ERROR: BSE {status_label} returned invalid JSON: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"ERROR fetching BSE {status_label}: {e}", file=sys.stderr)
            continue

        # BSE wraps data in {"Table": [...]}
        if isinstance(data, dict):
            items = data.get("Table", [])
        elif isinstance(data, list):
            items = data
        else:
            print(f"WARNING: BSE {status_label} returned unexpected type: {type(data)}", file=sys.stderr)
            continue

        if not isinstance(items, list):
            print(f"WARNING: BSE {status_label} 'Table' is not a list: {type(items)}", file=sys.stderr)
            continue

        for item in items:
            # Filter: ONLY IR_flag == "IPO" (exclude FPO, RI, BuyBack, CMN, OTB, DPI, etc.)
            if item.get("IR_flag") != "IPO":
                continue

            ipo = {
                "exchange": "BSE",
                "status": status_label,
                "name": item.get("Scrip_Name", "").strip(),
                # BSE uses Start_Dt and End_Dt (ISO format)
                "open_date": item.get("Start_Dt", "").split("T")[0] if item.get("Start_Dt") else "",
                "close_date": item.get("End_Dt", "").split("T")[0] if item.get("End_Dt") else "",
                # eXCHANGE_PLATFORM: "MainBoard" or "SME"
                "ipo_type": item.get("eXCHANGE_PLATFORM", "").strip() or "MainBoard",
            }
            if ipo["name"]:
                results.append(ipo)

    return results


def fetch_nse_ipos() -> list[dict]:
    """Fetch IPOs from NSE API. Status: 'Forthcoming' or 'Active'."""
    try:
        response = SESSION.get(NSE_API, timeout=10)
        response.raise_for_status()
        data = response.json()
    except json.JSONDecodeError as e:
        print(f"ERROR: NSE returned invalid JSON: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERROR fetching NSE IPOs: {e}", file=sys.stderr)
        return []

    results = []

    # Handle both direct list and wrapped object responses
    if isinstance(data, dict):
        items = data.get("data", [])
    elif isinstance(data, list):
        items = data
    else:
        print(f"WARNING: NSE returned unexpected type: {type(data)}", file=sys.stderr)
        return []

    if not isinstance(items, list):
        print(f"WARNING: NSE data is not a list: {type(items)}", file=sys.stderr)
        return []

    for item in items:
        status_raw = item.get("status", "").strip()
        if status_raw == "Forthcoming":
            status = "UPCOMING"
        elif status_raw == "Active":
            status = "LIVE"
        else:
            # Unknown status, skip
            continue

        ipo = {
            "exchange": "NSE",
            "status": status,
            "name": item.get("companyName", "").strip() or item.get("company_name", "").strip(),
            # NSE uses issueStartDate and issueEndDate instead of openDate/closeDate
            "open_date": item.get("issueStartDate", "") or item.get("openDate", "") or item.get("open_date", ""),
            "close_date": item.get("issueEndDate", "") or item.get("closeDate", "") or item.get("close_date", ""),
            "ipo_type": item.get("boardCode", "").strip() or item.get("board_code", "").strip() or "MainBoard",
        }
        if ipo["name"]:
            results.append(ipo)

    return results


def load_tracked_ipos() -> set[str]:
    """Load set of previously-seen IPO names (deduplicated across exchanges)."""
    if not TRACKER_FILE.exists():
        return set()

    tracked = set()
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("name"):
                    tracked.add(row["name"].lower())
    except Exception as e:
        print(f"WARNING: Could not read tracker file: {e}", file=sys.stderr)

    return tracked


def save_ipo(ipo: dict) -> None:
    """Append IPO to tracker file."""
    ipo_copy = ipo.copy()
    ipo_copy["fetched_at"] = datetime.now().isoformat()

    try:
        file_exists = TRACKER_FILE.exists()
        with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(ipo_copy)
    except Exception as e:
        print(f"ERROR saving IPO: {e}", file=sys.stderr)


def send_gchat_notification(ipo: dict) -> bool:
    """Send Google Chat webhook notification for new IPO."""
    if not GCHAT_WEBHOOK:
        print(f"INFO: No GCHAT_WEBHOOK_URL set, skipping notification for {ipo['name']}")
        return False

    # Format message for Google Chat
    exchange_emoji = "🏦" if ipo["exchange"] == "BSE" else "📈"
    status_emoji = "🆕" if ipo["status"] == "LIVE" else "⏳"

    message = {
        "text": (
            f"{status_emoji} New {ipo['status']} IPO Alert ({ipo['exchange']})\n\n"
            f"*Name:* {ipo['name']}\n"
            f"*Exchange:* {exchange_emoji} {ipo['exchange']}\n"
            f"*Open Date:* {ipo['open_date'] or 'N/A'}\n"
            f"*Close Date:* {ipo['close_date'] or 'N/A'}\n"
            f"*Type:* {ipo['ipo_type'] or 'N/A'}\n"
            f"*Status:* {ipo['status']}"
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
    """Fetch IPOs from BSE + NSE, detect new ones, send notifications."""
    print(f"[{datetime.now().isoformat()}] Starting IPO tracker (BSE + NSE)...")

    # Fetch from BSE
    print("Fetching BSE IPOs...")
    bse_ipos = fetch_bse_ipos()
    print(f"  Found {len(bse_ipos)} BSE IPO(s)")

    # Fetch from NSE
    print("Fetching NSE IPOs...")
    nse_ipos = fetch_nse_ipos()
    print(f"  Found {len(nse_ipos)} NSE IPO(s)")

    all_ipos = bse_ipos + nse_ipos

    # Load previously tracked
    tracked = load_tracked_ipos()
    print(f"Previously tracked: {len(tracked)} unique IPO name(s)")

    # Find new ones (deduplicate by name across exchanges)
    new_ipos = []
    for ipo in all_ipos:
        if ipo["name"].lower() not in tracked:
            new_ipos.append(ipo)
            tracked.add(ipo["name"].lower())  # Track immediately to avoid duplicates in same run

    print(f"New IPO(s): {len(new_ipos)}")

    # Process each new IPO
    for ipo in new_ipos:
        print(f"  -> [{ipo['exchange']}] {ipo['status']} {ipo['name']}")
        send_gchat_notification(ipo)
        save_ipo(ipo)

    if new_ipos:
        print(f"✓ Processed {len(new_ipos)} new IPO(s)")
    else:
        print("No new IPOs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
