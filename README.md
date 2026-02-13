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

# Overview

Blue Iris exposes a JSON API for clip listing and export operations. However, the API behavior differs significantly from older documentation and from what the Web UI appears to do internally.

This project implements the correct workflow for Blue Iris **5.9.9.x**, including:

- HTTP Basic authentication
- JSON session login handshake
- Export queue management using `cmd="export"`
- Proper download endpoint usage via `/clips/{uri}`
- Cross-platform filename normalization
- Thread-safe concurrent export handling

---

# Architecture

The solution is divided into three primary components:
bi_interface.py → CLI entrypoint
bi_client.py → Blue Iris API client
bi_exporter.py → Export orchestration + threading


---

## 1. `bi_client.py`

Encapsulates all communication with Blue Iris.

### Responsibilities

- HTTP Basic authentication
- JSON session login (MD5 challenge/response)
- Clip listing (`cliplist`)
- Camera listing (`camlist`)
- Export queue enqueue (`cmd="export"`)
- Download handling via `/clips/{uri}`

### Design Decisions

- Uses `requests.Session()` for persistent cookies
- Implements safe session refresh logic (no recursion)
- Separates queue ID from export URI correctly
- Avoids deprecated `clipcreate`

---

## 2. `bi_exporter.py`

Handles the export workflow and concurrency.

### Responsibilities

- Time-range clip querying
- Enqueueing exports
- Polling `/clips/{uri}` until available
- Saving files locally
- Structured logging
- ThreadPoolExecutor-based parallel processing
- Clean summary reporting

### Important Behavior

- Uses `cmd="export"` (not `clipcreate`)
- Extracts `uri` from export response
- Downloads using `/clips/{uri}?session=...`
- Normalizes Windows backslashes for cross-platform compatibility

---

## 3. `bi_interface.py`

Command-line entrypoint.

### Responsibilities

- Load YAML configuration
- Instantiate `BlueIrisClient`
- Trigger exports
- Optional camera listing
- Print summary results

---

# Correct Blue Iris Export Workflow

The working flow (as confirmed by documentation and live testing):

1. Authenticate via HTTP Basic
2. Perform JSON login handshake
3. Call:
        cmd = "export"
        path = "@record"
4. Receive:
        {
        "path": "@queue_record",
        "status": "queued",
        "uri": "Clipboard\filename.mp4"
        }
5. Poll:
        /clips/{uri}?session=...

6. When HTTP 200 → download file

### Important Notes

- `/file/` is **not** correct for export products
- `/clips/` must be used
- `uri` must be normalized (Windows → POSIX path separators)

---

# Why This Took the Long Path

This integration required navigating several non-obvious Blue Iris behaviors.

### 1. `clipcreate` Is Deprecated / Restricted

Even admin users receive `"Access denied"` in modern 5.9 builds.  
The correct command is `cmd="export"`.

### 2. Export Queue ≠ Direct File Endpoint

Export products are accessed via:
    /clips/{uri}

NOT via `/file/`.

### 3. `path` Is Not the Download Target

The returned `"path"` is a queue ID — not the exported file.

The `"uri"` is the actual file reference.

### 4. Windows Paths on macOS/Linux

Blue Iris returns:

videos/<camera>/<YYYY-MM-DD>/

- Automatic camera folder initialization
- Clean failure reporting
- Cross-platform compatibility
- Production-safe retry logic

---

# Example Folder Structure

videos/
am016-gp02/2026-02-08/am016-gp02.20260208_121446-122703.mp4
am036-gp02/2026-02-08/am036-gp02.20260208_121008-121457.mp4

---

# Configuration

All clips are specified in the configuration file:

    `config/export_jobs.yaml`

```yaml
        blueiris:
        host: "http://192.168.195.82:81"
        username: "theo"
        password: "your_password"

        export_root: "videos"

        jobs:
        - camera: "am016-gp02"
            date: 2026-02-08
            start: "12:00:00"
            end: "14:00:00"

---

# Running video export
python bi_interface.py

# Running list cameras and their status
python bi_interface.py --list-cameras


# Performance Notes

reencode=False uses direct-to-disk export (fastest)

reencode=True performs full conversion (slower but sometimes required)

Long clips may require extended polling windows

Export duration depends on clip length and disk throughput

Final Thoughts

What initially appeared to be:

A permissions problem

An authentication problem

An API failure

Turned out to be:

API evolution

Endpoint differences

Export queue mechanics

Windows path normalization issues

Version-specific behavior in 5.9.x

The result is now a stable, version-aligned export pipeline that mirrors the behavior of the Blue Iris Web UI while remaining fully automated and scriptable.

This solution is production-ready and robust against the quirks of modern Blue Iris builds.


---




