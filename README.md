# BSE + NSE IPO Tracker

Real-time tracker for **live** and **upcoming IPOs** on both **BSE** (Bombay Stock Exchange) and **NSE** (National Stock Exchange). Fetches from official APIs every 6 hours, detects new IPOs, and sends Google Chat notifications with key details.

## Features

- ✅ **Dual exchange support**: BSE MainBoard, BSE SME, and NSE
- ✅ **Live IPOs** (currently trading) + **Upcoming IPOs** (pre-opening)
- ✅ **Intelligent deduplication**: Same IPO listed on both exchanges → one notification
- ✅ **Real-time alerts**: Google Chat webhook notifications within 6 hours of listing
- ✅ **Persistent tracking**: `ipo_tracker.csv` prevents duplicate notifications
- ✅ **Zero server**: Runs free on GitHub Actions (no EC2, no Lambda)

## Supported IPO Types

| Exchange | Type | Example |
|---|---|---|
| BSE | MainBoard | Typical large-cap IPO |
| BSE | SME | Small/Medium Enterprise IPO |
| NSE | MainBoard | Typical large-cap IPO |

## Setup

### 1. Create Google Chat Webhook

1. Open [Google Chat](https://chat.google.com) → your space
2. Space name → **Manage webhooks** → **Create new webhook**
3. Name: `BSE-NSE IPO Tracker`
4. Click **Create** → copy the webhook URL

### 2. Create GitHub Repo

Create a new public repo at `https://github.com/Rachitjainca/bse-ipo-tracker`

### 3. Add Webhook to GitHub Secrets

1. Repo → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
   - Name: `GCHAT_WEBHOOK_URL`
   - Value: paste your webhook URL from step 1
3. **Add secret**

### 4. Test

1. **Actions** tab → **Check BSE + NSE IPOs** → **Run workflow**
2. Should run successfully, fetch from both exchanges
3. On first run: likely no new IPOs (tracker empty), but workflow succeeds
4. Check the commit to `ipo_tracker.csv`

## How It Works

| Step | Detail |
|---|---|
| **Fetch** | Calls BSE Live, BSE Upcoming, and NSE APIs every 6 hours |
| **Parse** | BSE: filters for `IR_flag="IPO"`; NSE: filters for `status="Active"` or `"Forthcoming"` |
| **Deduplicate** | Combines results, deduplicates by IPO name across exchanges (same IPO on BSE+NSE → 1 notification) |
| **Detect** | Compares against `ipo_tracker.csv` to find new ones |
| **Notify** | Sends Google Chat message with exchange, status, name, dates, type |
| **Track** | Appends to `ipo_tracker.csv` so it's never notified twice |
| **Commit** | Updates tracker in git so state persists across runs |

## Notification Example

When a new IPO appears on either exchange:

```
🆕 New LIVE IPO Alert (BSE)

Name: Example Corp Ltd.
Exchange: 🏦 BSE
Open Date: 15-Feb-2025
Close Date: 19-Feb-2025
Type: MainBoard
Status: LIVE
```

For NSE:
```
⏳ New UPCOMING IPO Alert (NSE)

Name: TechStart India Ltd.
Exchange: 📈 NSE
Open Date: 01-Mar-2025
Close Date: 05-Mar-2025
Type: MainBoard
Status: UPCOMING
```

## APIs

| Exchange | Endpoint | Status Field |
|---|---|---|
| **BSE Live** | `api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&status=L...` | Direct (LIVE) |
| **BSE Upcoming** | `api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1&status=F...` | Direct (UPCOMING) |
| **NSE** | `www.nseindia.com/api/all-upcoming-issues?category=ipo` | `status: "Active"` or `"Forthcoming"` |

Filter applied:
- **BSE**: `IR_flag == "IPO"` (excludes rights issues, etc.)
- **NSE**: `category == "ipo"` and `status in ["Active", "Forthcoming"]`

## Files

| File | Purpose |
|---|---|
| `fetch_ipos.py` | Main tracker script (fetches, deduplicates, notifies) |
| `.github/workflows/check_ipos.yml` | GitHub Actions workflow (runs every 6 hours) |
| `ipo_tracker.csv` | Persistent list of seen IPOs (auto-generated) |
| `.gitignore` | Ignores Python cache/venv |
| `README.md` | This file |

## Tracker File Format

`ipo_tracker.csv`:
```
exchange,status,name,open_date,close_date,ipo_type,fetched_at
BSE,LIVE,Example Corp Ltd.,15-Feb-2025,19-Feb-2025,MainBoard,2025-02-15T10:30:00
NSE,UPCOMING,TechStart India Ltd.,01-Mar-2025,05-Mar-2025,MainBoard,2025-02-28T08:00:00
```

## Local Testing

```bash
pip install requests
export GCHAT_WEBHOOK_URL="your-webhook-url-here"
python fetch_ipos.py
```

The script will:
1. Fetch from BSE Live, BSE Upcoming, NSE
2. Print results to console
3. Send Google Chat notification for each new IPO
4. Append to `ipo_tracker.csv`

If `GCHAT_WEBHOOK_URL` is not set, notifications are skipped (useful for testing).

## Customization

### Change Schedule

Edit `.github/workflows/check_ipos.yml` cron:

```yaml
- cron: "0 9,15 * * MON-FRI"  # 9am and 3pm, weekdays only (UTC)
```

Cron format: `minute hour day month day-of-week`

### Filter to Specific Exchange Only

Edit `fetch_ipos.py` `main()`:

```python
# Only BSE
ipos = bse_ipos  # Remove nse_ipos

# Only NSE
ipos = nse_ipos  # Remove bse_ipos
```

### Customize Notification Format

Edit `send_gchat_notification()` in `fetch_ipos.py`.

## Troubleshooting

| Issue | Solution |
|---|---|
| Workflow doesn't run | Check **Actions** tab for error logs. Verify `GCHAT_WEBHOOK_URL` secret exists. |
| Webhook URL invalid | Re-create webhook in Google Chat, copy the full URL (with `?key=...`). |
| NSE API 403 Forbidden | NSE blocks some user-agents. Script uses a standard browser User-Agent; if blocked, add retry logic. |
| Duplicate notifications | `ipo_tracker.csv` was deleted or git history reset. Restore backup or re-initialize. |
| No IPOs appearing | BSE/NSE APIs may be down. Check them directly in a browser. Try manual workflow trigger. |

## Notes

- Deduplication is **case-insensitive** by IPO name — "Acme Corp" and "ACME CORP" are treated as the same
- If an IPO appears on both BSE and NSE with different details, you see it once with the first-encountered exchange listed
- Tracker file is committed to git; history is permanent (prevents against server crashes or lost state)
- GitHub Actions free tier: 2,000 minutes/month, plenty for 4 runs/day

## License

Public domain.
