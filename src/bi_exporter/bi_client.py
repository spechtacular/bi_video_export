"""
Blue Iris JSON API client
- HTTP Basic + JSON session login
- Uses cmd="export" (Convert/Export queue) for MP4 creation
- Robust, non-recursive session refresh
- Thread-safe
"""

import requests
import hashlib
import threading
from typing import Optional


class BlueIrisClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: int = 30,
    ):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

        self.session_token: Optional[str] = None
        self.http = requests.Session()
        self.http.auth = (self.username, self.password)

        self._auth_lock = threading.Lock()

    # --------------------------------------------------------
    # Internal POST helper
    # --------------------------------------------------------

    def _post(self, payload: dict) -> dict:
        url = f"{self.host}/json"

        r = self.http.post(
            url,
            json=payload,
            timeout=self.timeout,
        )

        if r.status_code == 401:
            raise RuntimeError("HTTP 401 Unauthorized (check credentials)")

        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")

        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response: {r.text[:500]}")

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    def login(self):
        with self._auth_lock:

            # Step 1 — request session
            r1 = self._post({"cmd": "login"})

            if "session" not in r1:
                raise RuntimeError(f"Login step 1 failed: {r1}")

            session = r1["session"]

            # Step 2 — MD5 response hash
            response_hash = hashlib.md5(
                f"{self.username}:{session}:{self.password}".encode()
            ).hexdigest()

            r2 = self._post({
                "cmd": "login",
                "session": session,
                "response": response_hash,
            })

            if r2.get("result") != "success":
                raise RuntimeError(f"Login failed: {r2}")

            self.session_token = r2["session"]

    # --------------------------------------------------------
    # Camera Listing
    # --------------------------------------------------------

    def list_cameras(self):
        self._ensure_login()

        r = self._post({
            "cmd": "camlist",
            "session": self.session_token,
        })

        if r.get("result") != "success":
            raise RuntimeError(f"camlist failed: {r}")

        cameras = []

        for cam in r.get("data", []):
            if "ip" in cam:  # Skip layouts/groups
                cameras.append({
                    "short": cam["optionValue"],
                    "name": cam["optionDisplay"],
                    "ip": cam.get("ip"),
                    "is_enabled": cam.get("isEnabled", False),
                    "is_online": cam.get("isOnline", False),
                })

        return cameras

    # --------------------------------------------------------
    # Clip Listing
    # --------------------------------------------------------

    def list_clips(self, camera: str, start_epoch: int, end_epoch: int):
        self._ensure_login()

        r = self._post({
            "cmd": "cliplist",
            "session": self.session_token,
            "camera": camera,
            "startdate": start_epoch,
            "enddate": end_epoch,
            "view": "stored",
        })

        if r.get("result") != "success":
            raise RuntimeError(f"cliplist failed: {r}")

        return r.get("data", [])

    # --------------------------------------------------------
    # Create Export (Modern BI API)
    # --------------------------------------------------------

    def create_export(
        self,
        path: str,
        format: int = 1,        # 1 = MP4
        reencode: bool = True,
        overlay: bool = False,
        audio: bool = True,
    ):
        self._ensure_login()

        payload = {
            "cmd": "export",
            "session": self.session_token,
            "path": path,
            "format": format,
            "reencode": reencode,
            "overlay": overlay,
            "audio": audio,
        }

        r = self._post(payload)

        if r.get("result") != "success":
            raise RuntimeError(f"Export failed: {r}")

        return r.get("data")

    # --------------------------------------------------------
    # Check Export Status
    # --------------------------------------------------------

    def check_export_status(self, export_id: str):
        self._ensure_login()

        r = self._post({
            "cmd": "export",
            "session": self.sessi

