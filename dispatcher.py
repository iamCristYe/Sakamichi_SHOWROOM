import os
import requests
import json
from datetime import datetime, timedelta
import pytz
from telegram import send_telegram_message, send_telegram_file
import time

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
TARGET_REPO = os.getenv("TARGET_REPO")

API_URL = f"https://api.github.com/repos/{TARGET_REPO}/dispatches"


def check_day_relation_jst(timestamp: int) -> str:

    jst = pytz.timezone("Asia/Tokyo")

    target_date = datetime.fromtimestamp(timestamp, jst).date()

    today_date = datetime.now(jst).date()

    if target_date == today_date:
        return "today"
    else:
        return "future"


with open("data.json", "r") as f:
    data = json.load(f)
    print(data)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = data["channel_id"]
jst = pytz.timezone("Asia/Tokyo")
# https://campaign.showroom-live.com/nogizaka46_sr/data/rooms.json
# https://public-api.showroom-cdn.com/room/46_sugawarasatsuki

all_links = data["room_link_n"] + data["room_link_s"] + data["room_link_h"]

def dispatch_download(url_key):
    payload = {
        "event_type": "trigger-download",
        "client_payload": {"url_key": str(url_key)},
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    print(f"[DISPATCH] {url_key} - Status:", response.status_code)

known_schedules = {}
dispatched_schedules = set()

script_start_time = datetime.now(jst)
last_fetch_time = None

print("Monitoring for 5 hours, fetching API every 15 minutes...")

while True:
    now = datetime.now(jst)
    
    if (now - script_start_time).total_seconds() >= 5 * 3600:
        print("5 hours have passed. Exiting dispatcher.")
        break

    if last_fetch_time is None or (now - last_fetch_time).total_seconds() >= 15 * 60:
        last_fetch_time = now
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Fetching schedules from API...")
        
        for room_link in all_links:
            try:
                room_api = f"https://public-api.showroom-cdn.com/room/{room_link}"
                result = requests.get(room_api).json()
                
                if "nekojita" in room_api and "乃木坂" not in result.get("name", ""):
                    continue
                    
                url_key = result.get("url_key", room_link)
                
                ts = None
                if result.get("is_live"):
                    ts = "LIVE"
                elif result.get("next_live_schedule"):
                    ts = result["next_live_schedule"]
                    
                if ts:
                    if known_schedules.get(url_key) != ts:
                        known_schedules[url_key] = ts
                        
                        if ts == "LIVE":
                            time_str = "LIVE NOW"
                        else:
                            time_str = datetime.fromtimestamp(ts, tz=jst).strftime("%Y-%m-%d %H:%M")
                            
                        print(f"[NEW SCHEDULE/LIVE] {result.get('name', url_key)}: {time_str}")
                        send_telegram_message(
                            TELEGRAM_BOT_TOKEN,
                            TELEGRAM_CHAT_ID,
                            f"{result.get('name', url_key)}\n{time_str}",
                        )
            except Exception as e:
                print(f"Error checking {room_link}: {e}")

    # Dispatch check loop
    for url_key, ts in known_schedules.items():
        dispatch_key = (url_key, ts)
        if dispatch_key in dispatched_schedules:
            continue
            
        should_dispatch = False
        if ts == "LIVE":
            should_dispatch = True
        else:
            target_time = datetime.fromtimestamp(ts, jst) - timedelta(minutes=15)
            if now >= target_time:
                should_dispatch = True
                
        if should_dispatch:
            dispatch_download(url_key)
            dispatched_schedules.add(dispatch_key)
            
    time.sleep(10)
