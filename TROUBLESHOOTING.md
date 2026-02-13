# Troubleshooting Guide

This document covers common issues encountered when integrating with the Blue Iris 5.9.x JSON API and using this export automation tool.

---

# Table of Contents

- [Authentication Issues](#authentication-issues)
- [Permission Errors](#permission-errors)
- [Export Fails with 404 or 503](#export-fails-with-404-or-503)
- [“Clip not BVR” Error](#clip-not-bvr-error)
- [Export Takes Too Long](#export-takes-too-long)
- [File Saved With `Clipboard\` In Name](#file-saved-with-clipboard-in-name)
- [Curl / PowerShell Differences](#curl--powershell-differences)
- [Remote Desktop Clipboard Issues](#remote-desktop-clipboard-issues)

---

# Authentication Issues

## HTTP 401 Unauthorized

If you see:
    HTTP 401 Unauthorized


Check:

1. Correct host and port (example: `http://192.168.195.82:81`)
2. Correct username/password
3. Web server is enabled in Blue Iris
4. HTTP Basic authentication is allowed

Blue Iris requires:

- HTTP Basic authentication
- JSON login handshake (MD5 challenge/response)

Both are handled in `bi_client.py`.

---

# Permission Errors

## "Access denied" when using `clipcreate`

Modern Blue Iris 5.9.x builds restrict `clipcreate`.

Use:
    cmd="export" 
NOT
    cmd="clipcreate"



The export queue must be used for MP4 generation.

---

# Export Fails with 404 or 503

## 503 from `/file/`

This is incorrect endpoint usage.

Export queue products must be downloaded from:
    /clips/{uri}
NOT
    /file/{filename}


---

## 404 from `/clips/{uri}`

A 404 during polling usually means:

- Export is still processing
- File not yet created

Increase polling duration:

```python
poll_attempts = 600
poll_interval = 2


“Clip not BVR” Error

Occurs when calling:

cmd="export", path="@queue_id"


The returned path from enqueue is a queue record, not a BVR clip.

Do not poll export status via JSON unless necessary.

Instead:

Enqueue export

Poll /clips/{uri}

Export Takes Too Long

If exports are slow:

Check if using:
    reencode=True
Full re-encode is CPU-intensive.

For fastest performance:
    reencode=False

Direct-to-disk export is significantly faster.

Export speed depends on:

Clip duration

Resolution

Disk speed

CPU load

File Saved With Clipboard\ In Name

Blue Iris returns Windows-style paths:
    Clipboard\filename.mp4
On macOS/Linux, \ is not a separator.

Fix:
    uri = uri.replace("\\", "/")
    filename = Path(uri).name

Curl / PowerShell Differences

On Windows:
    curl

is often aliased to Invoke-WebRequest.
Use:
    curl.exe
Or use:

Invoke-RestMethod


Example:
    Invoke-RestMethod `
    -Uri "http://127.0.0.1:81/json" `
    -Method POST `
    -Credential $cred `
    -ContentType "application/json" `
    -Body '{"cmd":"login"}'

Remote Desktop Clipboard Issues

If copy/paste doesn't work in RDP:

On macOS:

Enable clipboard sharing in Microsoft Remote Desktop settings

Restart remote session
    Verifying Export Queue in Blue Iris

Open Blue Iris Console:

Clips → Convert/Export Queue


You should see:

Status: queued / active / done

Progress percentage

If exports appear there, API integration is working.
When All Else Fails

Check:

Web server enabled

Export queue not disabled

User has full admin permissions

No IP auto-ban triggered

Correct endpoint (/clips/)

If exports appear in the UI but not downloadable via API, confirm correct session token is used.