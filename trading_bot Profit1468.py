import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from ta.volatility import BollingerBands
from ta.trend import SMAIndicator
import argparse
from datetime import datetime
import matplotlib.dates as mdates
import mplcursors  # Для інтерактивних підказок
import time
import logging
import os

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Логи у консоль
        logging.FileHandler("trading_bot.log")  # Логи у файл
    ]
)

# Отримання Binance API ключів зі змінних середовища
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'

if not API_KEY or not API_SECRET:
    logging.error("API_KEY та API_SECRET повинні бути встановлені як змінні середовища.")
    raise EnvironmentError("API ключі не знайдені.")

# Ініціалізація Binance клієнта
client = Client(API_KEY, API_SECRET)


class TradingBotApp:
    def __init__(self, root, from_date=None, to_date=None):
        self.root = root
        self.root.title("Binance Trading Bot")

        # Ініціалізація параметрів бота з дефолтними значеннями
        self.params = {
            'balance': tk.DoubleVar(value=5000.0),  # Початковий баланс
            'number_of_orders': tk.IntVar(value=20),  # Кількість ордерів
            'martingale_factor': tk.DoubleVar(value=0.1),  # Фактор мартингейла
            'order_step_percentage': tk.DoubleVar(value=2.0),  # Крок наступного ордера (%)
            'profit_target_percent': tk.DoubleVar(value=1.9),  # Цільова прибутковість (%)
            'net_profit_target_percent': tk.DoubleVar(value=4.24),  # Чиста цільова прибутковість (%)
            'trailing_stop_percent': tk.DoubleVar(value=1.0),  # Трейлінг стоп (%)
            'trading_pair': tk.StringVar(value='BTCUSDT'),  # Торгова пара
            'timeframe': tk.StringVar(value='15m'),  # Таймфрейм
            'update_interval': tk.IntVar(value=50),  # Інтервал оновлення візуалізації
            'enable_plotting': tk.BooleanVar(value=True),  # Увімкнути/Вимкнути візуалізацію
            'ma_window_size': tk.IntVar(value=320),  # Розмір вікна MA
            'ma_10_window_size': tk.IntVar(value=10),  # Розмір вікна MA 10
            'bb_window_size': tk.IntVar(value=320),  # Розмір вікна BB
            'show_ma': tk.BooleanVar(value=True),  # Показати MA
            'show_bb': tk.BooleanVar(value=True),  # Показати Bollinger Bands
            'trade_history_filename': tk.StringVar(value='trade_history.csv'),  # Ім'я файлу історії торгівлі
            'purchase_balance_percent': tk.DoubleVar(value=25.0),  # Відсоток балансу для покупки
        }

        self.from_date = from_date
        self.to_date = to_date
        self.backtesting = True if self.from_date and self.to_date else False

        self.create_widgets()

        # Ініціалізація змінних
        self.bot_thread = None
        self.bot_running = False

        # Ініціалізація торгових змінних
        self.holding_coins = False
        self.bought_quantity = 0.0
        self.buy_prices = []
        self.sell_prices = []
        self.buy_times = []
        self.sell_times = []
        self.trade_history = []
        self.initial_balance = self.params['balance'].get()
        self.balance = self.initial_balance  # Доступний баланс для торгівлі
        self.profit = 0.0  # Накопичений прибуток
        self.conditional_orders = []
        self.total_profit = 0.0
        self.total_cost = 0.0
        self.all_buy_trades = []  # Деталізовані ордери на купівлю
        self.all_sell_trades = []  # Деталізовані ордери на продаж
        self.current_data = pd.DataFrame()
        self.remembered_orders = []  # Список запам'ятованих ордерів
        self.initial_buy_done = False  # Флаг для відстеження, чи була виконана початкова купівля

        # Змінні для функціоналу паузи
        self.paused = False
        self.pause_event = threading.Event()

    def create_widgets(self):
        # Створення головних фреймів
        config_frame = ttk.LabelFrame(self.root, text="Налаштування")
        config_frame.pack(fill="x", padx=10, pady=5)

        chart_settings_frame = ttk.LabelFrame(self.root, text="Налаштування Графіку")
        chart_settings_frame.pack(fill="x", padx=10, pady=5)

        # Створення трьох рядків для налаштувань
        settings_row1 = ttk.Frame(config_frame)
        settings_row1.pack(fill="x", padx=5, pady=2)

        settings_row2 = ttk.Frame(config_frame)
        settings_row2.pack(fill="x", padx=5, pady=2)

        settings_row3 = ttk.Frame(config_frame)
        settings_row3.pack(fill="x", padx=5, pady=2)

        # Розподіл налаштувань по трьох рядках
        # Рядок 1
        fields_row1 = [
            ('Початковий Баланс ($):', 'balance'),
            ('Кількість Ордерів:', 'number_of_orders'),
            ('Фактор Мартингейла:', 'martingale_factor'),
            ('Крок Ордера (%):', 'order_step_percentage'),
        ]

        for label_text, var_name in fields_row1:
            frame = ttk.Frame(settings_row1)
            frame.pack(side="left", padx=5, pady=2)
            ttk.Label(frame, text=label_text).pack(anchor="w")
            if isinstance(self.params[var_name], tk.BooleanVar):
                chk = ttk.Checkbutton(frame, variable=self.params[var_name])
                chk.pack(anchor="w")
            else:
                entry = ttk.Entry(frame, textvariable=self.params[var_name], width=15)
                entry.pack(anchor="w")

        # Рядок 2
        fields_row2 = [
            ('Цільова Прибутковість (%):', 'profit_target_percent'),
            ('Чиста Цільова Прибутковість (%):', 'net_profit_target_percent'),
            ('Трейлінг Стоп (%):', 'trailing_stop_percent'),
            ('Відсоток Балансу для Покупки (%):', 'purchase_balance_percent'),
        ]

        for label_text, var_name in fields_row2:
            frame = ttk.Frame(settings_row2)
            frame.pack(side="left", padx=5, pady=2)
            ttk.Label(frame, text=label_text).pack(anchor="w")
            if isinstance(self.params[var_name], tk.BooleanVar):
                chk = ttk.Checkbutton(frame, variable=self.params[var_name])
                chk.pack(anchor="w")
            else:
                entry = ttk.Entry(frame, textvariable=self.params[var_name], width=15)
                entry.pack(anchor="w")

        # Рядок 3
        fields_row3 = [
            ('Торгова Пара:', 'trading_pair'),
            ('Таймфрейм:', 'timeframe'),
            ('Інтервал Оновлення:', 'update_interval'),
            ('Увімкнути Візуалізацію:', 'enable_plotting'),
            ('Розмір Вікна MA:', 'ma_window_size'),
            ('Розмір Вікна MA 10:', 'ma_10_window_size'),
            ('Розмір Вікна BB:', 'bb_window_size'),
            ('Ім\'я Файлу Історії Торгівлі:', 'trade_history_filename'),
        ]

        for label_text, var_name in fields_row3:
            frame = ttk.Frame(settings_row3)
            frame.pack(side="left", padx=5, pady=2)
            ttk.Label(frame, text=label_text).pack(anchor="w")
            if isinstance(self.params[var_name], tk.BooleanVar):
                chk = ttk.Checkbutton(frame, variable=self.params[var_name])
                chk.pack(anchor="w")
            else:
                entry = ttk.Entry(frame, textvariable=self.params[var_name], width=15)
                entry.pack(anchor="w")

        # Налаштування графіку
        chart_fields = [
            ('Показати MA:', 'show_ma'),
            ('Показати Bollinger Bands:', 'show_bb'),
        ]

        for label_text, var_name in chart_fields:
            frame = ttk.Frame(chart_settings_frame)
            frame.pack(side="left", padx=5, pady=2)
            ttk.Label(frame, text=label_text).pack(anchor="w")
            chk = ttk.Checkbutton(frame, variable=self.params[var_name])
            chk.pack(anchor="w")

        # Кнопки Старт, Пауза та Стоп
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)

        self.start_button = ttk.Button(button_frame, text="Старт Бота", command=self.start_bot)
        self.start_button.pack(side="left", padx=5)

        self.pause_button = ttk.Button(button_frame, text="Пауза", command=self.pause_bot, state="disabled")
        self.pause_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(button_frame, text="Стоп Бота", command=self.stop_bot, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        # Вивід Логів
        log_frame = ttk.LabelFrame(self.root, text="Лог")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(fill="both", expand=True)

        # Візуалізація з інтерактивною панеллю
        self.figure = plt.Figure(figsize=(10, 8))  # Збільшена висота для додаткового субплоту
        self.ax_price = self.figure.add_subplot(111)

        chart_frame = ttk.LabelFrame(self.root, text="Ринкові Дані")
        chart_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Додавання Canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.draw()

        # Додавання Navigation Toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, chart_frame)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)  # Розташування toolbar вгорі

        # Додавання Canvas після toolbar
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill="both", expand=True)

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        logging.info(message)  # Логування як у GUI, так і у файл/консоль

    def start_bot(self):
        if self.bot_running:
            messagebox.showinfo("Бот Запущено", "Бот вже працює.")
            return

        # Валідація та оновлення налаштувань
        try:
            for key, var in self.params.items():
                if isinstance(var, tk.DoubleVar):
                    var.set(float(var.get()))
                elif isinstance(var, tk.IntVar):
                    var.set(int(var.get()))
                elif isinstance(var, tk.BooleanVar):
                    var.set(bool(var.get()))
                else:
                    var.set(var.get().strip())
        except ValueError as e:
            messagebox.showerror("Невірний Вхід", f"Будь ласка, введіть коректні значення.\nПомилка: {e}")
            self.log(f"Помилка введення: {e}")
            return

        # Ініціалізація параметрів бота з self.params
        self.balance = self.params['balance'].get()
        self.initial_balance = self.balance  # Збереження початкового балансу без змін
        self.number_of_orders = self.params['number_of_orders'].get()
        self.martingale_factor = self.params['martingale_factor'].get()
        self.order_step_percentage = self.params['order_step_percentage'].get()
        self.profit_target_percent = self.params['profit_target_percent'].get()
        self.net_profit_target_percent = self.params['net_profit_target_percent'].get()
        self.trailing_stop_percent = self.params['trailing_stop_percent'].get()
        self.trading_pair = self.params['trading_pair'].get()
        self.timeframe = self.params['timeframe'].get()
        self.update_interval = self.params['update_interval'].get()
        self.enable_plotting = self.params['enable_plotting'].get()
        self.ma_window_size = self.params['ma_window_size'].get()
        self.ma_10_window_size = self.params['ma_10_window_size'].get()
        self.bb_window_size = self.params['bb_window_size'].get()
        self.trade_history_filename = self.params['trade_history_filename'].get()
        self.purchase_balance_percent = self.params['purchase_balance_percent'].get() / 100  # Перетворення на дробове число

        # Валідація форматів дат
        try:
            if self.from_date:
                from_dt = datetime.strptime(self.from_date, '%Y-%m-%d')
            if self.to_date:
                to_dt = datetime.strptime(self.to_date, '%Y-%m-%d')
        except ValueError as e:
            messagebox.showerror("Невірна Дата", f"Помилка формату дати: {e}")
            self.log(f"Помилка формату дати: {e}")
            return

        # Автоматичне коригування --to дати, якщо вона у майбутньому
        if self.to_date:
            to_dt = datetime.strptime(self.to_date, '%Y-%m-%d')
            today = datetime.now()
            if to_dt > today:
                self.log(f"Дата завершення ({self.to_date}) знаходиться у майбутньому. Встановлено на сьогоднішню дату ({today.strftime('%Y-%m-%d')}).")
                logging.info(f"Дата завершення ({self.to_date}) знаходиться у майбутньому. Встановлено на сьогоднішню дату ({today.strftime('%Y-%m-%d')}).")
                self.to_date = today.strftime('%Y-%m-%d')

        self.bot_running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.pause_button.config(state="normal")
        self.log("Бот запущено.")

        # Скидання змінних
        self.holding_coins = False
        self.bought_quantity = 0.0
        self.buy_prices = []
        self.sell_prices = []
        self.buy_times = []
        self.sell_times = []
        self.trade_history = []
        self.balance = self.initial_balance  # Скидання балансу
        self.profit = 0.0  # Скидання прибутку
        self.conditional_orders = []
        self.total_profit = 0.0
        self.total_cost = 0.0
        self.all_buy_trades = []
        self.all_sell_trades = []
        self.current_data = pd.DataFrame()
        self.remembered_orders = []  # Скидання запам'ятованих ордерів
        self.initial_buy_done = False  # Скидання флагу початкової купівлі

        self.paused = False
        self.pause_event.clear()
        self.pause_button.config(text="Пауза")

        # Запуск бота у окремому потоці
        self.bot_thread = threading.Thread(target=self.run_bot)
        self.bot_thread.start()

    def pause_bot(self):
        if not self.bot_running:
            return  # Не можна поставити паузу, якщо бот не працює
        if not self.paused:
            self.paused = True
            self.pause_event.set()
            self.pause_button.config(text="Продовжити")
            self.log("Бот поставлено на паузу.")
            logging.info("Бот поставлено на паузу.")
        else:
            self.paused = False
            self.pause_event.clear()
            self.pause_button.config(text="Пауза")
            self.log("Бот продовжено.")
            logging.info("Бот продовжено.")

    def stop_bot(self):
        if not self.bot_running:
            return

        # Зупинка бота
        self.bot_running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.pause_button.config(state="disabled", text="Пауза")  # Скидання тексту кнопки
        self.paused = False
        self.pause_event.clear()
        self.log("Бот зупинено.")
        logging.info("Бот зупинено.")

        # Очистка графіку
        self.ax_price.clear()
        self.buy_times.clear()
        self.buy_prices.clear()
        self.sell_times.clear()
        self.sell_prices.clear()
        self.all_buy_trades.clear()
        self.all_sell_trades.clear()
        self.canvas.draw()

        # Отримання останньої ціни BTC з даних графіку
        if not self.current_data.empty:
            last_btc_price = self.current_data['close'].iloc[-1]  # Остання ціна на графіку
        else:
            last_btc_price = 0

        # Розрахунок та логування фінальних метрик
        usdt_balance = self.balance                 # Залишок USDT
        btc_balance = self.bought_quantity          # Загальна кількість BTC
        final_value = usdt_balance + (btc_balance * last_btc_price)
        profit = final_value - self.initial_balance

        # Обмеження використання тільки початкового балансу для купівлі
        # Прибуток не додається до балансу
        profit = self.profit

        # Логування результатів
        self.log(f"Початковий Баланс USDT: {self.initial_balance}")
        self.log(f"Фінальний Баланс USDT: {self.balance}")
        self.log(f"Фінальна Кількість BTC: {btc_balance}")
        self.log(f"Остання Ціна BTC на Графіку: {last_btc_price} USDT")
        self.log(f"Загальний Прибуток: {profit:.2f} USDT")
        logging.info(f"Початковий Баланс USDT: {self.initial_balance}")
        logging.info(f"Фінальний Баланс USDT: {self.balance}")
        logging.info(f"Фінальна Кількість BTC: {btc_balance}")
        logging.info(f"Остання Ціна BTC на Графіку: {last_btc_price} USDT")
        logging.info(f"Загальний Прибуток: {profit:.2f} USDT")

        # Додавання аннотації з останньою ціною BTC на графіку
        if self.enable_plotting and not self.current_data.empty:
            # Остання дата та ціна для відображення
            last_date = self.current_data.index[-1]  # Остання дата на графіку
            self.ax_price.text(last_date, last_btc_price,
                               f"Остання Ціна BTC: {last_btc_price} USDT",
                               color="blue", fontsize=10, ha="right", va="bottom")

            # Оновлення графіку з новою аннотацією
            self.canvas.draw()

    def run_bot(self):
        self.balance = self.initial_balance  # Скидання балансу на початку
        self.total_profit = 0.0
        self.trade_history = []
        self.total_cost = 0.0
        self.profit = 0.0  # Скидання прибутку

        if self.backtesting:
            try:
                data = get_historical_data(
                    self.trading_pair,
                    self.timeframe,
                    start_date=self.from_date,
                    end_date=self.to_date
                )
                data = calculate_indicators(data, self.ma_window_size, self.ma_10_window_size, self.bb_window_size)
                self.log(f"Дані завантажено з {data.index.min()} до {data.index.max()}")
                logging.info(f"Дані завантажено з {data.index.min()} до {data.index.max()}")
            except Exception as e:
                self.log(f"Помилка при завантаженні даних: {e}")
                logging.error(f"Помилка при завантаженні даних: {e}")
                return

            # Перевірка, чи дані охоплюють весь вказаний проміжок
            if self.to_date:
                expected_end_date = datetime.strptime(self.to_date, '%Y-%m-%d')
                actual_end_date = data.index.max()
                if actual_end_date < expected_end_date:
                    self.log(f"Попередження: Дані завантажено лише до {actual_end_date}, що раніше за вказану кінцеву дату {expected_end_date}.")
                    logging.warning(f"Дані завантажено лише до {actual_end_date}, що раніше за вказану кінцеву дату {expected_end_date}.")

            # Визначення початкового індексу для обробки даних
            window_size = max(self.ma_window_size, self.ma_10_window_size, self.bb_window_size)
            if len(data) < window_size:
                self.log(f"Недостатньо даних для обчислення індикаторів. Необхідно: {window_size}, Доступно: {len(data)}")
                logging.warning(f"Недостатньо даних для обчислення індикаторів. Необхідно: {window_size}, Доступно: {len(data)}")
                return

            index = window_size  # Початок з індексу, де всі індикатори мають валідні значення
            data_length = len(data)
            while index < data_length:
                if not self.bot_running:
                    break

                # Перевірка на паузу
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue

                # Оновлення поточних даних для використання в stop_bot
                self.current_data = data.iloc[:index + 1]

                # Перевірка на валідність дати
                current_timestamp = self.current_data.index[-1]
                if not isinstance(current_timestamp, pd.Timestamp):
                    self.log(f"Невірний тип часової мітки: {current_timestamp}")
                    logging.error(f"Невірний тип часової мітки: {current_timestamp}")
                    break
                if current_timestamp.year < 1 or current_timestamp.year > 9999:
                    self.log(f"Виявлено невірну дату: {current_timestamp}")
                    logging.error(f"Виявлено невірну дату: {current_timestamp}")
                    break

                try:
                    self.check_buy_conditions(self.current_data)
                    self.check_sell_conditions(self.current_data)

                    # Оновлення візуалізації кожні 'update_interval' ітерацій
                    if self.enable_plotting and index % self.update_interval == 0:
                        self.update_visualization(
                            self.current_data, self.buy_times, self.buy_prices,
                            self.sell_times, self.sell_prices
                        )
                except Exception as e:
                    self.log(f"Виникла помилка у циклі run_bot: {e}")
                    logging.error(f"Помилка у циклі run_bot: {e}")
                    break

                index += 1

            self.log("Бек-тест завершено.")
            self.log(f"Фінальний Баланс: {self.balance}")
            self.log(f"Загальний Прибуток: {self.profit:.2f}")
            logging.info(f"Бек-тест завершено. Фінальний Баланс: {self.balance}, Загальний Прибуток: {self.profit:.2f}")

            df_trade_history = pd.DataFrame(self.trade_history)
            self.log(f"Останні записи історії торгівлі:\n{df_trade_history.tail()}")
            logging.info(f"Останні записи історії торгівлі:\n{df_trade_history.tail()}")

            # Збереження історії торгівлі у файл
            filename = self.params['trade_history_filename'].get()
            try:
                df_trade_history.to_csv(filename, index=False)
                self.log(f"Історія торгівлі збережена у файл '{filename}'.")
                logging.info(f"Історія торгівлі збережена у файл '{filename}'.")
            except Exception as e:
                self.log(f"Не вдалося зберегти історію торгівлі: {e}")
                logging.error(f"Не вдалося зберегти історію торгівлі: {e}")

            # Оновлення візуалізації наприкінці
            if self.enable_plotting:
                self.update_visualization(
                    self.current_data, self.buy_times, self.buy_prices,
                    self.sell_times, self.sell_prices
                )
        else:
            # Реальний час торгівлі
            pass

    def check_buy_conditions(self, current_data):
        # Отримання останніх значень індикаторів
        last_close = current_data['close'].iloc[-1]
        last_ma = current_data['ma'].iloc[-1]
        last_ma_10 = current_data['ma_10'].iloc[-1]
        last_bb_lower = current_data['bb_lower'].iloc[-1]

        prev_ma_10 = current_data['ma_10'].iloc[-2]
        prev_ma = current_data['ma'].iloc[-2]
        prev_bb_lower = current_data['bb_lower'].iloc[-2]

        current_timestamp = current_data.index[-1]
        self.log(f"Перевірка умов купівлі на {current_timestamp}: Остання ціна={last_close}, MA10={last_ma_10}, MA={last_ma}, BB Lower={last_bb_lower}")
        logging.info(f"Умови купівлі - Час: {current_timestamp}, Ціна: {last_close}, MA10: {last_ma_10}, MA: {last_ma}, BB Lower: {last_bb_lower}")

        # Перевірка, чи MA10 перетнув MA320 зверху вниз
        if not self.holding_coins:
            if prev_ma_10 > prev_ma and last_ma_10 < last_ma:
                self.log("MA10 перетнув MA320 зверху вниз. Встановлення умовних ордерів.")
                logging.info("MA10 перетнув MA320 зверху вниз. Встановлення умовних ордерів.")
                self.setup_conditional_orders(last_close)
                # Не купувати на першому перетині
                return

        # Перевірка на початкову купівлю
        if not self.initial_buy_done:
            # Перевірка, чи MA10 перетнув BB нижню лінію зверху
            if prev_ma_10 < prev_bb_lower and last_ma_10 > last_bb_lower:
                self.log("MA10 перетнув BB нижню лінію зверху. Виконання початкової купівлі.")
                logging.info("MA10 перетнув BB нижню лінію зверху. Виконання початкової купівлі.")
                self.execute_initial_buy_order(current_data)
                self.initial_buy_done = True
        else:
            # Після початкової купівлі
            # Перевірка, чи ціна нижча за BB нижню лінію та досягла умовних ордерів
            if last_close < last_bb_lower:
                for order in self.conditional_orders:
                    if last_close <= order['price'] and order not in self.remembered_orders:
                        self.remembered_orders.append(order)
                        self.log(f"Ціна досягла умовного ордера на {order['price']:.2f}. Запам'ятовування ордера.")
                        logging.info(f"Ціна досягла умовного ордера на {order['price']:.2f}. Запам'ятовування ордера.")
            # Коли MA10 знову перетинає BB нижню лінію зверху
            if prev_ma_10 < prev_bb_lower and last_ma_10 > last_bb_lower:
                self.log("MA10 знову перетнув BB нижню лінію зверху. Виконання запам'ятованих ордерів.")
                logging.info("MA10 знову перетнув BB нижню лінію зверху. Виконання запам'ятованих ордерів.")
                self.execute_remembered_orders(current_data, last_close)

    def execute_initial_buy_order(self, current_data):
        last_close = current_data['close'].iloc[-1]
        current_timestamp = current_data.index[-1]
        self.log(f"Виконання початкової купівлі на {current_timestamp} за ціною {last_close:.2f} USDT")
        logging.info(f"Виконання початкової купівлі: Ціна={last_close:.2f} USDT")

        # Фільтрація ордерів, де ціна > поточної
        filtered_orders = [order for order in self.conditional_orders if order['price'] > last_close]

        if not filtered_orders:
            self.log("Немає умовних ордерів з ціною вище поточної для виконання.")
            logging.info("Немає умовних ордерів з ціною вище поточної для виконання.")
            return

        # Підрахунок загальної вартості фільтрованих ордерів за поточною ціною
        total_orders_cost = sum(order['quantity'] * last_close for order in filtered_orders)

        # Розрахунок, який відсоток початкового балансу це становить
        total_orders_percent = total_orders_cost / self.initial_balance

        # Обробка випадку, коли purchase_balance_percent = 0%
        if self.purchase_balance_percent == 0:
            orders_to_buy = filtered_orders.copy()
            cumulative_cost = total_orders_cost
            cumulative_quantity = sum(order['quantity'] for order in orders_to_buy)
            self.log(f"Відсоток балансу для покупки 0%. Виконано всі {len(orders_to_buy)} умовних ордерів.")
            logging.info(f"Відсоток балансу для покупки 0%. Виконано всі {len(orders_to_buy)} умовних ордерів.")
        elif total_orders_percent >= self.purchase_balance_percent:
            orders_to_buy = filtered_orders.copy()
            cumulative_cost = total_orders_cost
            cumulative_quantity = sum(order['quantity'] for order in orders_to_buy)
            self.log(f"Загальна вартість фільтрованих ордерів {cumulative_cost:.2f} USDT >= вказаному відсотку балансу для покупки.")
            logging.info(f"Загальна вартість фільтрованих ордерів {cumulative_cost:.2f} USDT >= вказаному відсотку балансу для покупки.")
        else:
            # Використання заданого відсотка балансу для покупки
            purchase_balance = self.initial_balance * self.purchase_balance_percent
            if self.balance < purchase_balance:
                purchase_balance = self.balance  # Використати весь доступний баланс, якщо менше
                self.log(f"Баланс ({self.balance:.2f} USDT) менше заданого відсотка. Використано весь доступний баланс.")
                logging.info(f"Баланс ({self.balance:.2f} USDT) менше заданого відсотка. Використано весь доступний баланс.")

            orders_to_buy = []
            cumulative_cost = 0.0
            cumulative_quantity = 0.0

            for order in filtered_orders:
                order_quantity = order['quantity']
                order_cost = order_quantity * last_close  # Використання поточної ціни
                if cumulative_cost + order_cost <= purchase_balance or cumulative_cost == 0.0:
                    orders_to_buy.append(order)
                    cumulative_cost += order_cost
                    cumulative_quantity += order_quantity
                else:
                    break
            self.log(f"Загальна вартість фільтрованих ордерів {cumulative_cost:.2f} USDT < заданому відсотку балансу для покупки. Купівля до {self.purchase_balance_percent*100:.2f}% балансу.")
            logging.info(f"Загальна вартість фільтрованих ордерів {cumulative_cost:.2f} USDT < заданому відсотку балансу для покупки. Купівля до {self.purchase_balance_percent*100:.2f}% балансу.")

        if not orders_to_buy:
            self.log("Немає умовних ордерів, які можна виконати з доступним балансом.")
            logging.info("Немає умовних ордерів, які можна виконати з доступним балансом.")
            return

        # Виконання покупки
        self.bought_quantity += cumulative_quantity
        self.balance -= cumulative_cost
        self.total_cost += cumulative_cost
        avg_price = last_close  # Купівля за поточною ціною

        # Перевірка валідності дати перед додаванням
        if not isinstance(current_timestamp, pd.Timestamp):
            self.log(f"Невірний тип часової мітки при виконанні ордерів купівлі: {current_timestamp}")
            logging.error(f"Невірний тип часової мітки при виконанні ордерів купівлі: {current_timestamp}")
            return
        if current_timestamp.year < 1 or current_timestamp.year > 9999:
            self.log(f"Виявлено невірну дату при виконанні ордерів купівлі: {current_timestamp}")
            logging.error(f"Виявлено невірну дату при виконанні ордерів купівлі: {current_timestamp}")
            return

        # Додавання до списків для візуалізації
        self.buy_prices.append(avg_price)
        self.buy_times.append(current_timestamp)
        self.all_buy_trades.append({
            'price': avg_price,
            'quantity': cumulative_quantity,
            'orders_executed': len(orders_to_buy),
            'timestamp': current_timestamp
        })

        self.holding_coins = True

        # Видалення виконаних ордерів з умовних
        self.conditional_orders = [order for order in self.conditional_orders if order not in orders_to_buy]

        # Запис торгівлі
        self.trade_history.append({
            'type': 'Buy',
            'price': avg_price,
            'quantity': cumulative_quantity,
            'timestamp': current_timestamp,
            'orders_executed': len(orders_to_buy)
        })

        self.log(f"Виконано початкову купівлю на суму {cumulative_cost:.2f} USDT за ціною {avg_price:.2f} USDT.")
        logging.info(f"Виконано початкову купівлю: Сума={cumulative_cost:.2f} USDT, Ціна={avg_price:.2f} USDT, Кількість={cumulative_quantity}")

    def execute_remembered_orders(self, current_data, crossing_price):
        current_timestamp = current_data.index[-1]
        self.log(f"Виконання запам'ятованих ордерів на {current_timestamp} за ціною {crossing_price:.2f} USDT")
        logging.info(f"Виконання запам'ятованих ордерів: Ціна={crossing_price:.2f} USDT")

        # Купівля запам'ятованих ордерів, де ціна > поточної ціни перетину
        orders_to_buy = [order for order in self.remembered_orders if order['price'] > crossing_price]
        if not orders_to_buy:
            self.log("Немає запам'ятованих ордерів для виконання на цьому перетині.")
            logging.info("Немає запам'ятованих ордерів для виконання на цьому перетині.")
            return

        cumulative_cost = 0.0
        cumulative_quantity = 0.0
        for order in orders_to_buy:
            order_quantity = order['quantity']
            order_cost = order_quantity * crossing_price  # Купівля за поточною ціною

            if self.balance >= order_cost:
                cumulative_cost += order_cost
                cumulative_quantity += order_quantity
                self.bought_quantity += order_quantity
                self.balance -= order_cost
                self.total_cost += order_cost

                # Запис торгівлі
                self.buy_prices.append(crossing_price)
                self.buy_times.append(current_timestamp)
                self.all_buy_trades.append({
                    'price': crossing_price,
                    'quantity': order_quantity,
                    'orders_executed': 1,
                    'timestamp': current_timestamp
                })
                self.trade_history.append({
                    'type': 'Buy',
                    'price': crossing_price,
                    'quantity': order_quantity,
                    'timestamp': current_timestamp,
                    'orders_executed': 1
                })
                self.log(f"Виконано запам'ятований ордер на ціну {crossing_price:.2f} USDT, кількість {order_quantity:.6f}.")
                logging.info(f"Виконано запам'ятований ордер: Ціна={crossing_price:.2f} USDT, Кількість={order_quantity:.6f}")
            else:
                self.log("Недостатньо балансу для виконання запам'ятованого ордера.")
                logging.info("Недостатньо балансу для виконання запам'ятованого ордера.")
                break  # Немає достатньо балансу для подальших ордерів

        # Видалення виконаних ордерів з умовних та запам'ятованих
        self.conditional_orders = [order for order in self.conditional_orders if order not in orders_to_buy]
        self.remembered_orders = [order for order in self.remembered_orders if order not in orders_to_buy]

    def setup_conditional_orders(self, crossing_price):
        self.conditional_orders = []
        P0 = crossing_price
        S = self.order_step_percentage / 100
        M = self.martingale_factor
        total_sum = 0
        prices = [P0]
        quantities = []

        # Розрахунок цін ордерів
        for n in range(1, self.number_of_orders + 1):
            if n > 1:
                Pn = prices[-1] - (S * P0)
                prices.append(Pn)
            exponent = (n - 1)
            total_sum += prices[-1] * (1 + M) ** exponent

        # Розрахунок кількості
        Q1 = self.initial_balance / total_sum  # Використання початкового балансу для розрахунку кількості
        quantities.append(Q1)
        for n in range(1, self.number_of_orders):
            Qn = quantities[-1] * (1 + M)
            quantities.append(Qn)

        # Зберігання умовних ордерів
        for price, quantity in zip(prices, quantities):
            self.conditional_orders.append({'price': price, 'quantity': quantity})

        self.log(f"Встановлено умовні ордери, починаючи з ціни {P0:.2f} USDT.")
        logging.info(f"Встановлено умовні ордери, починаючи з ціни {P0:.2f} USDT.")

    def check_sell_conditions(self, current_data):
        # Отримання останніх значень індикаторів
        last_close = current_data['close'].iloc[-1]
        last_bb_upper = current_data['bb_upper'].iloc[-1]

        current_timestamp = current_data.index[-1]
        self.log(f"Перевірка умов продажу на {current_timestamp}: Остання ціна={last_close}, BB Upper={last_bb_upper}")
        logging.info(f"Умови продажу - Час: {current_timestamp}, Ціна: {last_close}, BB Upper: {last_bb_upper}")

        if self.holding_coins and self.bought_quantity > 0:
            current_value = self.bought_quantity * last_close
            profit = current_value - self.total_cost
            profit_percent = (profit / self.total_cost) * 100 if self.total_cost > 0 else 0

            if profit_percent >= self.net_profit_target_percent or \
               (last_close > last_bb_upper and profit_percent >= self.profit_target_percent):
                # Виконання продажу
                trade_profit = (last_close * self.bought_quantity) - self.total_cost
                self.profit += trade_profit
                self.log(f"Продано {self.bought_quantity:.6f} одиниць за ціною {last_close:.2f} USDT.")
                logging.info(f"Продано {self.bought_quantity:.6f} одиниць за ціною {last_close:.2f} USDT.")

                self.sell_times.append(current_timestamp)
                self.sell_prices.append(last_close)
                # Запис торгівлі
                self.trade_history.append({
                    'type': 'Sell',
                    'price': last_close,
                    'quantity': self.bought_quantity,
                    'timestamp': current_timestamp,
                    'profit_percent': profit_percent
                })
                self.all_sell_trades.append({
                    'price': last_close,
                    'quantity': self.bought_quantity,
                    'profit_percent': profit_percent,
                    'timestamp': current_timestamp
                })
                self.log(f"Прибуток від торгівлі: {trade_profit:.2f} USDT.")
                logging.info(f"Прибуток від торгівлі: {trade_profit:.2f} USDT.")

                self.holding_coins = False
                self.bought_quantity = 0
                self.buy_prices = []
                self.total_cost = 0.0  # Скидання загальної вартості
                # Скидання для наступного циклу торгівлі
                self.conditional_orders = []
                self.remembered_orders = []  # Очищення запам'ятованих ордерів
                self.initial_buy_done = False  # Скидання флагу початкової купівлі
                # Скидання балансу до початкового, гарантування, що він не перевищує початковий
                self.balance = self.initial_balance
                self.log("Підготовка до наступної можливості купівлі.")
                logging.info("Підготовка до наступної можливості купівлі.")

    def update_visualization(self, data, buy_times, buy_prices, sell_times, sell_prices):
        # Очищення попередніх графіків
        self.ax_price.clear()

        # Побудова графіку ціни
        self.ax_price.plot(data.index, data['close'], label='Ціна', color='blue')

        # Побудова MA
        if self.params['show_ma'].get():
            self.ax_price.plot(data.index, data['ma'], label=f"MA {self.ma_window_size}", color='orange')
            self.ax_price.plot(data.index, data['ma_10'], label=f"MA {self.ma_10_window_size}", color='purple')

        # Побудова Bollinger Bands
        if self.params['show_bb'].get():
            self.ax_price.plot(data.index, data['bb_upper'], label='BB Верхня', color='green')
            self.ax_price.plot(data.index, data['bb_lower'], label='BB Нижня', color='red')

        # Побудова умовних ордерів як горизонтальних ліній
        for order in self.conditional_orders:
            self.ax_price.axhline(y=order['price'], linestyle='--', color='grey', alpha=0.5)

        # Побудова ордерів на купівлю
        if self.all_buy_trades:
            buy_scatter = self.ax_price.scatter(
                [trade['timestamp'] for trade in self.all_buy_trades],
                [trade['price'] for trade in self.all_buy_trades],
                marker='^',
                color='green',
                label='Купівля'
            )
            cursor = mplcursors.cursor(buy_scatter, hover=True)
            cursor.connect("add", lambda sel: sel.annotation.set_text(
                f"Купівля\nЦіна: {self.all_buy_trades[sel.target.index]['price']:.2f} USDT\n"
                f"Кількість: {self.all_buy_trades[sel.target.index]['quantity']:.6f}\n"
                f"Ордерів: {self.all_buy_trades[sel.target.index]['orders_executed']}"
            ))

        # Побудова ордерів на продаж
        if self.all_sell_trades:
            sell_scatter = self.ax_price.scatter(
                [trade['timestamp'] for trade in self.all_sell_trades],
                [trade['price'] for trade in self.all_sell_trades],
                marker='v',
                color='red',
                label='Продаж'
            )
            cursor = mplcursors.cursor(sell_scatter, hover=True)
            cursor.connect("add", lambda sel: sel.annotation.set_text(
                f"Продаж\nЦіна: {self.all_sell_trades[sel.target.index]['price']:.2f} USDT\n"
                f"Кількість: {self.all_sell_trades[sel.target.index]['quantity']:.6f}\n"
                f"Прибуток: {self.all_sell_trades[sel.target.index]['profit_percent']:.2f}%"
            ))

        # Форматування осі x для відображення дати та часу
        self.ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        self.ax_price.xaxis.set_major_locator(mdates.AutoDateLocator())

        # Додавання легенди
        self.ax_price.legend()

        # Налаштування макету та оновлення Canvas
        self.figure.tight_layout()
        self.canvas.draw()


def get_historical_data(symbol, interval, start_date=None, end_date=None, limit=1000):
    """Отримати історичні дані з Binance."""
    klines = []

    if start_date:
        try:
            start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        except ValueError as e:
            logging.error(f"Помилка парсингу початкової дати: {e}")
            raise
    else:
        start_ts = None

    if end_date:
        try:
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        except ValueError as e:
            logging.error(f"Помилка парсингу кінцевої дати: {e}")
            raise
    else:
        end_ts = None

    while True:
        try:
            temp_klines = client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                startTime=start_ts,
                endTime=end_ts
            )
            logging.info(f"Отримано {len(temp_klines)} клінів.")
        except BinanceAPIException as e:
            logging.error(f"Binance API помилка: {e}")
            break
        except BinanceRequestException as e:
            logging.error(f"Binance Запит помилка: {e}")
            break
        except Exception as e:
            logging.error(f"Несподівана помилка: {e}")
            break

        if not temp_klines:
            logging.info("Немає більше клінів для завантаження. Вихід з циклу.")
            break
        klines.extend(temp_klines)

        if len(temp_klines) < limit:
            # Немає більше даних для завантаження
            logging.info("Отримано менше ніж ліміт. Припускається, що всі дані завантажено.")
            break
        else:
            # Оновлення start_ts до часу закриття останнього кліну + 1 мс для уникнення перекриття
            last_close_time = temp_klines[-1][6]  # Час закриття знаходиться на індексі 6
            start_ts = last_close_time + 1
            last_date = pd.to_datetime(last_close_time, unit='ms')
            logging.info(f"Оновлено start_ts до {last_date}")

    # Обробка та повернення даних
    data = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms', errors='coerce')
    data = data.dropna(subset=['timestamp'])  # Видалення рядків з некоректними датами
    data.set_index('timestamp', inplace=True)
    data = data[['open', 'high', 'low', 'close', 'volume']]
    data = data.astype(float)
    logging.info(f"Загальна кількість отриманих даних: {len(data)}")
    return data


def calculate_indicators(data, ma_window_size, ma_10_window_size, bb_window_size):
    """Обчислити індикатори MA та Bollinger Bands."""
    # Простий рухомий середній (MA)
    data['ma'] = SMAIndicator(close=data['close'], window=ma_window_size).sma_indicator()
    data['ma_10'] = SMAIndicator(close=data['close'], window=ma_10_window_size).sma_indicator()

    # Bollinger Bands
    bb_indicator = BollingerBands(close=data['close'], window=bb_window_size, window_dev=2)
    data['bb_upper'] = bb_indicator.bollinger_hband()
    data['bb_lower'] = bb_indicator.bollinger_lband()

    logging.info("Індикатори успішно обчислено.")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Binance Trading Bot')
    parser.add_argument('--from', dest='from_date', type=str, help='Початкова дата у форматі YYYY-MM-DD')
    parser.add_argument('--to', dest='to_date', type=str, help='Кінцева дата у форматі YYYY-MM-DD')

    args = parser.parse_args()

    root = tk.Tk()
    app = TradingBotApp(root, from_date=args.from_date, to_date=args.to_date)
    root.mainloop()