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

schedule_today = []
schedule_future = []

# "id":
# "name":
# "url_key":
# "image_url":
# "description":
# "follower_num":
# "is_live":
# "is_party":
# "next_live_schedule":


for room_link in data["room_link_n"] + data["room_link_s"] + data["room_link_h"]:
    try:
        print(room_link)
        room_link = f"https://public-api.showroom-cdn.com/room/{room_link}"
        print(f"checking room_link: {room_link}")
        result = requests.get(room_link).json()
        result["download_dispatched"] = False
        if "nekojita" in room_link and "乃木坂" not in result["name"]:
            continue
        if result["is_live"]:
            result["next_live_schedule"] = int(time.time())
            schedule_today.append(result)
        if result["next_live_schedule"]:
            if check_day_relation_jst(result["next_live_schedule"]) == "today":
                schedule_today.append(result)
            else:
                schedule_future.append(result)
    except Exception as e:
        print(e)

print("today", schedule_today)
print("future", schedule_future)

for room in schedule_today + schedule_future:
    timestamp = room["next_live_schedule"]
    time_str = datetime.fromtimestamp(timestamp, tz=jst).strftime("%Y-%m-%d %H:%M")
    send_telegram_message(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        f"{room['name']}\n{time_str}",
    )


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


print("Monitoring")

while True:
    now = datetime.now(jst)
    all_dispatched = True
    for room in schedule_today:
        if room["download_dispatched"]:
            continue
        target_time = datetime.fromtimestamp(
            room["next_live_schedule"], jst
        ) - timedelta(minutes=15)
        if now >= target_time:
            dispatch_download(room["url_key"])
            room["download_dispatched"] = True
        else:
            all_dispatched = False
    if all_dispatched:
        print("all dispatched")
        break
    time.sleep(10)
