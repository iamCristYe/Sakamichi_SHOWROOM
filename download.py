import os
import requests
import json
from datetime import datetime, timedelta
import pytz
from telegram import send_telegram_message, send_telegram_file
import time
import subprocess
import threading

with open("data.json", "r") as f:
    data = json.load(f)
    print(data)


# JSON 文件存储每个文件的状态（首次出现时间 + 是否已发送）
SENT_JSON_FILE = "sent.json"
url_key = os.getenv("url_key")

if url_key in data["room_link_n"]:
    channel_id = data["channel_id_n"]
elif url_key in data["room_link_s"]:
    channel_id = data["channel_id_s"]
elif url_key in data["room_link_h"]:
    channel_id = data["channel_id_h"]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = channel_id

room_link = f"https://public-api.showroom-cdn.com/room/{url_key}"
room_link_result = requests.get(room_link).json()
api_link = f"https://www.showroom-live.com/api/live/streaming_url?room_id={room_link_result['id']}"

jst = pytz.timezone("Asia/Tokyo")
today_str = datetime.now(jst).strftime("%Y%m%d")


def retry_command_until_success(command, max_retries=10, retry_interval=5):
    for attempt in range(1, max_retries + 1):
        print(f"[Thread] Attempt {attempt}: Running command...")
        process = subprocess.Popen(command, shell=True)
        process.wait()
        if process.returncode == 0:
            print("[Thread] Command succeeded.")
            return
        else:
            print(
                f"[Thread] Failed with return code {process.returncode}. Retrying in {retry_interval}s..."
            )
            time.sleep(retry_interval)
    print("[Thread] Max retries reached. Command failed.")


def run_ffmpeg():
    ffmpeg_command = f"ffmpeg -i chunklist.ts -map 0:v -map 0:a -c copy -segment_time 10 -f segment -reset_timestamps 1 {url_key}_{today_str}_%08d.mp4"

    print(f"Running FFmpeg command:\n{ffmpeg_command}\n")

    try:
        subprocess.run(
            ffmpeg_command,
            shell=True,  # 必须为 True 才能使用字符串命令
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("FFmpeg error output:")
        print(e.stderr.decode())
        time.sleep(10)


def load_sent_status():
    """加载 sent.json 数据结构"""
    if os.path.exists(SENT_JSON_FILE):
        with open(SENT_JSON_FILE, "r") as f:
            return json.load(f)
    return {}


def save_sent_status(status_dict):
    """保存文件状态到 sent.json"""
    with open(SENT_JSON_FILE, "w") as f:
        json.dump(status_dict, f, indent=4)


def process_files():
    """处理并发送符合条件的 MP4 文件"""
    status = load_sent_status()
    now = time.time()

    # 查找所有还存在于文件夹的 output mp4
    all_files = sorted(
        [f for f in os.listdir() if f.startswith(url_key) and f.endswith(".mp4")]
    )

    # 更新状态字典中未记录的文件，记录首次发现时间和是否已发送
    for f in all_files:
        if f not in status:
            status[f] = {"first_seen": now, "sent": False}

    # 找出未发送的文件
    unsent_files = [f for f in all_files if not status.get(f, {}).get("sent", False)]

    # 分离最后五个
    if len(unsent_files) > 5:
        base_files = unsent_files[:-5]
        tail_files = unsent_files[-5:]
    else:
        base_files = []
        tail_files = unsent_files

    files_to_send = list(base_files)  # 确保复制

    # 添加尾部文件：如果 first_seen 时间超过 180 秒
    for f in tail_files:
        first_seen = status[f]["first_seen"]
        if now - first_seen > 180:
            files_to_send.append(f)

    # 发送文件
    for file_name in files_to_send:
        if not status[file_name]["sent"]:
            if send_telegram_file(
                TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, file_name, file_name
            ):
                print(f"Sent: {file_name}")
                status[file_name]["sent"] = True

    save_sent_status(status)


if __name__ == "__main__":
    while True:
        try:
            m3u8_result = requests.get(api_link).json()
            m3u8_url = m3u8_result["streaming_url_list"][0]["url"].replace("_abr", "")
            break
        except:
            time.sleep(5)
    # m3u8_url = "https://hls-css.live.showroom-live.com/live/fa7a599bf2d0cfb709f1ff63de75430457dc75c1ce543c3bdcc40ce4be92dbd8.m3u8".replace(
    #     "_abr", ""
    # )
    command = f'./N_m3u8DL-RE --live-real-time-merge "{m3u8_url}" --save-name chunklist'
    t = threading.Thread(target=retry_command_until_success, args=(command, 30, 10))
    t.start()

    process = subprocess.Popen(command, shell=True)
    while True:
        subprocess.run("ls", shell=True)

        run_ffmpeg()
        process_files()
        # time.sleep(30)
