import requests
import pandas as pd
import sqlite3
from sqlite3 import Error
from datetime import datetime, timedelta
import time

import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
import logging
# -------------------------------------------------------------

# Конфигурация
from config import API_TOKEN, BOT_TOKEN, DB_FILE

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------------------------------------------

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from base import save_to_db, create_db_connection
from analytics import get_flight_prices_from_db, train_and_predict, visualize_price_trends, statistical_analysis

# -------------------------------------------------------------
def create_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('🛫 Start'))
    keyboard.add(KeyboardButton('🌐 Forecast'))
    keyboard.add(KeyboardButton('❓ Help'))
    keyboard.add(KeyboardButton('🪧 Codes'))
    return keyboard


@bot.message_handler(func=lambda message: message.text in ['🛫 Start', '❓ Help', '🪧 Codes', '🌐 Forecast'])
def handle_commands(message):
    """Обработчик команд"""
    if message.text == '🛫 Start':
        text = """
    ✈️ Добро пожаловать в бота для прогнозирования цен на авиабилеты!
    
🔍 Я могу помочь вам:
- Показать историю цен на конкретный маршрут 📊
- Спрогнозировать цены на будущие даты 🗓️
- Показать график изменения цен 📉
    
🚀 Используйте команду '🌐 Forecast' чтобы начать.
    """
    elif message.text == '❓ Help':
        text = """
    Как пользоваться ботом:
    
    1. Введите команду '🌐 Forecast'
    2. Укажите маршрут в формате:
       ГОРОД_ОТПРАВЛЕНИЯ ГОРОД_НАЗНАЧЕНИЯ НАЧАЛЬНАЯ_ДАТА КОНЕЧНАЯ_ДАТА
    #    Например: LED MOW 2024-07-01 2024-07-30
    
    3. Бот запросит данные и покажет:
       - Историю цен за указанный период
       - Прогноз на следующие 30 дней
       - График изменения цен
    
    Коды городов должны быть в формате IATA (LED, MOW, KZN и т.д.)
    """
    elif message.text == '🪧 Codes':
        text = """
    Примеры кодов аэропортов:
    🌏 LED - аэропорт Санкт-Петербурга;
    🌏 MOW - аэропорт Москвы;
    🌏 KZN - аэропорт Казани;
    🌏 KJA — аэропорт Красноярска (Емельяново);
    🌏 IKT — аэропорт Иркутска;
    🌏 KGD — аэропорт Калининграда (Храброво);
    🌏 KHV — аэропорт Хабаровска (Новый);
    🌏 TJM — аэропорт Тюмени (Рощино);
    🌏 PEE — аэропорт Перми (Большое Савино);
    🌏 TOF — аэропорт Томска (Богашево);
    🌏 ASF — аэропорт Астрахани (Нариманово);
    🌏 GSV — аэропорт Саратова (Гагарин)
    """
    elif message.text == '🌐 Forecast':
        text = """Введите маршрут в формате: 
    ГОРОД_ОТПРАВЛЕНИЯ ГОРОД_НАЗНАЧЕНИЯ НАЧАЛЬНАЯ_ДАТА КОНЕЧНАЯ_ДАТА
    Например: LED MOW 2024-07-01 2024-07-30"""

    bot.send_message(message.chat.id, text, reply_markup=create_keyboard())
    return

@bot.message_handler(func=lambda message: True)
def handle_route(message):
    """Обработчик ввода маршрута"""
    try:
        parts = message.text.split()
        if len(parts) != 4:
            bot.send_message(
                message.chat.id,
                "Неверный формат. Введите данные как в примере: LED MOW 2024-07-01 2024-07-30",
                reply_markup=create_keyboard()
            )
            return
        
        origin, destination, start_date, end_date = parts
        
        # Валидация дат
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            bot.send_message(
                message.chat.id,
                "Неверный формат даты. Используйте YYYY-MM-DD",
                reply_markup=create_keyboard()
            )
            return
        
        # Информируем пользователя о начале обработки
        bot.send_message(
            message.chat.id,
            "Ищу данные по вашему запросу...",
            reply_markup=create_keyboard()
        )
        
        # Получаем данные из базы
        df = get_flight_prices_from_db(origin, destination, start_date, end_date)
        if df.empty:
            # Если данных нет, пробуем получить из API
            bot.send_message(
                message.chat.id,
                "Данных в базе нет. Пробуем получить свежие данные из API...")
            
            if save_to_db(origin, destination, start_date):
                df = get_flight_prices_from_db(origin, destination, start_date, end_date)
            
        if df.empty:
            bot.send_message(
                message.chat.id,
                "Не удалось найти данные для указанного маршрута и периода",
                reply_markup=create_keyboard()
            )
            return
        

        # Генерация прогноза
            # 1. Анализ временных рядов
        trend_buffer = statistical_analysis(df)
        if trend_buffer:
            bot.send_photo(message.chat.id, trend_buffer, caption="Анализ временных рядов")
            trend_buffer.close()
        
        # 2. График цен
        price_buffer = visualize_price_trends(df, origin, destination)
        if price_buffer:
            bot.send_photo(message.chat.id, price_buffer, caption="Динамика цен")
            price_buffer.close()
        
        # 3. Прогноз
        predict_buffer, forecast = train_and_predict(df, origin, destination)
        if predict_buffer and forecast:
            bot.send_photo(message.chat.id, predict_buffer, caption="Прогноз на 30 дней")
            predict_buffer.close()
            
            # Форматируем прогноз
            forecast_text = "\n".join(
                f"{datetime.strptime(item['date'], '%Y-%m-%d').strftime('%d.%m')}: {item['price']:.0f} руб"
                for item in forecast)
            bot.send_message(message.chat.id, f"Прогноз цен:\n{forecast_text}")

        # forecast_df = generate_price_forecast(df)
        
        # # Подготовка текстового ответа
        # response_text = f"""
        # Данные по маршруту: {origin} → {destination}
        # Период: {start_date} — {end_date}
        
        # Исторические цены:
        # Минимальная: {int(df['min_price'].min())} руб
        # Средняя: {int(df['min_price'].mean())} руб
        # Максимальная: {int(df['min_price'].max())} руб
        # """
        
        # if forecast_df is not None:
        #     best_price_date = forecast_df.loc[forecast_df['predicted_price'].idxmin()]
        #     response_text += f"""
            
        #     Прогноз на следующие 30 дней:
        #     Лучшая цена ожидается {best_price_date['date'].strftime('%Y-%m-%d')}
        #     Примерная стоимость: {int(best_price_date['predicted_price'])} руб
        #     """
        
        # # Отправка текстового ответа
        # bot.send_message(
        #     message.chat.id,
        #     response_text,
        #     reply_markup=create_keyboard()
        # )
        
        # # Отправка графика
        # plot_buf = create_plot(df, forecast_df, origin, destination)
        # bot.send_photo(
        #     message.chat.id,
        #     plot_buf,
        #     caption="График изменения цен",
        #     reply_markup=create_keyboard()
        # )
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике сообщения: {e}")
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке запроса",
            reply_markup=create_keyboard()
        )
    return

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен")
    bot.polling(none_stop=True, interval=0)