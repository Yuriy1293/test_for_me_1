# web_server.py
from flask import Flask, jsonify, send_from_directory
import os
import json
import pandas as pd
from datetime import datetime, timezone, timedelta

# Импортируем функции из вашего скрипта для создания JSON
# Убедитесь, что ваш скрипт называется 'data_collector.py' или что-то подобное,
# чтобы не было путаницы с 'app.py' или 'web_server.py'
from data_collector import create_web_data

app = Flask(__name__)

# Путь к JSON файлу, который генерирует ваш скрипт
WEB_DATA_PATH = "C:/Users/user/Desktop/web_gifts_data.json"
HTML_FILE_PATH = "index.html"


# --- Эндпоинт для отдачи HTML-файла ---
@app.route('/')
def serve_index():
    # Убедитесь, что index.html находится в той же папке, что и web_server.py
    # или укажите полный путь к нему, если он в другом месте.
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), HTML_FILE_PATH)


# --- Эндпоинт для отдачи данных API ---
@app.route('/api/gifts-data', methods=['GET'])
def get_gifts_data_from_file():
    # Убедитесь, что create_web_data() сохранит данные по WEB_DATA_PATH
    # В реальном приложении, если сбор данных занимает много времени,
    # лучше, чтобы data_collector.py работал по расписанию отдельно.
    if not os.path.exists(WEB_DATA_PATH):
        print("[!] web_gifts_data.json не найден. Попытка сгенерировать...")
        try:
            create_web_data()
            if not os.path.exists(WEB_DATA_PATH):
                return jsonify({"error": "Данные пока недоступны. Попробуйте позже."}), 503
        except Exception as e:
            # Логируем ошибку, если create_web_data() падает
            app.logger.error(f"[!] Ошибка при генерации веб-данных в web_server: {e}")
            return jsonify({"error": f"Ошибка сервера при подготовке данных: {e}"}), 500

    try:
        with open(WEB_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        app.logger.error(f"FileNotFoundError: Файл данных не найден по пути: {WEB_DATA_PATH}")
        return jsonify({"error": "Файл данных не найден."}), 404
    except json.JSONDecodeError as e:  # <<< ИЗМЕНЕНИЕ ЗДЕСЬ: добавляем as e
        # Логируем конкретную ошибку парсинга JSON
        app.logger.error(f"JSONDecodeError: Ошибка чтения файла данных JSON: {e}")
        return jsonify({"error": f"Ошибка чтения файла данных JSON: {e}"}), 500
    except Exception as e:
        # Логируем любую другую непредвиденную ошибку
        app.logger.error(f"Неизвестная ошибка в get_gifts_data_from_file: {e}")
        return jsonify({"error": f"Неизвестная ошибка сервера: {e}"}), 500


if __name__ == '__main__':
    # Включаем режим отладки для более подробных логов в консоли Flask
    app.run(debug=True, port=5000)  # Используйте debug=True для разработки
