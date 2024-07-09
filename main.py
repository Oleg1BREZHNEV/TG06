import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram. filters import CommandStart, Command
from aiogram. types import Message, FSInputFile
from aiogram. fsm. context import FSMContext
from aiogram. fsm.state import State, StatesGroup
from aiogram. fsm. storage. memory import MemoryStorage

#Импортируем библиотеки для работы с клавиатурами.
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from config import TOKEN
import sqlite3
import aiohttp
import logging
#Импортируем библиотеку request
import requests


bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
#Далее нам нужно определить функционал нашего бота. Бот будет иметь несколько возможностей:

#регистрация пользователя в Telegram;
#просмотр курса валют с помощью API или парсинга;
#получение советов по экономии в виде текста;
#ведение учёта личных финансов по трём категориям.

#Создаём кнопку регистрации.
button_registr = KeyboardButton(text="Регистрация в телеграм-боте")

#Создаём кнопку для выдачи курса валют.
button_exchange_rates = KeyboardButton(text="Курс валют")

#Создаём кнопку для советов по экономике.
button_tips = KeyboardButton(text="Советы по экономии")

#Создаём кнопку для учёта расходов.
button_finances = KeyboardButton(text="Личные финансы")

#Для работы кнопок нужно создавать клавиатуру. Клавиатура будет обычная,
# которая находится снизу. Создаём переменную с помощью класса
# ReplyKeyboardMarkup. В круглых скобках указываем список, внутри
# которого будут находиться другие списки.
# Таким образом настраиваем размещение кнопок.
#Кнопки выходят крупными, поэтому настроим изменение размера клавиатуры.

keyboards = ReplyKeyboardMarkup(keyboard=[
    [button_registr, button_exchange_rates],
    [button_tips, button_finances]
    ], resize_keyboard=True)

#Чтобы сохранять данные о пользователях, нам нужно создать базу данных.
# Сделаем мы это м помощью SQLite в этом же файле. Создаём подключение,
# курсор.

conn = sqlite3.connect('user.db')
cursor = conn.cursor()
#Выполняем действие — создаём таблицу. Указываем поля таблицы.
# Для ID пользователя указываем UNIQUE, потому что идентификатор
# пользователя не может быть неуникальным. Создаём поля для категорий
# (в TEXT будут названия категорий) и для расходов по этим категориям
# (REAL — это дробный тип данных).
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    name TEXT,
    category1 TEXT,
    category2 TEXT,
    category3 TEXT,
    expenses1 REAL,
    expenses2 REAL,
    expenses3 REAL
    )
''')
#Прописываем сохранение после выполнения этого действия.
conn.commit()

#Чтобы запрашивать информацию и ждать ответа, нужно использовать состояния. Создаём класс,
# в котором будут прописаны эти состояния для каждой категории и каждого значения категории.

class FinancesForm(StatesGroup):
    category1 = State()
    expenses1 = State()
    category2 = State()
    expenses2 = State()
    category3 = State()
    expenses3 = State()
#Теперь мы подготовились к написанию функций бота.



#Прописываем функцию /start, которая базово есть у всех ботов.
# Прописываем асинхронную функцию и стартовое сообщение.
# После этого сообщения должна отправляться клавиатура, поэтому
# после сообщения через запятую указываем переменную клавиатуру.

@dp.message(Command('start'))
async def send_start(message: Message):
    await message.answer("Привет! Я ваш личный финансовый помощник. Выберите одну из опций в меню:", reply_markup=keyboards)
#Прописываем декоратор для регистрации в боте.
# В кавычках указываем текст, который будет вызывать работу этой функции.
#Указываем саму асинхронную функцию. При получении сообщения мы можем
# получить информацию — прописываем сохранение этой информации в
# переменных: ID пользователя и имя.
@dp.message(F.text == "Регистрация в телеграм бот")
async def registration(message: Message):
    telegram_id = message.from_user.id
    name = message.from_user.full_name
#Проверяем существование пользователя с помощью действия с курсором.
# (telegram_id,) — это название столбца, в котором нужно искать
    cursor.execute('''SELECT * FROM users WHERE telegram_id = ?''', (telegram_id,))
#Берём выданную информацию. Переменная user = cursor.fetchone() будет
#брать первый попавшийся результат, но он и будет один.
    user = cursor.fetchone()
#Проверяем, существует ли юзер.Указываем, что должно происходить, если юзер существует или не существует.
    if user:
        await message.answer("Вы уже зарегистрированы!")
    else:
        cursor.execute('''INSERT INTO users (telegram_id, name) VALUES (?, ?)''', (telegram_id, name))
#Сохраняем изменения и отправляем сообщение об успешной регистрации
    conn.commit()
    await message.answer("Вы успешно зарегистрированы!")
#Создаём функцию, которая будет выдавать курс валют. Создаём декоратор и асинхронную функцию.
#Для выдачи курса валют мы будем запрашивать информацию без API, с помощью URL-ссылки. Чтобы получить ссылку:
#Переходим на сайт app.exchangerate-api.com/sign-up
#Вводим адрес электронной почты, придумываем пароль. Бесплатный период — две недели.
#Нажимаем на кнопку Accept Terms & Create API Key!.
#Если потребуется, проходим капчу.
#Переходим по ссылке из письма и копируем ссылку Example Request.
#Вставляем ссылку в переменную url. Используем конструкцию TRY—EXCEPT, чтобы избежать ошибок.
@dp.message(F.text == "Курс валют")
async def exchange_rates(message: Message):
    url = "https://v6.exchangerate-api.com/v6/09edf8b2bb246e1f801cbfba/latest/USD"
    try:
#Отправляем  GET - запрос  по адресу URL.

        response = requests.get(url)
#Проверяем успешность обращения
        data = response.json()
        if response.status_code != 200:
            await message.answer("Не удалось получить данные о курсе валют!")
            return
        usd_to_rub = data['conversion_rates']['RUB']
        eur_to_usd = data['conversion_rates']['EUR']

        euro_to_rub = eur_to_usd * usd_to_rub

        await message.answer(f"1 USD - {usd_to_rub:.2f}  RUB\n"
                             f"1 EUR - {euro_to_rub:.2f}  RUB")
    except:
        await message.answer("Произошла ошибка")




#Чтобы получить советы, генерируем их в ChatGPT.
#Создаём асинхронную функцию для отправки текста.
#Создаём список с советами.
@dp.message(F.text == "Советы по экономии")
async def send_tips(message: Message):
    tips = [
       "Совет 1: Ведите бюджет и следите за своими расходами.",
       "Совет 2: Откладывайте часть доходов на сбережения.",
       "Совет 3: Покупайте товары по скидкам и распродажам."
    ]
#Настраиваем   рандомную выдачу советов  с помощью переменной.
#Отправляем  совет из переменной.
    tip = random.choice(tips)
    await message.answer(tip)

#Создаём асинхронную функцию для работы с личными финансами.
@dp.message(F.text == "Личные финансы")
#Начинаем работу с состояниями. Вводим второй атрибут функции.
async def finances(message: Message, state: FSMContext):
#Устанавливаем новое состояние. В круглых скобках указываем
# класс и категорию этого состояния.
    await state.set_state(FinancesForm.category1)
#Отправляем сообщение пользователю.
    await message.reply("Введите первую категорию расходов:")

#Создаём декоратор, который сработает не по фразе, а по категории.
@dp.message(FinancesForm.category1)
#Настраиваем обновление данных. Теперь в category1 будет сохраняться текст сообщения.
async def finances(message: Message, state: FSMContext):
    await state.update_data(category1 = message.text)
    #Начинаем использовать  новое состояние.Теперь  нужно значение
    #денег, которые уходят на эту  категорию товаров.
    await state.set_state(FinancesForm.expenses1)
    await message.reply("Введите расходы для категории 1:")

#Прописываем функцию, которая сработает после получения предыдущего
#значения.
@dp.message(FinancesForm.expenses1)
async def finances(message: Message, state: FSMContext):
    #Используем float, чтобы преобразовывать тип данных.
    await state.update_data(expenses1 = float(message.text))
    #Устанавливаем вторую категорию.
    await state.set_state(FinancesForm.category2)
    await message.reply("Введите вторую категорию расходов:")

#Создаём функцию для расходов по второй категории.
@dp.message(FinancesForm.category2)
async def finances(message: Message, state: FSMContext):
    await state.update_data(category2=message.text)
    await state.set_state(FinancesForm.expenses2)
    await message.reply("Введите расходы для категории 2:")

#Повторяем для третьей категории.
@dp.message(FinancesForm.expenses2)
async def finances(message: Message, state: FSMContext):
    await state.update_data(expenses2=float(message.text))
    await state.set_state(FinancesForm.category3)
    await message.reply("Введите третью категорию расходов:")

@dp.message(FinancesForm.category3)
async def finances(message: Message, state: FSMContext):
    await state.update_data(category3=message.text)
    await state.set_state(FinancesForm.expenses3)
    await message.reply("Введите расходы для категории 3:")

#Создаём ункцию, которая сработает после третьего ответа по расходам.
#Создаём переменную data, в оторую сохраним всю нформацию по состояниям.
@dp.message(FinancesForm.expenses3)
async def finances(message: Message, state: FSMContext):
    data = await state.get_data()
    #Отравляем запрос.Обновляем  информацию и устанавливаем
    # значения для категорий в базе данных.
    telegram_id = message.from_user.id
    cursor.execute(
        '''UPDATE users SET category1 = ?, expenses1 = ?, category2 = ?, expenses2 = ?, category3 = ?, expenses3 = ? WHERE telegram_id = ?''',
        (data['category1'], data['expenses1'], data['category2'], data['expenses2'], data['category3'],
         float(message.text), telegram_id))
#Сохраняем     изменения.Очищаем     состояния.Прописываем
    # сообщение     о     сохранении     категорий     и     расходов.
    conn.commit()
    await state.clear()

    await message.answer("Категории и расходы сохранены!")


async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

#Далее нам нужно определить функционал нашего бота. Бот будет иметь несколько возможностей:
#регистрация пользователя в Telegram;
#просмотр курса валют с помощью API или парсинга;
#получение советов по экономии в виде текста;
#ведение учёта личных финансов по трём категориям.