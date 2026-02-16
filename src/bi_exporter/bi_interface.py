import argparse
from concurrent.futures import ThreadPoolExecutor

from load_config import load_config
from bi_client import BlueIrisClient
from bi_exporter import export_jobs, print_summary
from bi_scheduler import build_weekend_jobs


def parse_args():
    parser = argparse.ArgumentParser(description="Blue Iris Export Tool")

    parser.add_argument("--list-cameras", action="store_true")

    # Weekend scheduler mode
    parser.add_argument("--weekend", action="store_true")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--cameras")

    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config("config/export_jobs.yaml")

    bi = BlueIrisClient(
        cfg["blueiris"]["host"],
        cfg["blueiris"]["username"],
        cfg["blueiris"]["password"]
    )

    bi.login()

    if args.list_cameras:
        cameras = bi.list_cameras()
        print("\nAvailable Cameras:\n")
        for cam in cameras:
            print(f"{cam['short']} | {cam['name']} | "
                  f"Enabled={cam['is_enabled']} | "
                  f"Online={cam['is_online']}")
        return

    # ---------------------------------------------------
    # WEEKEND MODE
    # ---------------------------------------------------

    if args.weekend:

        if not args.start_date or not args.end_date or not args.cameras:
            raise RuntimeError(
                "--weekend requires --start-date, --end-date, and --cameras"
            )

        cameras = [c.strip() for c in args.cameras.split(",")]

        jobs = build_weekend_jobs(
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            cameras=cameras,
            timezone=cfg.get("timezone", "America/Chicago")
        )

        print(f"\nGenerated {len(jobs)} weekend jobs\n")

    else:
        jobs = cfg["jobs"]

    # ---------------------------------------------------
    # Run Export Pipeline
    # ---------------------------------------------------

    with ThreadPoolExecutor(max_workers=cfg.get("max_workers", 4)) as executor:
        all_results = export_jobs(
            bi_client=bi,
            jobs=jobs,
            export_root=cfg["export_root"],
        )

    print_summary(all_results)


if __name__ == "__main__":
    main()

