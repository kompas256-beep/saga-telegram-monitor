import json
import os
from pathlib import Path
from urllib.parse import urljoin

import requests


API_URL = "https://api.parse.bot/scraper/8fe7e14d-e42e-45e8-abd3-c3eb2b016d04/search_offices"
SAGA_BASE = "https://www.saga.hamburg"

STATE_FILE = Path("seen.json")

# Наши критерии
MIN_AREA = 85.0
MAX_RENT = 1361.85


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        return set(json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        ))
    except Exception:
        return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_listings():
    api_key = os.environ["PARSE_API_KEY"]

    response = requests.get(
        API_URL,
        params={"category": "APARTMENT"},
        headers={
            "X-API-Key": api_key,
            "Accept": "application/json",
        },
        timeout=60,
    )

    response.raise_for_status()

    payload = response.json()

    # API возвращает данные внутри "data"
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]

    if isinstance(payload, dict):
        for key in ("listings", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]

    if isinstance(payload, list):
        return payload

    raise RuntimeError(
        f"Неизвестный формат ответа API: {response.json()}"
    )

def number(value):
    if value is None:
        return None

    try:
        return float(
            str(value)
            .replace("€", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
    except ValueError:
        return None


def listing_id(item):
    return (
        item.get("detail_path")
        or item.get("url")
        or item.get("id")
        or item.get("title")
    )


def matches(item):
    area = number(item.get("area_m2"))
    rent = number(item.get("total_rent_eur"))

    if area is None or rent is None:
        return False

    return area >= MIN_AREA and rent <= MAX_RENT


def listing_url(item):
    path = item.get("detail_path") or item.get("url")

    if not path:
        return SAGA_BASE

    return urljoin(SAGA_BASE, path)


def format_message(item):
    title = item.get("title") or "Neue SAGA-Wohnung"
    address = item.get("address") or "Adresse nicht angegeben"

    area = item.get("area_m2")
    rent = item.get("total_rent_eur")
    district = item.get("district")
    available = item.get("available_from")

    lines = [
        f"🏠 <b>{title}</b>",
        f"📍 {address}",
    ]

    if district:
        lines.append(f"🏙️ Stadtteil: {district}")

    if area is not None:
        lines.append(f"📐 Fläche: {area} m²")

    if rent is not None:
        lines.append(f"💶 Gesamtmiete: {rent} €")

    if available:
        lines.append(f"📅 Frei ab: {available}")

    lines.append(
        f'🔗 <a href="{listing_url(item)}">'
        f"SAGA-Anzeige öffnen</a>"
    )

    return "\n".join(lines)


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def main():
    listings = get_listings()
    seen = load_seen()

    current_ids = {
        str(listing_id(item))
        for item in listings
        if listing_id(item)
    }

    # Первый запуск:
    # запоминаем уже существующие квартиры,
    # но НЕ отправляем уведомления на все старые объявления.
    if not STATE_FILE.exists():
        save_seen(current_ids)

        print(
            f"Запомнено существующих объявлений: "
            f"{len(current_ids)}"
        )

        return

    new_matches = []

    for item in listings:
        item_id = listing_id(item)

        if not item_id:
            continue

        item_id = str(item_id)

        if item_id not in seen and matches(item):
            new_matches.append(item)

    for item in new_matches:
        send_telegram(format_message(item))

    # Запоминаем все объявления.
    # Поэтому изменение цены существующей квартиры
    # не будет считаться новой квартирой.
    seen.update(current_ids)
    save_seen(seen)

    print(
        f"Проверено: {len(listings)}, "
        f"новых подходящих: {len(new_matches)}"
    )


if __name__ == "__main__":
    main()
