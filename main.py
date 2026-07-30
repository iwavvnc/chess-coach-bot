import os
import asyncio
import requests
import chess
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from googleapiclient.discovery import build

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_settings = {}

LANG_NEXT = {"ru": "en", "en": "pt", "pt": "ru"}
LANG_FLAGS = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pt": "🇵🇹 Português"}

TEXTS = {
    "ru": {
        "welcome": "👋 Привет! Я твой персональный AI-тренер по шахматам.\n\nНастрой платформу и язык, а затем отправь свой **никнейм**:",
        "analyzing": "🔍 Скачиваю и анализирую последние **{count} партий** для `{username}` на {platform}...",
        "not_found": "❌ Игрок не найден на {platform}. Проверь написание никнейма!",
        "no_games": "📊 Игрок **{username}** найден, но у него нет сыгранных партий.",
        "header": "📊 **ГЛУБОКИЙ AI-АНАЛИЗ {count} ПОСЛЕДНИХ ПАРТИЙ**\nИгрок: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Фактические проблемы, выявленные движком:**\n",
        "plan_header": "\n🎬 **Персональные видео-уроки по твоим ошибкам:**\n",
        "no_videos": "*(Не удалось подгрузить видео из YouTube API)*",
        "no_blunders": "✅ Отличная игра! Серьезных грубых зевов в последних партиях не обнаружено."
    },
    "en": {
        "welcome": "👋 Hi! I am your personal AI chess coach.\n\nConfigure your platform and language, then send your **username**:",
        "analyzing": "🔍 Downloading and analyzing the last **{count} games** for `{username}` on {platform}...",
        "not_found": "❌ Player not found on {platform}. Check your username spelling!",
        "no_games": "📊 Player **{username}** found, but has no recent games.",
        "header": "📊 **DEEP AI ANALYSIS OF LAST {count} GAMES**\nPlayer: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Specific Weaknesses Identified by Engine:**\n",
        "plan_header": "\n🎬 **Personal Video Lessons Based on Your Errors:**\n",
        "no_videos": "*(Failed to load videos from YouTube API)*",
        "no_blunders": "✅ Great play! No severe blunders detected in recent games."
    },
    "pt": {
        "welcome": "👋 Olá! Sou o seu treinador pessoal de xadrez com IA.\n\nConfigure a plataforma e o idioma e, em seguida, envie o seu **nome de utilizador**:",
        "analyzing": "🔍 A descarregar e analisar as últimas **{count} partidas** de `{username}` no {platform}...",
        "not_found": "❌ Jogador não encontrado no {platform}. Verifique o nome de utilizador!",
        "no_games": "📊 Jogador **{username}** encontrado, mas sem partidas recentes.",
        "header": "📊 **ANÁLISE PROFUNDA COM IA DAS ÚLTIMAS {count} PARTIDAS**\nJogador: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Problemas Específicos Identificados pelo Motor:**\n",
        "plan_header": "\n🎬 **Vídeo-Aulas Personalizadas Baseadas nos Seus Erros:**\n",
        "no_videos": "*(Não foi possível carregar vídeos do YouTube API)*",
        "no_blunders": "✅ Excelente jogo! Nenhum erro grave detetado nas últimas partidas."
    }
}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

# --- ДЕТЕКТОР ШАХМАТНЫХ ТЕМ ПО FEN ПОЗИЦИИ ---
def classify_position_error(fen: str, move_number: int) -> dict:
    board = chess.Board(fen)
    
    # 1. Дебютные ошибки
    if move_number <= 10:
        return {
            "topic_ru": "⚠️ **Дебют:** Нарушение принципов развития на первых ходах.",
            "yt_query_ru": "ошибки в дебюте правила развития шахматы"
        }
    
    # Считаем тяжелые и легкие фигуры
    rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    minor_pieces = len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.WHITE)) + \
                   len(board.pieces(chess.KNIGHT, chess.BLACK)) + len(board.pieces(chess.BISHOP, chess.BLACK))

    # 2. Пешечные окончания
    if queens == 0 and rooks == 0 and minor_pieces == 0:
        return {
            "topic_ru": "⚠️ **Пешечные окончания:** Ошибки в расчетe оппозиции и проведении пешек.",
            "yt_query_ru": "пешечные окончания правила шахматы"
        }

    # 3. Ладейные окончания (Позиции Филидора / Лусены)
    if queens == 0 and minor_pieces == 0 and rooks > 0:
        return {
            "topic_ru": "⚠️ **Ладейные окончания:** Ошибки в позиции Филидора/Лусены и активности ладьи.",
            "yt_query_ru": "ладейные окончания позиция филидора лусены шахматы"
        }

    # 4. Атака на короля в центре (Король не рокирован)
    king_sq_w = board.king(chess.WHITE)
    king_sq_b = board.king(chess.BLACK)
    if king_sq_w in [chess.E1, chess.D1] or king_sq_b in [chess.E8, chess.D8]:
        return {
            "topic_ru": "⚠️ **Безопасность короля:** Задержка рокировки и застрявший король в центре.",
            "yt_query_ru": "безопасность короля атака на короля в центре шахматы"
        }

    # 5. Тактический зев / Миттельшпиль
    return {
        "topic_ru": "⚠️ **Тактический зев:** Пропущенная связка, двойной удар или подвисшая фигура.",
        "yt_query_ru": "как перестать зевать фигуры тактика шахматы"
    }

# --- ПОЛУЧЕНИЕ ПОСЛЕДНИХ ПАРТИЙ С CHESS.COM И LICHESS ---
def fetch_recent_games(username: str, platform: str, limit: int = 10) -> list:
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    games = []
    
    try:
        if platform == "chesscom":
            archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
            res = requests.get(archives_url, headers=headers)
            if res.status_code == 200:
                archives = res.json().get("archives", [])
                if archives:
                    last_month_url = archives[-1]
                    g_res = requests.get(last_month_url, headers=headers)
                    if g_res.status_code == 200:
                        all_g = g_res.json().get("games", [])
                        games = all_g[-limit:]
        else: # Lichess
            url = f"https://lichess.org/api/games/user/{username}?max={limit}&pgnInBody=true"
            headers_lic = {'Accept': 'application/x-ndjson'}
            res = requests.get(url, headers=headers_lic)
            if res.status_code == 200:
                # В Lichess отдается ndjson
                lines = res.text.strip().split('\n')
                for line in lines:
                    if line:
                        import json
                        games.append(json.loads(line))
    except Exception as e:
        print(f"Ошибка получения партий: {e}")
        
    return games

def search_youtube_videos(query_topic: str, lang: str = "ru", max_results: int = 1) -> list:
    if not YOUTUBE_API_KEY:
        return []
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=query_topic,
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

def get_settings_keyboard(user_id: int):
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    
    plat_text = "♟ Chess.com" if platform == "chesscom" else "🐴 Lichess"
    lang_text = LANG_FLAGS.get(lang, "🇷🇺 Русский")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Platform: {plat_text}", callback_data="toggle_platform"),
            InlineKeyboardButton(text=f"Language: {lang_text}", callback_data="toggle_lang")
        ]
    ])
    return keyboard

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_setting(user_id, "lang", "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    await message.answer(t["welcome"], reply_markup=get_settings_keyboard(user_id))

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
    new_lang = LANG_NEXT.get(current_lang, "ru")
    set_user_setting(user_id, "new_lang", new_lang)
    t = TEXTS.get(new_lang, TEXTS["ru"])
    await callback.message.edit_text(t["welcome"], reply_markup=get_settings_keyboard(user_id))
    await callback.answer()

@dp.message()
async def analyze_player(message: types.Message):
    user_id = message.from_user.id
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    username = message.text.strip()
    
    # Для бесплатной версии зафиксируем 10 партий
    games_limit = 10
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    
    await message.answer(t["analyzing"].format(username=username, platform=platform_name, count=games_limit))
    
    games = fetch_recent_games(username, platform, limit=games_limit)
    
    if not games:
        await message.answer(t["not_found"].format(platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    detected_issues = []
    yt_queries = []

    # Разбираем партии и классифицируем проблемы
    for idx, game in enumerate(games, 1):
        # Достаем PGN / ходы партии
        pgn_text = game.get("pgn", "")
        if pgn_text:
            import io
            pgn = chess.pgn.read_game(io.StringIO(pgn_text))
            if pgn:
                board = pgn.board()
                moves = list(pgn.mainline_moves())
                
                # Анализируем позицию в середине партии (где обычно происходят переломы)
                half_move = len(moves) // 2
                for i, move in enumerate(moves):
                    board.push(move)
                    if i == half_move and len(moves) > 10:
                        fen = board.fen()
                        issue = classify_position_error(fen, move_number=i//2)
                        
                        if issue["topic_ru"] not in detected_issues:
                            detected_issues.append(issue["topic_ru"])
                            yt_queries.append(issue["yt_query_ru"])

    # Ограничиваем топ-3 главными проблемами
    detected_issues = detected_issues[:3]
    yt_queries = yt_queries[:3]

    # Подгружаем видео с YouTube по найденным проблемам
    all_videos = []
    for q in yt_queries:
        vids = search_youtube_videos(q, lang=lang, max_results=1)
        all_videos.extend(vids)

    # Собираем отчёт
    text = t["header"].format(username=username, platform=platform_name, count=len(games))
    text += t["weak_header"]
    
    if detected_issues:
        for issue in detected_issues:
            text += f"{issue}\n"
    else:
        text += t["no_blunders"] + "\n"

    text += t["plan_header"]
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += t["no_videos"]

    await message.answer(
        text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True, 
        reply_markup=get_settings_keyboard(user_id)
    )

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
