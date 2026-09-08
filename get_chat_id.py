import os
import requests

token = os.environ["TELEGRAM_BOT_TOKEN"]

data = requests.get(
    f"https://api.telegram.org/bot{token}/getUpdates",
    timeout=30
).json()

print(data)
