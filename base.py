import requests
import pandas as pd
import sqlite3
from sqlite3 import Error
from datetime import datetime
import time

# конфигурационные параметры
API_TOKEN = "ac8ce1565a9125a5e14654bec272189c"  # токен с сайта https://www.travelpayouts.com/ru/
DB_FILE = "aviasales_data.db"
FLIGHTS_API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

# аэропорты
def get_airports_data():
    url = "https://api.travelpayouts.com/data/airports.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при получении данных об аэропортах: {e}")
        return None

# города
def get_cities_data():
    url = "https://api.travelpayouts.com/data/cities.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при получении данных о городах: {e}")
        return None

# страны
def get_countries_data():
    url = "https://api.travelpayouts.com/data/countries.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при получении данных о странах: {e}")
        return None

# рейсы
def get_flight_data(origin, destination, departure_date):
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_date,
        "currency": "rub",
        "token": API_TOKEN
    }
    try:
        response = requests.get(FLIGHTS_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при получении данных о рейсах: {e}")
        return None

# обработка и нормализация данных
def process_data(raw_data, data_type):
    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)
    df['extracted_at'] = pd.to_datetime('now')

    if data_type == "airports":
        df = df.rename(columns={
            'code': 'iata_code',
            'name': 'airport_name',
            'city_code': 'city_iata_code',
            'country_code': 'country_code'
        })
        # Обработка координат
        if 'coordinates' in df.columns:
            df['latitude'] = df['coordinates'].apply(lambda x: x['lat'] if isinstance(x, dict) else None)
            df['longitude'] = df['coordinates'].apply(lambda x: x['lon'] if isinstance(x, dict) else None)
            df = df.drop('coordinates', axis=1)  # Удаляем оригинальный словарь

    elif data_type == "cities":
        df = df.rename(columns={
            'code': 'city_iata_code',
            'name': 'city_name',
            'country_code': 'country_code'
        })
        if 'coordinates' in df.columns:
            df['latitude'] = df['coordinates'].apply(lambda x: x['lat'] if isinstance(x, dict) else None)
            df['longitude'] = df['coordinates'].apply(lambda x: x['lon'] if isinstance(x, dict) else None)
            df = df.drop('coordinates', axis=1)

    elif data_type == "countries":
        df = df.rename(columns={
            'code': 'country_code',
            'name': 'country_name'
        })
        # Для стран тоже может быть словарь координат
        if 'coordinates' in df.columns:
            df['latitude'] = df['coordinates'].apply(lambda x: x['lat'] if isinstance(x, dict) else None)
            df['longitude'] = df['coordinates'].apply(lambda x: x['lon'] if isinstance(x, dict) else None)
            df = df.drop('coordinates', axis=1)

    return df

# создание подключения к базе данных
def create_db_connection():
    try:
        conn = sqlite3.connect(DB_FILE)
        print("Успешное подключение к базе данных")
        return conn
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# сохранение данных в базу данных
def save_to_db(df, conn, table_name):
    if df.empty:
        print(f"Нет данных для сохранения в таблицу {table_name}")
        return

    # Проверяем, есть ли словари в данных
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
            print(f"Предупреждение: столбец {col} содержит словари/списки и будет преобразован")
            df[col] = df[col].astype(str)  # Конвертируем в строку

    try:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f"Данные сохранены в таблицу {table_name}")
    except Error as e:
        print(f"Ошибка при сохранении данных: {e}")

# обновление базы
def update_database():
    print("Начало обновления базы данных")
    conn = create_db_connection()
    if not conn:
        return

    # Получаем и обрабатываем данные
    airports_df = process_data(get_airports_data(), "airports")
    cities_df = process_data(get_cities_data(), "cities")
    countries_df = process_data(get_countries_data(), "countries")

    # Сохраняем данные в базу
    save_to_db(airports_df, conn, "airports")
    save_to_db(cities_df, conn, "cities")
    save_to_db(countries_df, conn, "countries")

    # Создаем таблицу flights, если она не существует
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            origin_iata TEXT,
            destination_iata TEXT,
            departure_datetime TEXT,
            return_datetime TEXT,
            price_rub REAL,
            extracted_at TEXT
        )
        """)
        conn.commit()
    except Error as e:
        print(f"Ошибка при создании таблицы flights: {e}")

    # Создаем индексы
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_airports_city ON airports(city_iata_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flights_route ON flights(origin_iata, destination_iata)")
        conn.commit()
    except Error as e:
        print(f"Ошибка при создании индексов: {e}")

    conn.close()
    print("Обновление базы данных завершено")

if __name__ == "__main__":
    # первоначальное заполнение базы данных
    update_database()

def show_airports_sample(limit=5):
    conn = sqlite3.connect(DB_FILE)
    query = f"SELECT * FROM airports LIMIT {limit}"
    df = pd.read_sql(query, conn)
    conn.close()
    print(f"\nПервые {limit} записей из таблицы airports:")
    print(df.to_string(index=False))
