import requests
import time


def send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    while True:
        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        )
        if response.status_code == 200:
            return True

        print(f"Failed to send message, retrying...")
        time.sleep(5)


def send_telegram_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, file_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    while True:
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"document": f},
            )
        if response.status_code == 200:
            return True

        print(f"Failed to send {file_path}, retrying...")
        time.sleep(5)
