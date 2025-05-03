import os
import asyncio
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from random import choice, shuffle
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = ""
scheduler = AsyncIOScheduler()
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=storage)


user_schedules = {}
current_sessions = {}

class UserState(StatesGroup):
    choose_answer = State()
    creating_days = State()
    creating_time = State()
    creating_count = State()
    creating_difficulty = State()
    in_progress = State()
    in_progress_schedule = State()

main_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .add(KeyboardButton('🎲 Случайная задача')) \
    .row(KeyboardButton('📅 Расписание'), KeyboardButton('🎚️ Сложность'))

cancel_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .add(KeyboardButton('❌ Отмена'))

schedule_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .add(KeyboardButton('❌ Удалить расписание')) \
    .add(KeyboardButton('🏠 Главное меню'))

start_session_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .add(KeyboardButton('🚀 Начать решение')) \
    .add(KeyboardButton('🏠 Главное меню'))

difficulty_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .row(KeyboardButton('🍀 Легкие'), KeyboardButton('🎯 Средние')) \
    .add(KeyboardButton('💣 Сложные')) \
    .add(KeyboardButton('🏠 Главное меню'))

difficulty_cancel_kb = ReplyKeyboardMarkup(resize_keyboard=True) \
    .row(KeyboardButton('🍀 Легкие'), KeyboardButton('🎯 Средние')) \
    .add(KeyboardButton('💣 Сложные')) \
    .add(KeyboardButton('❌ Отмена'))

TASKS = {
    "💣 Сложные": [
        ("7−3(5x−3)=−11x", "4"),
        ("Найдите две последние цифры числа 82**, если оно делится на 90.", "80"),
        ("Решите уравнение: 2x−3(3x+1)=11.", "-2"),
        ("Кофеварку на распродаже уценили на 20%, при этом она стала стоить 4800 рублей. Сколько рублей стоила кофеварка до распродажи?", "6000")
    ,("Самолёт, находящийся в полёте, преодолевает 230 метров за каждую секунду. Выразите скорость самолёта в километрах в час.","828"),
        ("Решите уравнение: 16−7(5−x)=9.", "4")],
    "🎯 Средние": [
        ("Найдите значение выражения\n 5,4·5,5+3,7.", "33.4"),
        ("Найдите значение выражения.\n −4,9+4,81:1,3.", "-1,2"),
        ("Найдите значение выражения.\n −4,5+6,24:1,6.", "-0,6"),
        ("Автомобиль едет со скоростью 72км/ч. Сколько метров он проезжает за одну секунду?", "20"),
        ("В планы директора лицея входит реконструкция прямоугольного спортивного зала. Было решено увеличить длину помещения в раза, а ширину уменьшить на 20%. Во сколько раз площадь спортивного зала изменится после окончания работ? Ответ дайте в десятичных", "1.4")
    ],
    "🍀 Легкие": [
        ("Найдите значение выражения\n 8,26−7,52:2.", "4,5"),
        ("Найдите значение выражения \n(2,3+1,9):3,5", "1,2"),
        ("Найдите значение выражения.\n 2,9+1,92:1,6.", "4,1"),
        ("Найдите значение выражения\n 6,4·8,5+0,8.", "55,2")
    ]
}
async def on_startup(_):
    scheduler.start()

async def on_shutdown(_):
    scheduler.shutdown()
    await bot.close()


def normalize_answer(answer: str) -> str:
    return answer.replace(',', '.').strip().lower()

@dp.message_handler(lambda message: message.text == '❌ Отмена', state='*')
async def cancel_creation(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Создание расписания отменено", reply_markup=main_kb)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("📚 Математический тренажер готов к работе!", reply_markup=main_kb)

@dp.message_handler(text='🏠 Главное меню', state='*')
async def main_menu(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Главное меню:", reply_markup=main_kb)

@dp.message_handler(text='🎲 Случайная задача')
async def random_task(message: types.Message):
    all_tasks = [task for category in TASKS.values() for task in category]
    task = choice(all_tasks)
    await message.answer(f"🔔 Новая задача:\n\n{task[0]}", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('🏠 Главное меню'))
    await UserState.in_progress.set()
    current_sessions[message.from_user.id] = task

@dp.message_handler(text='🎚️ Сложность')
async def set_difficulty(message: types.Message):
    await message.answer("Выберите уровень сложности:", reply_markup=difficulty_kb)

@dp.message_handler(text=['🍀 Легкие', '🎯 Средние', '💣 Сложные'])
async def difficulty_selected(message: types.Message):
    tasks = TASKS[message.text]
    task = choice(tasks)
    await message.answer(f"🔔 {message.text} задача:\n\n{task[0]}", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('🏠 Главное меню'))
    await UserState.in_progress.set()
    current_sessions[message.from_user.id] = task

@dp.message_handler(state=UserState.in_progress)
async def check_answer(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    task = current_sessions.get(user_id)
    if not task:
        await state.finish()
        return
    user_answer = normalize_answer(message.text)
    correct_answer = normalize_answer(task[1])
    if user_answer == correct_answer:
        await message.answer("✅ Верно! Молодец!", reply_markup=main_kb)
        del current_sessions[user_id]
        await state.finish()
    else:
        await message.answer("❌ Неверно. Попробуй еще раз или вернись в меню.")

@dp.message_handler(text='📅 Расписание')
async def schedule_menu(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_schedules:
        schedule = user_schedules[user_id]
        text = (
            f"📅 Ваше расписание:\n\n"
            f"• Дней осталось: {schedule['days'] - schedule['current_day']}\n"
            f"• Время занятий: {schedule['time']}\n"
            f"• Задач в день: {schedule['count']}\n"
            f"• Сложность: {schedule['difficulty']}"
        )
        await message.answer(text, reply_markup=schedule_kb)
    else:
        await message.answer("Расписание не настроено. Хотите создать? (да/нет)")
        await UserState.choose_answer.set()

@dp.message_handler(state=UserState.choose_answer)
async def set_days(message: types.Message, state: FSMContext):
    if message.text.lower() != 'да':
        await message.answer("Создание расписания отменено", reply_markup=main_kb)
        await state.finish()
        return
    await message.answer("📆 На сколько дней создать расписание? (от 1 до 30)", reply_markup=cancel_kb)
    await UserState.creating_days.set()

@dp.message_handler(state=UserState.creating_days)
async def set_time(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not 1 <= int(message.text) <= 30:
        await message.answer("❌ Некорректное число дней! Введите число от 1 до 30", reply_markup=cancel_kb)
        return
    await state.update_data(days=int(message.text))
    await message.answer("⏰ В какое время присылать задачи? (Формат: ЧЧ:ММ)", reply_markup=cancel_kb)
    await UserState.creating_time.set()

@dp.message_handler(state=UserState.creating_time)
async def set_count(message: types.Message, state: FSMContext):
    try:
        time = datetime.strptime(message.text, "%H:%M").time()
    except ValueError:
        await message.answer("❌ Неверный формат времени! Используйте ЧЧ:ММ", reply_markup=cancel_kb)
        return
    await state.update_data(time=time.strftime("%H:%M"))
    await message.answer("🔢 Сколько задач в день вы хотите решать? (от 1 до 10)", reply_markup=cancel_kb)
    await UserState.creating_count.set()

@dp.message_handler(state=UserState.creating_count)
async def set_difficulty_schedule(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not 1 <= int(message.text) <= 10:
        await message.answer("❌ Некорректное число задач! Введите число от 1 до 10", reply_markup=cancel_kb)
        return
    await state.update_data(count=int(message.text))
    await message.answer("🎚️ Выберите сложность задач:", reply_markup=difficulty_cancel_kb)
    await UserState.creating_difficulty.set()

@dp.message_handler(text=['🍀 Легкие', '🎯 Средние', '💣 Сложные'], state=UserState.creating_difficulty)
async def save_schedule(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    schedule = {
        'days': data['days'],
        'current_day': 0,
        'time': data['time'],
        'count': data['count'],
        'difficulty': message.text,
        'tasks': []
    }
    user_schedules[user_id] = schedule
    await generate_tasks(user_id)
    await message.answer("✅ Расписание успешно создано!", reply_markup=main_kb)
    await state.finish()
    await schedule_tasks(user_id)

async def generate_tasks(user_id: int):
    schedule = user_schedules[user_id]
    all_tasks = TASKS[schedule['difficulty']].copy()
    shuffle(all_tasks)
    for day in range(schedule['days']):
        daily_tasks = all_tasks[day * schedule['count']: (day + 1) * schedule['count']]
        if not daily_tasks:
            daily_tasks = [choice(all_tasks) for _ in range(schedule['count'])]
        schedule['tasks'].append(daily_tasks)

async def schedule_tasks(user_id: int):
    schedule = user_schedules[user_id]
    now = datetime.now()
    target_time = datetime.strptime(schedule['time'], "%H:%M").time()
    first_run = datetime.combine(now.date(), target_time)
    if first_run < now:
        first_run += timedelta(days=1)
    scheduler.add_job(
        send_notification,
        'date',
        run_date=first_run,
        args=[user_id],
        id=f'schedule_{user_id}'
    )

async def send_notification(user_id: int):
    schedule = user_schedules.get(user_id)
    if not schedule:
        return
    if schedule['current_day'] >= schedule['days']:
        await bot.send_message(user_id, "🎉 Все занятия по расписанию завершены!", reply_markup=main_kb)
        del user_schedules[user_id]
        return
    await bot.send_message(
        user_id,
        f"⏰ Время занятия! День {schedule['current_day'] + 1}/{schedule['days']}",
        reply_markup=start_session_kb
    )

@dp.message_handler(text='🚀 Начать решение')
async def start_session(message: types.Message):
    user_id = message.from_user.id
    schedule = user_schedules.get(user_id)
    if not schedule or schedule['current_day'] >= schedule['days']:
        await message.answer("❌ Нет активного расписания", reply_markup=main_kb)
        return
    tasks = schedule['tasks'][schedule['current_day']]
    question, answer = tasks[0]
    await message.answer(f"🔔 Задача 1/{schedule['count']}:\n\n{question}", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('🏠 Главное меню'))
    current_sessions[user_id] = {
        'schedule': schedule,
        'tasks': tasks,
        'current': 1,
        'total': schedule['count'],
        'correct_answer': answer
    }
    await UserState.in_progress_schedule.set()

@dp.message_handler(state=UserState.in_progress_schedule)
async def handle_session_answer(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    session = current_sessions.get(user_id)
    if not session:
        await state.finish()
        return
    user_answer = normalize_answer(message.text)
    correct_answer = normalize_answer(session['correct_answer'])
    if user_answer == correct_answer:
        session['current'] += 1
        if session['current'] > session['total']:
            await message.answer("🎉 Все задачи на сегодня выполнены!", reply_markup=main_kb)
            user_schedules[user_id]['current_day'] += 1
            await schedule_tasks(user_id)
            await state.finish()
            del current_sessions[user_id]
            return
        next_question, next_answer = session['tasks'][session['current'] - 1]
        session['correct_answer'] = next_answer
        await message.answer(f"✅ Верно! Задача {session['current']}/{session['total']}:\n\n{next_question}")
    else:
        await message.answer("❌ Неверно. Попробуй еще раз:")
    current_sessions[user_id] = session

@dp.message_handler(text='❌ Удалить расписание')
async def delete_schedule(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_schedules:
        del user_schedules[user_id]
        scheduler.remove_job(f'schedule_{user_id}')
        await message.answer("🗑️ Расписание удалено!", reply_markup=main_kb)
    else:
        await message.answer("❌ У вас нет активного расписания", reply_markup=main_kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
