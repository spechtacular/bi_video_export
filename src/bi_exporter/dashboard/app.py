import os
import requests
from datetime import datetime, timezone
from flask import Flask, jsonify

BASE_URL = "https://api.zerotier.com/api/v1"

ONLINE_THRESHOLD = 120        # 2 minutes
STALE_THRESHOLD = 600         # 10 minutes


def calculate_status(last_seen_ms: int):
    if not last_seen_ms:
        return "-", "-", "offline"

    dt = datetime.fromtimestamp(last_seen_ms / 1000, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())

    # Relative time
    if seconds < 60:
        ago = f"{seconds}s ago"
    elif seconds < 3600:
        ago = f"{seconds // 60}m ago"
    elif seconds < 86400:
        ago = f"{seconds // 3600}h ago"
    else:
        ago = f"{seconds // 86400}d ago"

    if seconds <= ONLINE_THRESHOLD:
        state = "online"
    elif seconds <= STALE_THRESHOLD:
        state = "stale"
    else:
        state = "offline"

    return dt.strftime("%Y-%m-%d %H:%M:%S UTC"), ago, state


def create_app():
    app = Flask(__name__)

    ZT_TOKEN = os.environ.get("ZT_TOKEN")
    ZT_NETWORK_ID = os.environ.get("ZT_NETWORK_ID")

    if not ZT_TOKEN or not ZT_NETWORK_ID:
        raise RuntimeError("ZT_TOKEN and ZT_NETWORK_ID must be set")

    @app.route("/api/zt")
    def get_members():
        url = f"{BASE_URL}/network/{ZT_NETWORK_ID}/member"
        headers = {"Authorization": f"bearer {ZT_TOKEN}"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 500

        members = response.json()
        processed = []

        online_count = 0
        stale_count = 0

        for m in members:
            ips = m.get("config", {}).get("ipAssignments", [])
            ip_address = ips[0] if ips else "Unassigned"

            last_seen_raw = m.get("lastSeen", 0)
            last_seen_human, last_seen_ago, state = calculate_status(last_seen_raw)

            if state == "online":
                online_count += 1
            elif state == "stale":
                stale_count += 1

            processed.append({
                "id": m.get("id", "-"),
                "name": m.get("name") or m.get("config", {}).get("name") or "—",
                "ip": ip_address,
                "authorized": m.get("config", {}).get("authorized", False),
                "state": state,
                "lastSeenHuman": last_seen_human,
                "lastSeenAgo": last_seen_ago,
                "lastSeenRaw": last_seen_raw
            })

        # Sort by state priority and recency
        state_priority = {"online": 0, "stale": 1, "offline": 2}

        processed.sort(
            key=lambda x: (
                state_priority.get(x["state"], 3),
                -x["lastSeenRaw"]
            )
        )

        total = len(processed)

        # Network Health Calculation
        if online_count >= total * 0.6:
            health = "good"
        elif online_count > 0:
            health = "degraded"
        else:
            health = "critical"

        return jsonify({
            "summary": {
                "total_nodes": total,
                "online_nodes": online_count,
                "stale_nodes": stale_count,
                "offline_nodes": total - online_count - stale_count,
                "health": health
            },
            "members": processed
        })

    return app

