import os
import re
import time
from urllib.parse import urlparse

import pytesseract
import requests
from PIL import Image
from seleniumbase import SB

# ─────────────────────────────────────────────
# НАСТРОЙКИ
# ─────────────────────────────────────────────

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# URL страницы с лотами
MARKET_URL = 'https://lis-skins.com/ru/market/csgo/%E2%98%85-navaja-knife-case-hardened-field-tested/'

# Эталонные blue gem паттерны
BLUE_GEM_PATTERNS = {189, 278, 363, 689, 690, 868, 872}

# Папка для временных скриншотов
IMAGES_DIR = './images'

# Координаты кропа области с номером паттерна на скриншоте
CROP_BOX = (1000, 0, 1400, 150)


# ─────────────────────────────────────────────


def load_blue_gem_patterns(filepath: str) -> set:
    """Загрузить эталонные паттерны из файла."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}


def get_screenshot_url(market_url: str, data_id: str) -> str:
    """
    Строим URL скриншота напрямую из URL маркета и data-id лота.
    Пример: https://ss.lis-skins.com/★-navaja-knife-case-hardened-minimal-wear-409569403.webp
    """
    parsed = urlparse(market_url)
    slug = parsed.path.rstrip('/').split('/')[-1]
    return f"https://ss.lis-skins.com/{slug}-{data_id}.webp"


def recognize_pattern(image_path: str):
    """OCR: вырезаем область с паттерном и распознаём число."""
    try:
        image = Image.open(image_path)
        cropped = image.crop(CROP_BOX)
        text = pytesseract.image_to_string(cropped, config='--psm 7 digits')
        digits = re.findall(r'\d+', text)
        if digits:
            return int(digits[0])
    except Exception as e:
        print(f"  [OCR ERROR] {e}")
    return None


def close_popups(driver):
    """Закрываем рекламный попап и куки через JS."""
    try:
        driver.execute_script(
            "var el = document.querySelector('.popup-window.visible .popup-wrap .popup-close');"
            "if (el) el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));"
        )
        time.sleep(1)
    except Exception:
        pass

    try:
        driver.execute_script(
            "var el = document.querySelector('.cookie-popup__close');"
            "if (el) el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));"
        )
        time.sleep(1)
    except Exception:
        pass


def find_blue_gems():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    found_blue_gems = []

    with SB(
            headed=True,
            undetected=True,
            maximize=True,
            ad_block=True,
            headless=False,
            skip_js_waits=True,
    ) as driver:

        print(f"[*] Открываю страницу: {MARKET_URL}")
        driver.open(MARKET_URL)
        time.sleep(3)

        close_popups(driver)

        # Собираем data-id всех лотов
        elements = driver.find_elements(".item.row.market_item")
        print(f"[*] Найдено лотов: {len(elements)}")

        lot_ids = []
        for element in elements:
            data_id = element.get_attribute("data-id")
            if data_id:
                lot_ids.append(data_id)
            else:
                print("  [WARN] Лот без data-id, пропускаю")

        print(f"[*] Собрано data-id: {lot_ids}\n")

    # Браузер закрыт — дальше работаем только через requests
    for index, data_id in enumerate(lot_ids):
        lot_url = f"{MARKET_URL.rstrip('/')}/{data_id}/"
        screenshot_url = get_screenshot_url(MARKET_URL, data_id)

        print(f"[{index + 1}/{len(lot_ids)}] data-id: {data_id}")
        print(f"  Лот:       {lot_url}")
        print(f"  Скриншот:  {screenshot_url}")

        # Скачиваем скриншот напрямую
        image_path = os.path.join(IMAGES_DIR, f"pattern_{data_id}.webp")
        try:
            resp = requests.get(screenshot_url, timeout=15)
            resp.raise_for_status()
            with open(image_path, 'wb') as f:
                f.write(resp.content)
        except Exception as e:
            print(f"  [ERROR] Не удалось скачать скриншот: {e}")
            continue

        # OCR
        pattern = recognize_pattern(image_path)
        print(f"  Паттерн:   {pattern}")

        if pattern is not None and pattern in BLUE_GEM_PATTERNS:
            print(f"  ✅ BLUE GEM! Паттерн {pattern} → {lot_url}")
            found_blue_gems.append({'pattern': pattern, 'url': lot_url})
        else:
            print(f"  ✗ Not blue gem")

    print("\n" + "=" * 50)
    if found_blue_gems:
        print(f"Найдено Blue Gem: {len(found_blue_gems)}\n")
        for item in found_blue_gems:
            print(f"  Паттерн {item['pattern']:>4} → {item['url']}")
    else:
        print("Blue Gem скинов не найдено.")
    print("=" * 50)

    return found_blue_gems


if __name__ == '__main__':
    # Если хочешь грузить паттерны из файла, раскомментируй:
    # BLUE_GEM_PATTERNS = load_blue_gem_patterns('navaja_blue_gem.txt')

    find_blue_gems()
