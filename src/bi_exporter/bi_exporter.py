"""
Concurrent MP4 exporter for Blue Iris (5.9.x compatible)

Features:
- Uses cmd="export" (Convert/Export queue)
- Correctly downloads using returned 'uri'
- Thread-safe export handling
- Robust 503 polling until file ready
- Camera folder initialization
- Clean summary reporting
"""

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
import time
from typing import Dict, List, Any


# ---------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------

def setup_logger():
    logger = logging.getLogger("bi_exporter")

    if logger.handlers:
        return logger  # prevent duplicate handlers

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(threadName)s - %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = logging.FileHandler("bi_export.log")
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
progress_lock = threading.Lock()


# ---------------------------------------------------------
# Camera Folder Initialization
# ---------------------------------------------------------

def create_camera_folders(bi_client, export_root: str) -> List[str]:
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)

    cameras = bi_client.list_cameras()
    created = []

    for cam in cameras:
        short = cam["short"]
        folder = root / short
        folder.mkdir(parents=True, exist_ok=True)
        created.append(str(folder))

    logger.info(f"Created {len(created)} camera folders.")
    return created


# ---------------------------------------------------------
# Export Worker
# ---------------------------------------------------------

def export_single_clip(
    bi_client,
    camera: str,
    clip: Dict[str, Any],
    target_dir: Path,
    poll_attempts: int = 600,
    poll_interval: float = 3.0,
) -> Dict[str, Any]:

    clip_id = clip["path"]

    try:
        logger.info(f"{camera} → Creating MP4 for {clip_id}")

        # Enqueue export
        export_data = bi_client.enqueue_export(
            clip_record=clip_id,
            format_code=1,   # MP4
            reencode=False,  # FAST direct-to-disk
            audio=True,
            overlay=False,
        )

        uri = export_data.get("uri")
        if not uri:
            raise RuntimeError(f"No URI returned (data={export_data!r})")

        uri = uri.replace("\\", "/")
        filename = Path(uri).name
        out_file = target_dir / filename

        download_url = (
            f"{bi_client.host}/clips/{uri}"
            f"?session={bi_client.session_token}"
        )

        last_status = None

        for _ in range(poll_attempts):
            r = bi_client.http.get(download_url, stream=True, timeout=bi_client.timeout)
            last_status = r.status_code

            if r.status_code == 200:
                with open(out_file, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)

                logger.info(f"{camera} → Saved {filename}")
                return {"camera": camera, "clip": clip_id, "status": "success"}

            r.close()
            time.sleep(poll_interval)

        raise RuntimeError(
            f"Export never became available (last HTTP {last_status})"
        )

    except Exception as e:
        logger.error(f"{camera} → FAILED {clip_id} → {e}")
        return {
            "camera": camera,
            "clip": clip_id,
            "status": "failed",
            "error": str(e),
        }



# ---------------------------------------------------------
# Export Clips For One Job
# ---------------------------------------------------------

def export_clips_for_job(
    bi_client,
    job: Dict[str, Any],
    export_root: str,
    executor: ThreadPoolExecutor,
) -> List[Dict[str, Any]]:

    camera = job["camera"]
    date = job["date"]
    start = job["start"]
    end = job["end"]

    date_str = date.strftime("%Y-%m-%d")
    target_dir = Path(export_root) / camera / date_str
    target_dir.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.strptime(
        f"{date.strftime('%Y-%m-%d')} {start}",
        "%Y-%m-%d %H:%M:%S",
    )

    end_dt = datetime.strptime(
        f"{date.strftime('%Y-%m-%d')} {end}",
        "%Y-%m-%d %H:%M:%S",
    )

    start_epoch = int(start_dt.astimezone(timezone.utc).timestamp())
    end_epoch = int(end_dt.astimezone(timezone.utc).timestamp())

    logger.info(
        f"{camera} → Searching clips from {start_epoch} to {end_epoch}"
    )

    clips = bi_client.list_clips(
        camera=camera,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
    )

    if not clips:
        logger.warning(f"{camera} → No clips found")
        return []

    logger.info(f"{camera} → Found {len(clips)} clips")

    futures = [
        executor.submit(
            export_single_clip,
            bi_client,
            camera,
            clip,
            target_dir,
        )
        for clip in clips
    ]

    results = []
    for future in as_completed(futures):
        results.append(future.result())

    return results


# ---------------------------------------------------------
# Export Multiple Jobs
# ---------------------------------------------------------

def export_jobs(
    bi_client,
    jobs: List[Dict[str, Any]],
    export_root: str,
    max_workers: int = 4,
) -> List[Dict[str, Any]]:

    all_results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for job in jobs:
            results = export_clips_for_job(
                bi_client=bi_client,
                job=job,
                export_root=export_root,
                executor=executor,
            )
            all_results.extend(results)

    return all_results


# ---------------------------------------------------------
# Summary Printer
# ---------------------------------------------------------

def print_summary(all_results: List[Dict[str, Any]]):

    successes = [r for r in all_results if r["status"] == "success"]
    failures = [r for r in all_results if r["status"] == "failed"]

    logger.info("--------------------------------------------------")
    logger.info(f"Total clips processed: {len(all_results)}")
    logger.info(f"Successful exports:   {len(successes)}")
    logger.info(f"Failed exports:       {len(failures)}")

    if failures:
        logger.info("---- Failures ----")
        for f in failures:
            logger.info(
                f"{f['camera']} | {f['clip']} | {f.get('error','unknown')}"
            )
