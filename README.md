# Blue Iris Export Automation

Automated MP4 export pipeline for **Blue Iris 5.9.x** using the JSON API and Convert/Export queue.

This project provides a robust, production-ready interface for:

- Authenticating with Blue Iris
- Querying clips by camera and time range
- Exporting individual clips to MP4
- Polling export completion
- Downloading finished exports
- Organizing output into structured folders
- Running concurrent exports safely

---

# Blue Iris Video Export Platform

Production-grade automation pipeline for:

- Exporting clips from Blue Iris via JSON API
- Weekend (Fri/Sat/Sun) scheduled exports
- Multi-camera batch jobs
- Export deduplication
- Export metrics tracking
- ZeroTier network dashboard
- Nginx portal integration
- Threaded export processing
- Timezone-aware scheduling

---

# Architecture Overview

Blue Iris Server
│
│ JSON API (login, cliplist, export)
▼
bi_client.py
│
▼
bi_exporter.py
│
├── Export Tracker (JSON file)
├── Metrics aggregation
├── ThreadPool export workers
▼
Exported MP4 files
│
▼
Nginx HTTPS Portal
├── /videos
├── /images
├── /documents
├── /zt dashboard
└── /bi_metrics dashboard


---

# Features

## Export Engine

- Uses modern BI `export` command (not deprecated `clipcreate`)
- Polls export queue until `status=done`
- Downloads from `/clips/`
- Automatically removes `Clipboard\` from filenames
- Multi-threaded exports
- Timezone-aware epoch conversion
- Handles large clips
- Clean failure reporting

## Export Deduplication

Clips are tracked in:

<export_root>/.bi_export_tracker.json


If a clip was previously exported successfully:


It will be skipped automatically.

---

## Metrics Dashboard

Provides:

- Total success / failed / skipped
- Per-camera breakdown
- Recent activity log
- Health badge
- Auto-refresh every 10 seconds

Available at:

https://<host>:8443/bi_metrics.html

API endpoint:

/api/bi/metrics


---

## ZeroTier Dashboard

Live network visibility:

- Online / offline nodes
- 2–10 minute “stale” yellow state
- Network health badge
- Online node count

Available at:

https://<host>:8443/zt_dashboard.html


API endpoint:

/api/zt


---

# Project Structure

bi_video_export/
│
├── src/
│ └── bi_exporter/
│ ├── bi_client.py
│ ├── bi_exporter.py
│ └── dashboard/
│ └── app.py
│
├── scripts/
│ ├── run_dashboard.sh
│ └── deploy.sh
│
├── nginx/
│ ├── blueiris.conf
│ └── README.md
│
│
├── videos/ # Export root
├── documents/
├── requirements.txt
├── .env
└── README.md


---

# Required Environment Variables

Create `.env` in project root:

ZT_TOKEN=<your_zerotier_api_token>
ZT_NETWORK_ID=<your_network_id>
BI_EXPORT_ROOT=/absolute/path/to/videos


Example:

ZT_TOKEN=abc123
ZT_NETWORK_ID=48d6023c46240a68
BI_EXPORT_ROOT=/Users/tedspecht/haunt_stalker/bi_video_export/videos


---

# Running the Export Script

## Basic Run


This:

- Loads config/export_jobs.yaml
- Logs into Blue Iris
- Processes all jobs
- Applies dedupe
- Writes metrics
- Prints summary

---

## List Cameras


---

## List Clips

python bi_interface.py
--list-clips am011-gp01
--date 2026-02-07
--start 17:00:00
--end 21:00:00


---

## Weekend Export Automation

Example job config:

```yaml
jobs:
  - camera: am016-gp02
    date: 2026-02-07
    start: "18:00:00"
    end: "23:00:00"
    timezone: America/Chicago



---


You can dynamically generate jobs for every Friday, Saturday, Sunday.

Running the Dashboard
Start Flask Dashboard
./scripts/run_dashboard.sh


Flask runs locally:
http://127.0.0.1:5001

Nginx proxies:
https://<host>:8443/api/

To restart nginx on Mac:
brew services restart nginx

Installing Dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


Example requirements:
- Flask
- requests
- PyYAML

---

Troubleshooting
- Export Never Completes
-- Check BI Convert/Export queue in console
-- Verify disk space
-- Try reencode=false for faster direct export
- 401 Unauthorized
-- Verify HTTP Basic Auth credentials
-- Confirm BI web server authentication settings
- 404 Export Download
-- Ensure correct /clips/{uri} path
-- Confirm export reached status=done

---


Development Notes
- No SQLite used
- Tracker stored as JSON
- Thread-safe export processing
- No recursive retry loops
- Designed for macOS + Homebrew nginx
- Compatible with ZeroTier private network

---

Security Notes
- Nginx uses HTTPS (self-signed)
- HTTP Basic Auth protects portal
- ZeroTier isolates internal services
- Flask bound to 127.0.0.1 only
