"""
Blue Iris Export Interface

CLI entrypoint for:
- Listing cameras
- Initializing camera folders
- Listing clips by camera/time range
- Running export jobs

Designed for macOS/Linux clients connecting to a Windows Blue Iris server.
"""

import argparse
from datetime import datetime

from load_config import load_config
from bi_client import BlueIrisClient
from bi_exporter import (
    export_jobs,
    print_summary,
    create_camera_folders,
)


# ---------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Blue Iris Export Tool"
    )

    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="List available Blue Iris camera short names and exit",
    )

    parser.add_argument(
        "--init-cameras",
        action="store_true",
        help="Create subdirectories for all cameras under export_root and exit",
    )

    parser.add_argument(
        "--list-clips",
        type=str,
        help="List clips for specified camera short name",
    )

    parser.add_argument(
        "--date",
        type=str,
        help="Date in YYYY-MM-DD format (required for --list-clips)",
    )

    parser.add_argument(
        "--start",
        type=str,
        help="Start time HH:MM:SS (required for --list-clips)",
    )

    parser.add_argument(
        "--end",
        type=str,
        help="End time HH:MM:SS (required for --list-clips)",
    )

    return parser.parse_args()


# ---------------------------------------------------------
# Helper: Convert Local Time → Epoch Seconds
# ---------------------------------------------------------

def local_to_epoch(date_str: str, time_str: str) -> int:
    """
    Convert YYYY-MM-DD and HH:MM:SS (24-hour)
    into epoch seconds using local system timezone.
    """
    dt = datetime.strptime(
        f"{date_str} {time_str}",
        "%Y-%m-%d %H:%M:%S",
    )

    # On macOS/Linux, naive datetime.timestamp()
    # interprets time as local time and converts to UTC epoch correctly.
    return int(dt.timestamp())


# ---------------------------------------------------------
# Main Entry
# ---------------------------------------------------------

def main():
    args = parse_args()
    cfg = load_config("config/export_jobs.yaml")

    bi = BlueIrisClient(
        host=cfg["blueiris"]["host"],
        username=cfg["blueiris"]["username"],
        password=cfg["blueiris"]["password"],
    )

    # -----------------------------------------------------
    # List Cameras
    # -----------------------------------------------------
    if args.list_cameras:
        cameras = bi.list_cameras()

        print("\nAvailable Cameras:\n")
        print(f"{'SHORT NAME':15} {'ENABLED':8} {'ONLINE':8} {'IP':15} NAME")
        print("-" * 75)

        for cam in sorted(cameras, key=lambda c: c["short"]):
            enabled = "Yes" if cam["is_enabled"] else "No"
            online = "Yes" if cam["is_online"] else "No"

            print(
                f"{cam['short']:15} "
                f"{enabled:8} "
                f"{online:8} "
                f"{cam['ip']:15} "
                f"{cam['name']}"
            )

        print()
        return

    # -----------------------------------------------------
    # Initialize Camera Folders
    # -----------------------------------------------------
    if args.init_cameras:
        print("Creating camera folders...\n")

        created = create_camera_folders(
            bi_client=bi,
            export_root=cfg["export_root"],
        )

        print(f"Created/verified {len(created)} camera directories:\n")

        for folder in created:
            print(f"  {folder}")

        print("\nDone.\n")
        return

    # -----------------------------------------------------
    # List Clips
    # -----------------------------------------------------
    if args.list_clips:

        if not args.date or not args.start or not args.end:
            print("Error: --date, --start, and --end are required with --list-clips")
            return

        camera = args.list_clips

        try:
            start_epoch = local_to_epoch(args.date, args.start)
            end_epoch = local_to_epoch(args.date, args.end)
        except ValueError:
            print("Invalid date/time format. Use YYYY-MM-DD and HH:MM:SS")
            return

        if end_epoch <= start_epoch:
            print("End time must be after start time.")
            return

        clips = bi.list_clips(
            camera=camera,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
        )

        if not clips:
            print("\nNo clips found.\n")
            return

        print(f"\nClips for {camera}:\n")
        print(f"{'PATH':20} {'START (LOCAL)':19} {'DURATION':10} {'RESOLUTION':10}")
        print("-" * 75)

        for clip in clips:
            start_epoch = clip.get("date")
            duration_ms = clip.get("msec", 0)
            resolution = clip.get("res", "N/A")

            # Convert epoch to local readable time
            if start_epoch:
                start_local = datetime.fromtimestamp(start_epoch).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            else:
                start_local = "N/A"

            # Convert milliseconds → HH:MM:SS
            total_seconds = int(duration_ms / 1000)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"

            print(
                f"{clip.get('path','N/A'):20} "
                f"{start_local:19} "
                f"{duration_str:10} "
                f"{resolution:10}"
            )


        print()
        return

    # -----------------------------------------------------
    # Run Export Jobs
    # -----------------------------------------------------
    all_results = export_jobs(
        bi_client=bi,
        jobs=cfg["jobs"],
        export_root=cfg["export_root"],
        max_workers=4,
    )

    print_summary(all_results)


# ---------------------------------------------------------
# Script Execution
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
