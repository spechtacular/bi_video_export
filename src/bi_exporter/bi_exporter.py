"""
Blue Iris Export Pipeline
Concurrent MP4 exporter for Blue Iris (5.9.x compatible)

Features:
- Uses cmd="export" (Convert/Export queue)
- Correctly downloads using returned 'uri'
- Thread-safe export handling
- Robust 503 polling until file ready
- Camera folder initialization
- Clean summary reporting
- Timezone-aware, threaded, queue-driven exporter
- Export de-duplication via JSON tracker file (no SQLite)
- Metrics recording + summary reporting
"""

import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

def setup_logger():
    logger = logging.getLogger("bi_exporter")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s - %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


logger = setup_logger()


# ---------------------------------------------------------
# Timezone Handling
# ---------------------------------------------------------

def convert_to_epoch(date_obj, time_str: str, timezone_name: str) -> int:
    """
    Convert local date + HH:MM:SS to UTC epoch seconds.
    """
    dt_str = f"{date_obj} {time_str}"
    local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    tz = ZoneInfo(timezone_name)
    local_dt = local_dt.replace(tzinfo=tz)
    return int(local_dt.timestamp())


# ---------------------------------------------------------
# Export Tracker (dedupe + metrics)
# ---------------------------------------------------------

class ExportTracker:
    """
    Simple JSON file tracker stored under export_root.
    - Dedup rule: if clip_key has status=success, skip exporting again.
    - Stores recent activity + counters per camera.
    """
    def __init__(self, export_root: str | Path):
        self.export_root = Path(export_root)
        self.path = self.export_root / ".bi_export_tracker.json"
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "version": 1,
                "created_at_utc": int(time.time()),
                "updated_at_utc": int(time.time()),
                "clips": {},          # key -> record
                "events": [],         # recent events (bounded)
                "counters": {
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                },
                "per_camera": {},     # camera -> counters
            }
        try:
            return json.loads(self.path.read_text())
        except Exception:
            # If corrupted, keep a backup and start fresh
            backup = self.path.with_suffix(".json.bak")
            try:
                self.path.rename(backup)
            except Exception:
                pass
            return {
                "version": 1,
                "created_at_utc": int(time.time()),
                "updated_at_utc": int(time.time()),
                "clips": {},
                "events": [],
                "counters": {"success": 0, "failed": 0, "skipped": 0},
                "per_camera": {},
            }

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    @staticmethod
    def clip_key(camera: str, clip_path: str) -> str:
        return f"{camera}|{clip_path}"

    def has_success(self, camera: str, clip_path: str) -> bool:
        key = self.clip_key(camera, clip_path)
        with self._lock:
            rec = self._data["clips"].get(key)
            return bool(rec and rec.get("status") == "success")

    def record(self, camera: str, clip_path: str, status: str, **fields):
        """
        status: success | failed | skipped
        fields: export_id, filename, bytes, error, started_at_utc, finished_at_utc, etc.
        """
        key = self.clip_key(camera, clip_path)
        now = int(time.time())

        with self._lock:
            # clip record
            rec = self._data["clips"].get(key, {})
            rec.update({
                "camera": camera,
                "clip": clip_path,
                "status": status,
                "updated_at_utc": now,
            })
            rec.update(fields)
            self._data["clips"][key] = rec

            # counters
            if status not in ("success", "failed", "skipped"):
                status = "failed"
            self._data["counters"][status] = self._data["counters"].get(status, 0) + 1

            camc = self._data["per_camera"].setdefault(camera, {"success": 0, "failed": 0, "skipped": 0})
            camc[status] = camc.get(status, 0) + 1

            # events (bounded)
            event = {
                "ts_utc": now,
                "camera": camera,
                "clip": clip_path,
                "status": status,
            }
            for k in ("filename", "export_id", "error"):
                if k in fields and fields[k]:
                    event[k] = fields[k]
            self._data["events"].append(event)
            self._data["events"] = self._data["events"][-300:]  # keep last 300

            self._data["updated_at_utc"] = now
            self._save()

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._data))


# ---------------------------------------------------------
# Export Worker
# ---------------------------------------------------------

def export_single_clip(bi_client, tracker: ExportTracker, camera: str, clip: dict, target_dir: Path):
    clip_path = clip["path"]

    # Dedupe: skip if already exported successfully
    if tracker.has_success(camera, clip_path):
        logger.info(f"{camera} → SKIP (already exported) {clip_path}")
        tracker.record(camera, clip_path, "skipped", reason="dedupe_success")
        return {"camera": camera, "clip": clip_path, "status": "skipped", "reason": "already_exported"}

    started = int(time.time())

    try:
        logger.info(f"{camera} → Creating MP4 for {clip_path}")

        export_data = bi_client.create_export(
            path=clip_path,
            format=1,          # MP4
            reencode=True,
            overlay=False,
            audio=True,
        )

        export_id = export_data["path"]
        tracker.record(camera, clip_path, "skipped", started_at_utc=started, export_id=export_id, reason="queued")  # interim marker
        logger.info(f"{camera} → Export queued as {export_id}")

        # Poll export status
        last_status = None
        for _ in range(300):  # 10 minutes @ 2s
            status = bi_client.check_export_status(export_id)
            last_status = status

            state = status.get("status")
            if state == "done":
                uri = status.get("uri")
                if not uri:
                    raise RuntimeError("Export completed but no URI returned")

                # URI example: Clipboard\\cam.2026....mp4
                filename = uri.split("\\")[-1]  # removes Clipboard\
                download_path = f"/clips/{uri.replace('\\', '/')}"

                out_file = target_dir / filename
                bi_client.download_file(download_path, out_file)

                finished = int(time.time())
                tracker.record(
                    camera, clip_path, "success",
                    started_at_utc=started,
                    finished_at_utc=finished,
                    export_id=export_id,
                    filename=filename,
                    uri=uri,
                    filesize=status.get("filesize"),
                )

                logger.info(f"{camera} → Saved {filename}")
                return {"camera": camera, "clip": clip_path, "status": "success", "file": str(out_file)}

            if state == "error":
                raise RuntimeError(status.get("error", "Unknown export error"))

            time.sleep(2)

        raise RuntimeError(f"Export did not reach done status (last={last_status})")

    except Exception as e:
        finished = int(time.time())
        tracker.record(
            camera, clip_path, "failed",
            started_at_utc=started,
            finished_at_utc=finished,
            error=str(e),
        )
        logger.error(f"{camera} → FAILED {clip_path} → {e}")
        return {"camera": camera, "clip": clip_path, "status": "failed", "error": str(e)}


# ---------------------------------------------------------
# Per-Job Export
# ---------------------------------------------------------

def export_clips_for_job(bi_client, tracker: ExportTracker, job: dict, export_root: str | Path, max_workers: int = 4):
    camera = job["camera"]
    date = job["date"]
    start = job["start"]
    end = job["end"]
    timezone = job.get("timezone", "America/Chicago")

    date_str = date.strftime("%Y-%m-%d")
    target_dir = Path(export_root) / camera / date_str
    target_dir.mkdir(parents=True, exist_ok=True)

    start_epoch = convert_to_epoch(date, start, timezone)
    end_epoch = convert_to_epoch(date, end, timezone)

    logger.info(f"{camera} → Searching clips from {start_epoch} to {end_epoch}")

    clips = bi_client.list_clips(camera=camera, start_epoch=start_epoch, end_epoch=end_epoch)

    if not clips:
        logger.warning(f"{camera} → No clips found")
        return []

    logger.info(f"{camera} → Found {len(clips)} clips")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(export_single_clip, bi_client, tracker, camera, clip, target_dir)
            for clip in clips
        ]
        for f in as_completed(futures):
            results.append(f.result())

    return results


# ---------------------------------------------------------
# Export Multiple Jobs
# ---------------------------------------------------------

def export_jobs(bi_client, jobs: list[dict], export_root: str | Path, max_workers: int = 4):
    tracker = ExportTracker(export_root)
    all_results: list[dict] = []

    for job in jobs:
        job_results = export_clips_for_job(
            bi_client=bi_client,
            tracker=tracker,
            job=job,
            export_root=export_root,
            max_workers=max_workers,
        )
        all_results.extend(job_results)

    return all_results


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def print_summary(all_results: list[dict]):
    successes = [r for r in all_results if r["status"] == "success"]
    failures = [r for r in all_results if r["status"] == "failed"]
    skipped = [r for r in all_results if r["status"] == "skipped"]

    logger.info("--------------------------------------------------")
    logger.info(f"Total clips processed: {len(all_results)}")
    logger.info(f"Successful exports:   {len(successes)}")
    logger.info(f"Skipped (dedupe):     {len(skipped)}")
    logger.info(f"Failed exports:       {len(failures)}")

    if failures:
        logger.info("---- Failures ----")
        for f in failures:
            logger.info(f"{f['camera']} | {f['clip']} | {f.get('error','unknown')}")

