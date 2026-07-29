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

# Настройки пользователей: {user_id: {"platform": "chesscom"|"lichess", "lang": "ru"|"en"}}
user_settings = {}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

def search_youtube_videos(query_topic: str, lang: str = "ru", max_results: int = 1) -> list:
    """Ищет релевантные видео на YouTube с учетом выбранного языка"""
    if not YOUTUBE_API_KEY:
        return []
    
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        search_query = f"Chess {query_topic}" if lang == "en" else f"Шахматы {query_topic}"
        
        request = youtube.search().list(
            q=search_query,
            part="snippet",
            maxResults=max_results,
            type="video",
            relevanceLanguage=lang
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
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    url = f"https://api.chess.com/pub/player/{username}/stats"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    return {
        'rapid': data.get('chess_rapid', {}).get('last', {}).get('rating', 0),
        'blitz': data.get('chess_blitz', {}).get('last', {}).get('rating', 0),
        'bullet': data.get('chess_bullet', {}).get('last', {}).get('rating', 0),
    }

def get_lichess_stats(username: str):
    url = f"https://lichess.org/api/user/{username}"
    response = requests.get(url)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    perfs = data.get('perfs', {})
    return {
        'rapid': perfs.get('rapid', {}).get('rating', 0),
        'blitz': perfs.get('blitz', {}).get('rating', 0),
        'bullet': perfs.get('bullet', {}).get('rating', 0),
    }

# --- КНОПКИ НАСТРОЕК ---

def get_settings_keyboard(user_id: int):
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    
    plat_text = "♟ Chess.com" if platform == "chesscom" else "🐴 Lichess"
    lang_text = "🇷🇺 Русский" if lang == "ru" else "🇬🇧 English"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Платформа: {plat_text}", callback_data="toggle_platform"),
            InlineKeyboardButton(text=f"Язык видео: {lang_text}", callback_data="toggle_lang")
        ]
    ])
    return keyboard

# --- ХЕНДЛЕРЫ TELEGRAM ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        "👋 Привет! Я твой персональный шахматный тренер.\n\n"
        "Настрой платформу и язык обучающих видео, а затем отправь свой **никнейм**:",
        reply_markup=get_settings_keyboard(user_id)
    )

@dp.callback_query(F.data == "toggle_platform")
async def toggle_platform_cmd(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    current_plat = get_user_setting(user_id, "platform", "chesscom")
    new_plat = "lichess" if current_plat == "chesscom" else "chesscom"
    set_user_setting(user_id, "platform", new_plat)
    
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "toggle_lang")
async def toggle_lang_cmd(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    current_lang = get_user_setting(user_id, "lang", "ru")
    new_lang = "en" if current_lang == "ru" else "ru"
    set_user_setting(user_id, "lang", new_lang)
    
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_id))
    await callback.answer()

@dp.message()
async def analyze_player(message: types.Message):
    user_id = message.from_user.id
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    username = message.text.strip()
    
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    await message.answer(f"🔍 Провожу глубокий анализ профиля `{username}` на {platform_name}...")
    
    # Запрос данных
    stats = get_chesscom_stats(username) if platform == "chesscom" else get_lichess_stats(username)
        
    if not stats:
        await message.answer(
            f"❌ Игрок не найден на {platform_name}. Проверь написание никнейма!",
            reply_markup=get_settings_keyboard(user_id)
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

    # Учитываем разницу ELO между Lichess и Chess.com
    rating_offset = 200 if platform == "lichess" else 0
    
    weak_points = []
    
    # Темы поиска зависят от выбранного языка
    if lang == "en":
        if current_rating < (1000 + rating_offset):
            level_name = "Beginner level"
            weak_points = [
                "⚠️ **Tactics & Blunders:** Frequently hanging pieces and missing basic 1-2 move mates.",
                "⚠️ **Opening:** Lack of center control, moving the same piece multiple times early on.",
                "⚠️ **Time Management:** Panic under low time, rushing in simple positions."
            ]
            search_topics = ["avoid blunders chess beginner", "opening principles center control", "chess time management"]
        elif current_rating < (1600 + rating_offset):
            level_name = "Intermediate level"
            weak_points = [
                "⚠️ **Opening Prep:** Weak knowledge of standard plans and pawn structures after 5-7 moves.",
                "⚠️ **Middlegame:** Difficulty constructing long-term attack plans.",
                "⚠️ **Endgame:** Lack of technique in converting material advantage (pawn and rook endgames)."
            ]
            search_topics = ["middlegame plans chess", "pawn endgame basics", "chess strategy intermediate"]
        else:
            level_name = "Advanced level"
            weak_points = [
                "⚠️ **Calculation:** Inaccuracies in forced lines 3+ moves ahead.",
                "⚠️ **Complex Endgames:** Small errors in rook/piece endgames with equal material.",
                "⚠️ **Prophylaxis:** Insufficient awareness of opponent's counterplay."
            ]
            search_topics = ["deep calculation chess", "rook endgame masterclass", "prophylaxis in chess"]
    else:
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
                "⚠️ **Дебютная подготовка:** Слабое знание типовых планов и пешечных структур после 5-7 ходов.",
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

    # Ищем видео под каждую тему
    all_videos = []
    for topic in search_topics:
        found_vids = search_youtube_videos(topic, lang=lang, max_results=1)
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

    text += "🎬 **Персональный учебный план:**\n"
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += "*(Не удалось подгрузить видео из YouTube API)*"

    await message.answer(
        text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True, 
        reply_markup=get_settings_keyboard(user_id)
    )

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
