from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from typing import List, Dict


def generate_weekend_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() in (4, 5, 6):  # Fri/Sat/Sun
            dates.append(current)
        current += timedelta(days=1)
    return dates


def build_weekend_jobs(
    start_date_str: str,
    end_date_str: str,
    cameras: List[str],
    timezone: str,
    start_time: str = "18:00:00",
    end_time: str = "23:00:00",
) -> List[Dict]:

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    weekend_dates = generate_weekend_dates(start_date, end_date)

    jobs = []

    for day in weekend_dates:
        for camera in cameras:
            jobs.append({
                "camera": camera,
                "date": day.date(),
                "start": start_time,
                "end": end_time,
                "timezone": timezone,
            })

    return jobs

