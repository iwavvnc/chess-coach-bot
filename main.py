import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from googleapiclient.discovery import build

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Привязываем категории проблем и уровень ELO к проверенным шахматным каналам
RECOMMENDED_CHANNELS = {
    "blunders": ["Levitov Chess", "Crestbook Шахматы", "Шахматы для всех"],
    "time": ["Шахматы с Сергеем Шиповым", "Levitov Chess"],
    "endgame": ["Шахматы для всех", "Crestbook Шахматы"],
    "general": ["Levitov Chess", "Шахматы с Сергеем Шиповым"]
}

def search_youtube_video(query_topic: str, channel_name: str) -> dict:
    """Ищет релевантное видео на конкретном YouTube-канале через API"""
    if not YOUTUBE_API_KEY:
        return None
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        search_query = f"{channel_name} {query_topic}"
        request = youtube.search().list(
            q=search_query,
            part="snippet",
            maxResults=1,
            type="video",
            relevanceLanguage="ru"
        )
        response = request.execute()
        
        items = response.get("items", [])
        if items:
            video = items[0]
            video_id = video["id"]["videoId"]
            title = video["snippet"]["title"]
            return {
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}"
            }
    except Exception as e:
        print(f"Ошибка поиска YouTube API: {e}")
    return None

def get_chess_stats(username: str):
    """Запрашивает данные профиля с Chess.com API"""
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    url = f"https://api.chess.com/pub/player/{username}/stats"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    stats = {}
    
    for mode in ['chess_blitz', 'chess_rapid', 'chess_bullet']:
        if mode in data and 'last' in data[mode]:
            stats[mode] = {
                'rating': data[mode]['last']['rating'],
                'record': data[mode].get('record', {})
            }
    return stats

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой персональный шахматный тренер.\n\n"
        "Отправь мне свой **никнейм на Chess.com**, и я проанализирую твой профиль, "
        "определю слабые места и подберу обучающие видео под твой уровень!"
    )

@dp.message()
async def analyze_player(message: types.Message):
    username = message.text.strip()
    await message.answer(f"🔍 Анализирую профиль `{username}` на Chess.com...")
    
    stats = get_chess_stats(username)
    if not stats:
        await message.answer("❌ Игрок не найден или у него нет сыгранных партий. Проверь никнейм!")
        return

    # Находим основной рейтинг (Rapid или Blitz)
    rapid_rating = stats.get('chess_rapid', {}).get('rating', 0)
    blitz_rating = stats.get('chess_blitz', {}).get('rating', 0)
    current_rating = max(rapid_rating, blitz_rating)

    if current_rating == 0:
        await message.answer(f"📊 Игрок **{username}** найден, но нет сыгранных партий в Rapid/Blitz.")
        return

    # Подбираем тему и каналы на основе ELO
    if current_rating < 1000:
        topic = "как перестать зевать фигуры базовые ошибки"
        category = "blunders"
        level_text = "Начинающий уровень"
    elif current_rating < 1500:
        topic = "стратегия и тактика средний уровень"
        category = "general"
        level_text = "Любительский уровень"
    else:
        topic = "глубокий анализ партий эндшпиль"
        category = "endgame"
        level_text = "Продвинутый уровень"

    # Ищем видео через YouTube API
    channels = RECOMMENDED_CHANNELS.get(category, RECOMMENDED_CHANNELS["general"])
    video_info = None
    
    for channel in channels:
        video_info = search_youtube_video(topic, channel)
        if video_info:
            break

    # Формируем ответ пользователю
    text = f"📊 **Результаты анализа для {username}:**\n\n"
    text += f"🏆 Максимальный рейтинг: **{current_rating} ELO** ({level_text})\n\n"
    
    if video_info:
        text += f"🎯 **Рекомендованный урок:**\n"
        text += f"🎬 [{video_info['title']}]({video_info['url']})\n\n"
        text += "💡 Посмотри этот разбор, чтобы закрыть основные пробелы в игре!"
    else:
        text += "🎬 *Не удалось подгрузить видео из YouTube API, попробуй позже.*"

    await message.answer(text, parse_mode="Markdown")

# Фейковый веб-сервер для поддержания Render в активном состоянии
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def main():
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
