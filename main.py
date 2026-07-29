import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from googleapiclient.discovery import build

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Временное хранение выбранной платформы для пользователей {user_id: "chesscom" | "lichess"}
user_platforms = {}

def search_youtube_videos(query_topic: str, max_results: int = 3) -> list:
    """Ищет несколько релевантных видео на YouTube"""
    if not YOUTUBE_API_KEY:
        return []
    
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
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

# --- МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ ---

def get_chesscom_stats(username: str):
    """Запрашивает данные профиля с Chess.com API"""
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    url = f"https://api.chess.com/pub/player/{username}/stats"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    stats = {
        'rapid': data.get('chess_rapid', {}).get('last', {}).get('rating', 0),
        'blitz': data.get('chess_blitz', {}).get('last', {}).get('rating', 0),
        'bullet': data.get('chess_bullet', {}).get('last', {}).get('rating', 0),
    }
    return stats

def get_lichess_stats(username: str):
    """Запрашивает данные профиля с Lichess API"""
    url = f"https://lichess.org/api/user/{username}"
    response = requests.get(url)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    perfs = data.get('perfs', {})
    stats = {
        'rapid': perfs.get('rapid', {}).get('rating', 0),
        'blitz': perfs.get('blitz', {}).get('rating', 0),
        'bullet': perfs.get('bullet', {}).get('rating', 0),
    }
    return stats

# --- КНОПКИ ВЫБОРА ПЛАТФОРМЫ ---

def get_platform_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♟ Chess.com", callback_data="platform_chesscom"),
            InlineKeyboardButton(text="🐴 Lichess", callback_data="platform_lichess")
        ]
    ])
    return keyboard

# --- ХЕНДЛЕРЫ TELEGRAM ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой персональный шахматный тренер.\n\n"
        "Выбери платформу, на которой ты играешь:",
        reply_markup=get_platform_keyboard()
    )

@dp.callback_query(F.data.startswith("platform_"))
async def set_platform(callback: types.CallbackQuery):
    platform = callback.data.split("_")[1]
    user_platforms[callback.from_user.id] = platform
    
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    
    await callback.message.edit_text(
        f"✅ Выбрана платформа: **{platform_name}**\n\n"
        f"Отправь мне свой **никнейм на {platform_name}**, чтобы я проанализировал твой профиль!",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message()
async def analyze_player(message: types.Message):
    user_id = message.from_user.id
    platform = user_platforms.get(user_id, "chesscom") # По умолчанию Chess.com
    username = message.text.strip()
    
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    await message.answer(f"🔍 Провожу глубокий анализ профиля `{username}` на {platform_name}...")
    
    # Запрашиваем данные с нужной платформы
    if platform == "chesscom":
        stats = get_chesscom_stats(username)
    else:
        stats = get_lichess_stats(username)
        
    if not stats:
        await message.answer(
            f"❌ Игрок не найден на {platform_name}. Проверь написание никнейма!",
            reply_markup=get_platform_keyboard()
        )
        return

    rapid_rating = stats.get('rapid', 0)
    blitz_rating = stats.get('blitz', 0)
    bullet_rating = stats.get('bullet', 0)
    
    current_rating = max(rapid_rating, blitz_rating, bullet_rating)

    if current_rating == 0:
        await message.answer(
            f"📊 Игрок **{username}** найден на {platform_name}, но у него нет сыгранных партий."
        )
        return

    # Определение уровня и слабых мест с учетом платформы
    # На Lichess рейтинги в среднем на 200-300 пунктов выше, учитываем это
    rating_offset = 200 if platform == "lichess" else 0
    
    weak_points = []
    search_topics = []

    if current_rating < (1000 + rating_offset):
        level_name = "Начинающий уровень"
        weak_points = [
            "⚠️ **Тактика и зевы:** Регулярная потеря незащищенных фигур и пропуск простых матов в 1-2 хода.",
            "⚠️ **Дебют:** Отсутствие контроля центра, слишком частые ходы одной и той же фигурой в начале.",
            "⚠️ **Тайм-менеджмент:** Паника при нехватке времени, спешка в простых позициях."
        ]
        search_topics = ["базовые зевы фигуры", "основы дебюта контроль центра", "как перестать спешить в шахматах"]

    elif current_rating < (1600 + rating_offset):
        level_name = "Любительский уровень"
        weak_points = [
            "⚠️ **Дебютная подготовка:** Слабо знание типовых планов и пешечных структур после 5-7 ходов.",
            "⚠️ **Миттельшпиль:** Трудности с построением долгосрочного плана игры и атаки на короля.",
            "⚠️ **Эндшпиль:** Недостаток техники в реализации материального перевеса (пешечные и ладейные окончания)."
        ]
        search_topics = ["типовые планы в миттельшпиле", "основы пешечных окончаний", "шахматная стратегия средний уровень"]

    else:
        level_name = "Продвинутый уровень"
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

    # Формируем отчет
    text = f"📊 **ГЛУБОКИЙ АНАЛИЗ ПРОФИЛЯ:** `{username}` ({platform_name})\n"
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

    # Добавляем кнопку смены платформы в конце
    change_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сменить платформу", callback_data="change_platform")]
    ])

    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=change_keyboard)

@dp.callback_query(F.data == "change_platform")
async def change_platform_cmd(callback: types.CallbackQuery):
    await callback.message.answer("Выбери платформу:", reply_markup=get_platform_keyboard())
    await callback.answer()

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
