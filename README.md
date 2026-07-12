# Train Ticket Availability Monitor

Monitors Chennai ↔ Bangalore train seat availability and sends email alerts when seats start filling up.

## What it does

- Checks availability every hour for:
  - **Chennai → Bangalore** evening trains on Mondays & Tuesdays
  - **Bangalore → Chennai** evening trains on Thursdays & Fridays
  - Over the next 14 days
- Sends an **immediate alert email** when available seats drop below a threshold (default: ≤60 seats, then again at ≤20)
- Sends a **daily digest email** at 8 AM IST with a full availability table across all upcoming dates
- All classes are monitored: 1A, 2A, 3A, SL, CC, EC, 2S
- Alerts fire at most once per threshold per train/date/class per day

## Setup

### 1. Get an API key

Register for a free account at [indianrailapi.com](https://indianrailapi.com/registration).

> **Note on the free tier:** The free plan allows 100 API hits/day. Hourly checks across all classes and upcoming dates will exceed this. For full functionality, consider upgrading to a paid plan (contact them after registration). Alternatively, reduce `CHECK_INTERVAL_MINUTES` to 240 (4 hours) to stay closer to the free tier limit.

### 2. Create a Gmail App Password

1. Enable 2-Step Verification on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create an app password for "Mail"
4. Copy the 16-character password

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API key, Gmail address, and app password
```

### 4. Install & run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Configuration reference

All settings live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `RAIL_API_KEY` | — | indianrailapi.com API key (required) |
| `GMAIL_ADDRESS` | — | Gmail address to send from (required) |
| `GMAIL_APP_PASSWORD` | — | Gmail app password (required) |
| `NOTIFY_EMAIL` | harimanjunath@gmail.com | Who receives alerts |
| `CHECK_INTERVAL_MINUTES` | 60 | How often to poll for availability |
| `DAILY_DIGEST_TIME` | 08:00 | Time to send daily summary (IST, HH:MM) |
| `LOOKAHEAD_DAYS` | 14 | How many days ahead to monitor |
| `ALERT_THRESHOLDS` | 60,20 | Comma-separated seat counts that trigger alerts |
| `CHENNAI_BLR_WINDOW_START` | 16:00 | Earliest departure for Chennai→Bangalore |
| `CHENNAI_BLR_WINDOW_END` | 22:00 | Latest departure for Chennai→Bangalore |
| `BLR_CHENNAI_WINDOW_START` | 16:00 | Earliest departure for Bangalore→Chennai |
| `BLR_CHENNAI_WINDOW_END` | 22:00 | Latest departure for Bangalore→Chennai |

To change monitored days or add routes, edit `ROUTES` in `config.py`.

## How alerts work

IRCTC's availability system returns strings like `AVAILABLE-42`, meaning 42 seats are currently open. Since total train capacity isn't exposed by the API, alerts are based on **absolute seat counts** rather than percentages.

Suggested threshold mapping:
- ≤60 seats ≈ "starting to fill up" (roughly 50% full for a typical SL coach set)
- ≤20 seats ≈ "almost full"

Adjust `ALERT_THRESHOLDS` in `.env` to match your comfort level.

## Running as a background service

For 24/7 operation, run with a process manager:

```bash
# Using nohup
nohup python main.py > train_monitor.log 2>&1 &

# Or with systemd — create /etc/systemd/system/train-monitor.service
```
