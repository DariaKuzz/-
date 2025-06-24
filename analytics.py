import pandas as pd
from sqlite3 import Error
from datetime import datetime, timedelta
import time
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from base import create_db_connection

# Работа с БД (Извлечение данных о ценах на авиабилеты из базы данных для заданного маршрута и периода).
def get_flight_prices_from_db(origin, destination, start_date, end_date, conn):

    try:
        cursor = conn.cursor()
        query = f"""
        SELECT departure_datetime, MIN(price_rub) as min_price
        FROM flights
        WHERE origin_iata = '{origin}' 
        AND destination_iata = '{destination}' 
        AND departure_datetime BETWEEN '{start_date}' 
        AND '{end_date}'
        GROUP BY departure_datetime
        ORDER BY departure_datetime
        """
        cursor.execute(query)
        data = cursor.fetchall()

        if data:
            df = pd.DataFrame(data, columns=['departure_datetime', 'min_price'])
            df['departure_datetime'] = pd.to_datetime(df['departure_datetime'])
            print("Данные о ценах успешно извлечены из базы данных.")
        else:
            print("Нет данных о ценах для заданного маршрута и периода.")
            df = pd.DataFrame(columns=['departure_datetime', 'min_price'])
    except Error as e:
        print(f"Ошибка при извлечении данных: {e}")
        df = pd.DataFrame(columns=['departure_datetime', 'min_price'])

    return df

# Статистический анализ данных (ценах на авиабилеты).
def statistical_analysis(df):
    if df.empty:
        print("Недостаточно данных для статистического анализа.")
        return

    # Анализ временных рядов.
    try:
        decomposition = sm.tsa.seasonal_decompose(df.set_index('departure_datetime')['min_price'], model='additive', period=30)
        plt.figure(figsize=(12, 8))
        plt.subplot(411)
        plt.plot(decomposition.observed, label='Исходные данные')
        plt.legend(loc='upper left')
        plt.subplot(412)
        plt.plot(decomposition.trend, label='Тренд')
        plt.legend(loc='upper left')
        plt.subplot(413)
        plt.plot(decomposition.seasonal, label='Сезонность')
        plt.legend(loc='upper left')
        plt.subplot(414)
        plt.plot(decomposition.resid, label='Остаток')
        plt.legend(loc='upper left')
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Ошибка при анализе временных рядов: {e}.")

# Графическая визуализация динамики цен.
def visualize_price_trends(df, origin, destination, start_date, end_date):
    if df.empty:
        print("Нет данных для визуализации.")
        return

    plt.figure(figsize=(12, 6))
    plt.plot(df['departure_datetime'], df['min_price'], marker='o', linestyle='-')
    plt.xlabel("Дата вылета")
    plt.ylabel("Минимальная цена")
    plt.title(f"Динамика цен на авиабилеты: из {origin} в {destination} ({start_date} - {end_date})")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# Машинное обучение
def train_and_predict(df, origin, destination):

    if df.empty or len(df) < 10:
        print("Недостаточно данных для обучения модели.")
        return

    # Подготовка данных
    df['days_since_start'] = (df['departure_datetime'] - df['departure_datetime'].min()).dt.days
    X = df[['days_since_start']]
    y = df['min_price']

    # Выделение обучающей выборки
    X_train, y_train = train_test_split(X, y, test_size=0.2, random_state=42)

    # Выбор модели (линейная регрессия с полиномиальными признаками)
    poly = PolynomialFeatures(degree=2)
    X_train_poly = poly.fit_transform(X_train)

    model = LinearRegression()
    model.fit(X_train_poly, y_train)

    # Прогноз на будущее
    last_date = df['departure_datetime'].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, 31)]
    future_df = pd.DataFrame({'departure_datetime': future_dates})
    future_df['days_since_start'] = (future_df['departure_datetime'] - df['departure_datetime'].min()).dt.days
    X_future = future_df[['days_since_start']]
    X_future_poly = poly.transform(X_future)
    future_prices = model.predict(X_future_poly)

    future_df['predicted_price'] = future_prices
    print("\n Прогноз цен на ближайшие 30 дней:")
    print(future_df[['departure_datetime', 'predicted_price']])

    # Визуализация прогноза
    plt.figure(figsize=(12, 6))
    plt.plot(df['departure_datetime'], df['min_price'], marker='o', linestyle='-', label='Фактические цены')
    plt.plot(future_df['departure_datetime'], future_df['predicted_price'], marker='x', linestyle='--', label='Прогноз')
    plt.xlabel("Дата вылета")
    plt.ylabel("Цена (руб)")
    plt.title(f"Прогноз цен на авиабилеты: {origin} -> {destination}")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()

# Использование данных пользователя
if __name__ == "__main__":


    origin_iata = input("Введите код города отправления (например, LED): ").upper()
    destination_iata = input("Введите код города назначения (например, MOW): ").upper()
    start_date_str = input("Введите начальную дату (YYYY-MM-DD): ")
    end_date_str = input("Введите конечную дату (YYYY-MM-DD): ")


    conn = create_db_connection()
    if not conn:
        exit()

    flight_prices_df = get_flight_prices_from_db(origin_iata, destination_iata, start_date_str, end_date_str, conn)
    conn.close()


    if not flight_prices_df.empty:
        print("Составляем прогноз...")
        statistical_analysis(flight_prices_df)
        visualize_price_trends(flight_prices_df, origin_iata, destination_iata, start_date_str, end_date_str)
        train_and_predict(flight_prices_df, origin_iata, destination_iata)
    else:
        print("Нет данных для указанного маршрута и периода.")


        
    
