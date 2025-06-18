import requests
import time
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
import os
from datetime import datetime, timezone, timedelta
import json
import csv
import pandas as pd
import re
from urllib.parse import quote




def determining_currenttime():
    return datetime.now(timezone.utc)


# === Загрузка исторических данных ===
def load_data(hours_back):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    delta = now - timedelta(hours=hours_back)
    folder_path = "C:/Users/user/Desktop/gifts_exports"
    data = []

    if not os.path.exists(folder_path):
        return pd.DataFrame()

    for file in os.listdir(folder_path):
        if not file.endswith('.csv'):
            continue

        time_str = file.replace(".csv", "").replace("gifts_", "").strip()
        try:
            file_time = datetime.strptime(time_str, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc)

            if delta <= file_time <= now:
                df = pd.read_csv(os.path.join(folder_path, file))
                data.append(df)
        except ValueError:
            continue

    if data:
        all_data = pd.concat(data, ignore_index=True)
        return all_data
    return pd.DataFrame()


# === Создание JSON для веб-интерфейса ===
def create_web_data():
        # Загружаем данные за последний месяц для полной аналитики
        df = load_data(24 * 30)  # 30 дней

        if df.empty:
            print("[!] Нет данных для создания веб-файла")
            return

        # Преобразуем время из строки в datetime
        df['SnapshotTime'] = pd.to_datetime(df['SnapshotTime'])

        # Группируем данные по коллекциям и моделям
        web_data = {
            "metadata": {
                "last_update": determining_currenttime().isoformat(),
                "data_range_hours": 24 * 30,
                "total_records": len(df)
            },
            "collections": {}
        }

        # Группируем по коллекциям и моделям
        for collection in df['Collection'].unique():
            collection_data = df[df['Collection'] == collection].copy()  # <--- Добавил .copy() для безопасности

            if collection_data.empty:
                print(f"[*] Пропускаем коллекцию '{collection}' из-за отсутствия данных.")
                continue

            processed_collection_name_for_url = quote(collection.lower())
            collection_url_begining = f"https://gifts.coffin.meme/{processed_collection_name_for_url}/"

            collection_image_url = ""
            if not collection_data.empty:
                first_model_name = collection_data['Model'].iloc[0]
                cleaned_first_model_name = re.sub(r'\s*\(.*\)\s*', '', first_model_name).strip()
                first_model_name_for_url_encoded = quote(cleaned_first_model_name)
                collection_image_url = f"{collection_url_begining}{first_model_name_for_url_encoded}.png"

            web_data["collections"][collection] = {
                "collection_image_url": collection_image_url,
                "models": {}
            }

            # Временный список для сбора цен моделей в текущей коллекции для floorPrice коллекции
            current_collection_model_floor_prices = []  # <--- ДОБАВЛЕНО ДЛЯ collection_floorPrice

            for model in collection_data['Model'].unique():
                model_data = collection_data[collection_data['Model'] == model].copy()
                model_data = model_data.sort_values('SnapshotTime')

                if model_data.empty:
                    print(f"[*] Пропускаем модель '{model}' в коллекции '{collection}' из-за отсутствия данных.")
                    continue

                latest = model_data.iloc[-1]

                history = []
                for _, row in model_data.iterrows():
                    history.append({
                        "time": row['SnapshotTime'].isoformat(),
                        "price": float(row['Price']) if pd.notna(row['Price']) else 0.0,  # <--- Явно 0.0
                        "priceWithCommission": float(row['PriceWithCommission']) if pd.notna(
                            row['PriceWithCommission']) else 0.0,  # <--- Явно 0.0
                        "quantity": int(row['Quantity']) if pd.notna(row['Quantity']) else 0
                    })

                cleaned_model_name = re.sub(r'\s*\(.*\)\s*', '', model).strip()
                processed_model_name_for_url = quote(cleaned_model_name)
                model_full_image_url = f"{collection_url_begining}{processed_model_name_for_url}.png"
                changes = calculate_changes(model_data)

                model_current_floor_price = float(latest['Price']) if pd.notna(latest['Price']) else 0.0

                web_data["collections"][collection]["models"][model] = {
                    "model_image_url": model_full_image_url,
                    "current": {
                        "floorPrice": model_current_floor_price,  # <--- ИСПОЛЬЗУЕМ ПЕРЕМЕННУЮ
                        "priceWithComission": float(latest['PriceWithCommission']) if pd.notna(
                            latest['PriceWithCommission']) else 0.0,
                        "howMany": int(latest['Quantity']) if pd.notna(latest['Quantity']) else 0,
                        "lastUpdate": latest['SnapshotTime'].isoformat()
                    },
                    "changes": changes,
                    "history": history
                }
                current_collection_model_floor_prices.append(model_current_floor_price)  # <--- ДОБАВЛЕНО

            # Расчет и добавление collection_floorPrice
            collection_floor_price = float('inf')
            if current_collection_model_floor_prices:
                # Отфильтруем 0.0, если они не должны влиять на минимальное значение
                # Или просто найдем минимум из всех, включая 0.0, если 0.0 - это валидная цена
                non_zero_prices = [p for p in current_collection_model_floor_prices if p > 0]
                if non_zero_prices:
                    collection_floor_price = min(non_zero_prices)
                else:
                    collection_floor_price = 0.0  # Если все цены 0, то мин. цена 0
            else:
                collection_floor_price = 0.0

            web_data["collections"][collection]["collection_floorPrice"] = collection_floor_price  # <--- ДОБАВЛЕНО ПОЛЕ

        # Сохраняем в JSON файл для веб-интерфейса
        web_json_path = "C:/Users/user/Desktop/web_gifts_data.json"
        try:
            def custom_serializer(obj):
                if pd.isna(obj):
                    return None
                if isinstance(obj, (datetime, pd.Timestamp)):
                    return obj.isoformat()
                if isinstance(obj, float):  # Ограничение точности float
                    return float(f"{obj:.6f}")  # Увеличьте или уменьшите точность по необходимости
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

            with open(web_json_path, "w", encoding="utf-8") as f:
                json.dump(web_data, f, indent=2, ensure_ascii=False, default=custom_serializer,
                          separators=(',', ':'))  # <--- ИЗМЕНЕНО
            print(f"[✓] Веб-данные сохранены: {web_json_path}")
        except Exception as e:
            print(f"[!] Ошибка при сохранении веб-данных: {e}")







# === Расчет изменений за разные периоды ===
def calculate_changes(model_data):
    if len(model_data) < 2:
        return {"1h": 0, "24h": 0, "7d": 0, "30d": 0}

    model_data = model_data.sort_values('SnapshotTime')
    current_price = float(model_data.iloc[-1]['Price']) if pd.notna(model_data.iloc[-1]['Price']) else 0
    current_time = model_data.iloc[-1]['SnapshotTime']

    changes = {}
    periods = {"1h": 1, "24h": 24, "7d": 24 * 7, "30d": 24 * 30}

    for period_name, hours in periods.items():
        target_time = current_time - timedelta(hours=hours)

        # Находим ближайшую запись к целевому времени
        time_diffs = abs(model_data['SnapshotTime'] - target_time)
        closest_idx = time_diffs.idxmin()
        past_price = float(model_data.loc[closest_idx, 'Price']) if pd.notna(
            model_data.loc[closest_idx, 'Price']) else 0

        if past_price > 0:
            change_percent = ((current_price - past_price) / past_price) * 100
            changes[period_name] = round(change_percent, 2)
        else:
            changes[period_name] = 0

    return changes


# === Запрос к API ===
def get_data():
    url = 'https://gifts2.tonnel.network/api/filterStats'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://gifts.tonnel.network/',
        'Origin': 'https://gifts.tonnel.network',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    payload = {
        "authData": "user=%7B%22id%22%3A7023705381%2C%22first_name%22%3A%22%D0%AE%D1%80%D0%B8%D0%B9%22%2C%22last_name%22%3A%22%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FZQlVrBxi8zd5nprNdgxAqJ563M_v-yoGDJJjYm7NFOiGKhroZJ9tgXwMYFY1Meoo.svg%22%7D&chat_instance=4159862832564989925&chat_type=sender&auth_date=1749766341&signature=TEuWuy9-DEhjrrUNrH1k-ewS0YeT8IamrhswIMJZTCADRH4Xwt0_Xr9epNK23S7dCm4Q-IHfDxE7rMgCwzRrAA&hash=9c50f49b5ddf37d58c5c4f45f2d0e413e1c787f3fa4f442097403746a790ff24"}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("✅ Успешно получены данные")
        return response.json()
    else:
        print(f"❌ Ошибка {response.status_code}")
        print(response.text)
        return None


# === Сортировка и преобразование данных ===
def sorting_values(gifts):
    gifts_list = gifts["data"]
    result = {}

    for gift_name, gift_data in gifts_list.items():
        before = gift_name.split('_')[0]
        after = gift_name.split('_')[1]

        if before not in result:
            result[before] = {}

        result[before][after] = gift_data
        result[before][after]["priceWithComission"] = round(gift_data["floorPrice"] * 1.1, 2)

    result_with_time = result.copy()
    result_with_time["time"] = determining_currenttime().isoformat()
    return result, result_with_time


# === Экспорт в JSON ===
def storing_to_json(gifts):
    _, dict_for_json = sorting_values(gifts)
    path = "C:/Users/user/Desktop/gifts_snapshot.json"

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dict_for_json, f, indent=4, ensure_ascii=False)
        print(f"[✓] JSON сохранён: {path}")
    except Exception as e:
        print(f"[!] Ошибка при сохранении JSON: {e}")



# === Экспорт в CSV ===
def export_to_csv(gifts):
    result, _ = sorting_values(gifts)
    snapshot_time = determining_currenttime()
    time_str = snapshot_time.strftime("%Y-%m-%d_%H-%M-%S")
    folder_path = "C:/Users/user/Desktop/gifts_exports"
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"gifts_{time_str}.csv")

    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Collection", "Model", "Price", "PriceWithCommission", "Quantity", "SnapshotTime"])

            for collection_name, models in result.items():
                for model_name, model_data in models.items():
                    writer.writerow([
                        collection_name,
                        model_name,
                        model_data.get("floorPrice", "N/A"),
                        model_data.get("priceWithComission", "N/A"),
                        model_data.get("howMany", "N/A"),
                        snapshot_time.isoformat()
                    ])

        print(f"[✓] CSV сохранён: {file_path}")
    except Exception as e:
        print(f"[!] Ошибка при сохранении CSV: {e}")



# === Главный блок выполнения ===
if __name__ == '__main__':  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
    print("Запуск сбора данных...")  # Добавим для ясности
    while True:
        gifts = get_data()
        if gifts:
            # uploading_to_database(gifts) # <--- У вас эта функция была в закомментированном блоке.
            # Если она вам нужна, раскомментируйте.
            storing_to_json(gifts)
            export_to_csv(gifts)
            # Создаем данные для веб-интерфейса
            create_web_data()
        print("Ждём 60 минут...\n")
        time.sleep(3600)  # <--- УБЕДИТЕСЬ, ЧТО ЗДЕСЬ УКАЗАНО ВРЕМЯ (например, 3600 секунд)
