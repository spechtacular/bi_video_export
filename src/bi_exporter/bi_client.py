"""
Blue Iris JSON API client
- HTTP Basic + JSON session login
- Uses cmd="export" (Convert/Export queue) for MP4 creation
- Robust, non-recursive session refresh
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth


class BlueIrisClient:
    def __init__(self, host: str, username: str, password: str, timeout: int = 15):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

        self.http = requests.Session()
        self.http.auth = HTTPBasicAuth(self.username, self.password)

        self.session_token: Optional[str] = None

    # -----------------------------
    # Login handshake
    # -----------------------------

    def login(self) -> None:
        # Step 1: request session
        r1 = self.http.post(f"{self.host}/json", json={"cmd": "login"}, timeout=self.timeout)
        if r1.status_code == 401:
            raise RuntimeError("HTTP 401 Unauthorized during login step 1 (check credentials)")
        if r1.status_code != 200:
            raise RuntimeError(f"Login step 1 HTTP {r1.status_code}: {r1.text[:300]}")

        data1 = r1.json()
        session = data1.get("session")
        if not session:
            raise RuntimeError(f"Login step 1 failed: {data1}")

        # Step 2: MD5(username:session:password)
        raw = f"{self.username}:{session}:{self.password}"
        response_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

        r2 = self.http.post(
            f"{self.host}/json",
            json={"cmd": "login", "session": session, "response": response_hash},
            timeout=self.timeout,
        )
        if r2.status_code == 401:
            raise RuntimeError("HTTP 401 Unauthorized during login step 2 (check credentials)")
        if r2.status_code != 200:
            raise RuntimeError(f"Login step 2 HTTP {r2.status_code}: {r2.text[:300]}")

        data2 = r2.json()
        if data2.get("result") != "success":
            raise RuntimeError(f"Login failed: {data2}")

        self.session_token = data2.get("session") or session

    def _ensure_logged_in(self) -> None:
        if not self.session_token:
            self.login()

    # -----------------------------
    # JSON POST with 1 refresh retry
    # -----------------------------

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_logged_in()

        for _ in range(2):  # try, then refresh session once if needed
            body = dict(payload)
            body["session"] = self.session_token

            r = self.http.post(f"{self.host}/json", json=body, timeout=self.timeout)

            if r.status_code == 401:
                # Basic auth failed or server wants auth again
                raise RuntimeError("HTTP 401 Unauthorized (check credentials / web server auth)")

            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")

            data = r.json()

            # Refresh only on explicit invalid-session style failures
            reason = ""
            if isinstance(data.get("data"), dict):
                reason = str(data["data"].get("reason", "")).lower()

            if data.get("result") == "fail" and ("invalid session" in reason or "session" in reason):
                self.login()
                continue

            return data

        raise RuntimeError("Request failed after session refresh retry")

    # -----------------------------
    # API methods
    # -----------------------------

    def list_clips(self, camera: str, start_epoch: int, end_epoch: int) -> List[Dict[str, Any]]:
        r = self._post(
            {
                "cmd": "cliplist",
                "camera": camera,
                "startdate": start_epoch,
                "enddate": end_epoch,
                "view": "stored",
            }
        )
        if r.get("result") != "success":
            raise RuntimeError(f"cliplist failed: {r}")
        return r.get("data", []) or []

    def list_cameras(self) -> List[Dict[str, Any]]:
        r = self._post({"cmd": "camlist"})
        if r.get("result") != "success":
            raise RuntimeError(f"camlist failed: {r}")

        cameras: List[Dict[str, Any]] = []
        for cam in r.get("data", []) or []:
            if "ip" in cam:  # real cameras only
                cameras.append(
                    {
                        "short": cam.get("optionValue"),
                        "name": cam.get("optionDisplay"),
                        "ip": cam.get("ip"),
                        "is_enabled": cam.get("isEnabled", False),
                        "is_online": cam.get("isOnline", False),
                    }
                )
        return cameras

    # -----------------------------
    # Export queue (cmd="export")
    # -----------------------------

    def enqueue_export(
        self,
        *,
        clip_record: str,
        startms: Optional[int] = None,
        msec: Optional[int] = None,
        audio: bool = True,
        overlay: bool = False,
        format_code: int = 1,  # 1 = MP4
        profile: Optional[int] = None,
        reencode: bool = True,
        timelapse: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates an export item in BI's Convert/Export queue.
        Returns BI's response data; typically includes a 'path' to the export item.
        """
        payload: Dict[str, Any] = {
            "cmd": "export",
            "path": clip_record,   # "@record"
            "audio": audio,
            "overlay": overlay,
            "format": format_code,  # 1 = MP4
            "reencode": reencode,
        }
        if startms is not None:
            payload["startms"] = int(startms)
        if msec is not None:
            payload["msec"] = int(msec)
        if profile is not None:
            payload["profile"] = int(profile)
        if timelapse is not None:
            payload["timelapse"] = timelapse

        r = self._post(payload)
        if r.get("result") != "success":
            raise RuntimeError(f"export enqueue failed: {r}")

        return r.get("data") or {}

    def export_status(self, export_path: str) -> Dict[str, Any]:
        """
        Query status of a single export item.
        """
        r = self._post({"cmd": "export", "path": export_path})
        if r.get("result") != "success":
            raise RuntimeError(f"export status failed: {r}")
        return r.get("data") or {}

    # -----------------------------
    # Download helper
    # -----------------------------

    def download_file_when_ready(
        self,
        *,
        filename_or_path: str,
        output_path: Path,
        poll_attempts: int = 30,
        poll_interval: float = 2.0,
    ) -> None:
        """
        Polls /file/<name>?session=... until available then downloads.
        filename_or_path may be 'New\\xyz.mp4' or just 'xyz.mp4'.
        """
        self._ensure_logged_in()

        filename = Path(filename_or_path).name
        url = f"{self.host}/file/{filename}?session={self.session_token}"

        last_status = None
        for _ in range(poll_attempts):
            r = self.http.get(url, stream=True, timeout=self.timeout)
            last_status = r.status_code

            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                return

            r.close()
            time.sleep(poll_interval)

        raise RuntimeError(f"Export never became available for download (last HTTP {last_status})")
