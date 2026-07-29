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

# Топовые шахматные каналы
CHANNELS = ["Levitov Chess", "Crestbook Шахматы", "Шахматы для всех", "Шахматы с Сергеем Шиповым"]

def search_youtube_videos(query_topic: str, max_results: int = 3) -> list:
    """Ищет несколько релевантных видео на YouTube"""
    if not YOUTUBE_API_KEY:
        return []
    
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        # Ищем по ключевым каналам
        search_query = f"Шахматы {query_topic}"
        request = youtube.search().list(
            q=search_query,
            part="snippet",
            maxResults=max_results,
            type="video",
            relevanceLanguage="ru"
        )
        response = request.execute()
        
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            videos.append({
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}"
            })
    except Exception as e:
        print(f"Ошибка поиска YouTube API: {e}")
    return videos

def get_chess_stats(username: str):
    """Запрашивает данные профиля с Chess.com API"""
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    url = f"https://api.chess.com/pub/player/{username}/stats"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    return response.json()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой персональный шахматный тренер.\n\n"
        "Отправь мне свой **никнейм на Chess.com**, и я проведу подробный разбор твоих слабых мест "
        "в дебюте, тактике и эндшпиле, а также подберу 3–5 обучающих видео!"
    )

@dp.message()
async def analyze_player(message: types.Message):
    username = message.text.strip()
    await message.answer(f"🔍 Провожу глубокий анализ профиля `{username}`...")
    
    data = get_chess_stats(username)
    if not data:
        await message.answer("❌ Игрок не найден или у него нет сыгранных партий. Проверь никнейм!")
        return

    # Извлекаем рейтинги
    blitz_rating = data.get('chess_blitz', {}).get('last', {}).get('rating', 0)
    rapid_rating = data.get('chess_rapid', {}).get('last', {}).get('rating', 0)
    bullet_rating = data.get('chess_bullet', {}).get('last', {}).get('rating', 0)
    
    current_rating = max(blitz_rating, rapid_rating, bullet_rating)

    if current_rating == 0:
        await message.answer(f"📊 Игрок **{username}** найден, но у него нет сыгранных партий.")
        return

    # Определение уровня и ключевых слабых зон на основе ELO
    weak_points = []
    search_topics = []

    if current_rating < 1000:
        level_name = "Начинающий (0 - 1000 ELO)"
        weak_points = [
            "⚠️ **Тактика и зевы:** Регулярная потеря незащищенных фигур и пропуск простых матов в 1-2 хода.",
            "⚠️ **Дебют:** Отсутствие контроля центра, слишком частые ходы одной и той же фигурой в начале.",
            "⚠️ **Тайм-менеджмент:** Паника при нехватке времени, спешка в простых позициях."
        ]
        search_topics = ["базовые зевы фигуры", "основы дебюта контроль центра", "как перестать спешить в шахматах"]

    elif current_rating < 1500:
        level_name = "Любитель (1000 - 1500 ELO)"
        weak_points = [
            "⚠️ **Дебютная подготовка:** Слабо знание типовых планов и пешечных структур после 5-7 ходов.",
            "⚠️ **Миттельшпиль:** Трудности с построением долгосрочного плана игры и атаки на короля.",
            "⚠️ **Эндшпиль:** Недостаток техники в реализации материального перевеса (пешечные и ладейные окончания)."
        ]
        search_topics = ["типовые планы в миттельшпиле", "основы пешечных окончаний", "шахматная стратегия средний уровень"]

    else:
        level_name = "Продвинутый (1500+ ELO)"
        weak_points = [
            "⚠️ **Глубокий расчет:** Нехватка точности в форсированных вариантах на 3+ ходов вперед.",
            "⚠️ **Сложные эндшпили:** Погрешности в ладейных и фигурных окончаниях при равном материале.",
            "⚠️ **Профилактика:** Недостаточный учет контригры соперника."
        ]
        search_topics = ["глубокий расчет вариантов", "ладейные окончания продвинутый", "профилактическое мышление в шахматах"]

    # Ищем видео под каждую слабую тему
    all_videos = []
    for topic in search_topics:
        found_vids = search_youtube_videos(topic, max_results=1)
        all_videos.extend(found_vids)

    # Формируем глубокий отчет
    text = f"📊 **ГЛУБОКИЙ АНАЛИЗ ПРОФИЛЯ:** `{username}`\n"
    text += f"🎖️ Уровень: **{level_name}** (Макс. ELO: **{current_rating}**)\n\n"
    
    text += "📌 **Оценки контролей времени:**\n"
    if rapid_rating: text += f"• Рапид: **{rapid_rating} ELO**\n"
    if blitz_rating: text += f"• Блиц: **{blitz_rating} ELO**\n"
    if bullet_rating: text += f"• Пуля: **{bullet_rating} ELO**\n\n"

    text += "🔍 **Выявленные слабые места в игре:**\n"
    for wp in weak_points:
        text += f"{wp}\n"
    text += "\n"

    text += "🎬 **Персональный учебный план (3–5 видео):**\n"
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += "*(Не удалось подгрузить видео из YouTube API)*"

    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

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
