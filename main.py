import os
import asyncio
import logging
import requests
from datetime import datetime
from collections import Counter

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message

# Берём токен из настроек сервера Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

VIDEO_DATABASE = [
    {
        "min_elo": 0, "max_elo": 1200, "category": "checkmated",
        "title": "Как перестать зевать маты в 1-2 хода",
        "channel": "Шахматы для всех", "url": "https://youtu.be/dummy1"
    },
    {
        "min_elo": 0, "max_elo": 1500, "category": "black_losses",
        "title": "Базовый солидный репертуар за черных",
        "channel": "Levitov Chess", "url": "https://youtu.be/dummy2"
    },
    {
        "min_elo": 1000, "max_elo": 1800, "category": "timeout",
        "title": "Как играть в цейтноте и не терять время",
        "channel": "Crestbook", "url": "https://youtu.be/dummy3"
    }
]

def analyze_chesscom(username):
    headers = {'User-Agent': 'ChessSkillBoosterBot/1.0'}
    
    stats_url = f"https://api.chess.com/pub/player/{username}/stats"
    stats_res = requests.get(stats_url, headers=headers)
    
    if stats_res.status_code != 200:
        return f"❌ Игрок с ником '{username}' не найден на Chess.com!"
        
    stats_data = stats_res.json()
    rapid_elo = stats_data.get('chess_rapid', {}).get('last', {}).get('rating', 1200)
    blitz_elo = stats_data.get('chess_blitz', {}).get('last', {}).get('rating', 1200)
    user_elo = max(rapid_elo, blitz_elo)
    
    now = datetime.now()
    games_url = f"https://api.chess.com/pub/player/{username}/games/{now.strftime('%Y')}/{now.strftime('%m')}"
    games_res = requests.get(games_url, headers=headers)
    games = games_res.json().get('games', []) if games_res.status_code == 200 else []
    
    if not games:
        return f"📊 Рейтинг: {user_elo} ELO\n\n⚠️ Не найдено сыгранных партий за этот месяц."

    losses = []
    white_losses, black_losses = 0, 0
    
    for game in games:
        white_player = game.get('white', {})
        black_player = game.get('black', {})
        is_white = white_player.get('username', '').lower() == username.lower()
        user_data = white_player if is_white else black_player
        
        user_result = user_data.get('result')
        if user_result in ['resigned', 'checkmated', 'timeout']:
            losses.append(user_result)
            if is_white: white_losses += 1
            else: black_losses += 1
            
    if not losses:
        return f"📊 Рейтинг: {user_elo} ELO\n\n🎉 У вас отличная серия без поражений!"
        
    main_problem = Counter(losses).most_common(1)[0][0]
    
    problem_names = {
        'checkmated': 'Мат / Потеря фигуры',
        'timeout': 'Просрочка времени (цейтнот)',
        'resigned': 'Сдача в тяжелой позиции'
    }
    
    report = f"📊 Игрок: {username}\n"
    report += f"⚡ Рабочий ELO: {user_elo}\n\n"
    report += f"⚠️ Главная проблема: {problem_names.get(main_problem, main_problem)}\n\n"
    report += "🎓 Персональный урок на эту неделю:\n"
    
    found = False
    for item in VIDEO_DATABASE:
        if item['min_elo'] <= user_elo <= item['max_elo']:
            report += f"\n• {item['title']}\n  Канал: {item['channel']}\n  Ссылка: {item['url']}\n"
            found = True
            break
            
    if not found:
        report += "\nПодходящих видео пока нет в базе."
        
    return report

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я твой персональный шахматный тренер.\n\n"
        "Отправь мне свой никнейм на Chess.com, и я подберу для тебя полезные уроки!"
    )

@dp.message(F.text)
async def handle_text(message: Message):
    username = message.text.strip()
    await message.answer(f"🔍 Анализирую партии для {username}...")
    
    loop = asyncio.get_event_loop()
    report = await loop.run_in_executor(None, analyze_chesscom, username)
    await message.answer(report)

from aiohttp import web

# Фейковый веб-сервер для обмана Render
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def main():
    # Запускаем фоновый веб-сервер на порту, который требует Render
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    print("🚀 БОТ И ВЕБ-СЕРВЕР УСПЕШНО ЗАПУЩЕНЫ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
