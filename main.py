import os
import asyncio
import aiohttp
import chess
import chess.pgn
import io
import json
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
        "analyzing": "⚡ Скачиваю и мгновенно анализирую партии `{username}` на {platform}...",
        "not_found": "❌ Игрок не найден на {platform}. Проверь написание никнейма!",
        "no_games": "📊 Игрок **{username}** найден, но у него нет сыгранных партий.",
        "header": "📊 **КОНКРЕТНЫЙ AI-АНАЛИЗ ОШИБОК ({count} ПАРТИЙ)**\nИгрок: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Выявленные точечные проблемы и темы для проработки:**\n",
        "plan_header": "\n🎬 **Рекомендованные видео-уроки:**\n",
        "trainers_header": "\n🧩 **Интерактивные тренажеры для смартфона:**\n",
        "no_videos": "*(Не удалось подгрузить видео из YouTube API)*",
    },
    "en": {
        "welcome": "👋 Hi! I am your personal AI chess coach.\n\nConfigure your platform and language, then send your **username**:",
        "analyzing": "⚡ Downloading and analyzing games for `{username}` on {platform}...",
        "not_found": "❌ Player not found on {platform}. Check your username spelling!",
        "no_games": "📊 Player **{username}** found, but has no recent games.",
        "header": "📊 **SPECIFIC AI ERROR ANALYSIS ({count} GAMES)**\nPlayer: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Identified Specific Topics to Improve:**\n",
        "plan_header": "\n🎬 **Recommended Video Lessons:**\n",
        "trainers_header": "\n🧩 **Interactive Mobile Practice Trainers:**\n",
        "no_videos": "*(Failed to load videos from YouTube API)*",
    },
    "pt": {
        "welcome": "👋 Olá! Sou o seu treinador pessoal de xadrez com IA.\n\nConfigure a plataforma e o idioma e, em seguida, envie o seu **nome de utilizador**:",
        "analyzing": "⚡ A analisar partidas de `{username}` no {platform}...",
        "not_found": "❌ Jogador não encontrado no {platform}. Verifique o nome de utilizador!",
        "no_games": "📊 Jogador **{username}** encontrado, mas sem partidas recentes.",
        "header": "📊 **ANÁLISE DE ERROS ESPECÍFICOS COM IA ({count} PARTIDAS)**\nJogador: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Tópicos Específicos Identificados para Melhorar:**\n",
        "plan_header": "\n🎬 **Vídeo-Aulas Recomendadas:**\n",
        "trainers_header": "\n🧩 **Treinadores Interativos para Telemóvel:**\n",
        "no_videos": "*(Não foi possível carregar vídeos do YouTube API)*",
    }
}

# --- БАЗА ИНТЕРАКТИВНЫХ МОБИЛЬНЫХ ТРЕНАЖЕРОВ ---
TRAINER_DATABASE = {
    "undefended": {
        "title": "⚡ **Тренажер: Борьба с зевками и зависающими фигурами**",
        "url": "https://lichess.org/practice/basic-tactics/hanging-pieces/9P1c8e7A"
    },
    "back_rank": {
        "title": "🧱 **Тренажер: Мат по 8-й горизонтали и завлечение**",
        "url": "https://lichess.org/practice/checkmates/checkmate-patterns/28e5a720"
    },
    "fork": {
        "title": "🐴 **Тренажер: Коневые вилки и двойные удары**",
        "url": "https://lichess.org/practice/basic-tactics/knight-fork/O3f7WfT4"
    },
    "pin": {
        "title": "🧲 **Тренажер: Связки и рентгены**",
        "url": "https://lichess.org/practice/basic-tactics/the-pin/84zK4b2Q"
    },
    "endgame": {
        "title": "♔ **Тренажер: Базовые эндшпили (Ладейники и пешники)**",
        "url": "https://lichess.org/practice/pawn-endgames/key-squares/L28m7Z9Q"
    }
}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

def analyze_board_concepts(board: chess.Board) -> list:
    detected = []

    # 1. Зависающие фигуры / Зевки
    undefended = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type != chess.KING:
            if board.is_attacked_by(not p.color, sq) and not board.is_attacked_by(p.color, sq):
                undefended += 1
    if undefended >= 1:
        detected.append({
            "key": "undefended",
            "topic": "🎯 **Зависающие фигуры:** Оставление фигур под ударом без защиты (зевки).",
            "query": "как не делать зевки в шахматах"
        })

    # 2. Безопасность короля и форточка
    for color, sqs in [(chess.WHITE, [chess.F1, chess.G1, chess.H1]), (chess.BLACK, [chess.F8, chess.G8, chess.H8])]:
        if board.king(color) in [chess.G1, chess.H1, chess.G8, chess.H8]:
            if sum(1 for sq in sqs if board.piece_at(sq) == chess.Piece(chess.PAWN, color)) == 3:
                detected.append({
                    "key": "back_rank",
                    "topic": "🎯 **Безопасность короля:** Слабость 8-й горизонтали и отсутствие «форточки».",
                    "query": "мат по последней горизонтали форточка шахматы"
                })
                break

    # 3. Коневые вилки (Двойные удары)
    has_fork_risk = False
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type == chess.KNIGHT:
            attacks = board.attacks(sq)
            attacked_valuable = sum(1 for a in attacks if board.piece_at(a) and board.piece_at(a).piece_type in [chess.ROOK, chess.QUEEN, chess.KING])
            if attacked_valuable >= 2:
                has_fork_risk = True
                break
    if has_fork_risk:
        detected.append({
            "key": "fork",
            "topic": "🎯 **Коневые вилки:** Пропуск двойных ударов конем.",
            "query": "коневая вилка двойной удар шахматы"
        })

    # 4. Связка и рентген
    detected.append({
        "key": "pin",
        "topic": "🎯 **Связки и рентгены:** Защита фигур, стоящих на одной линии.",
        "query": "тактический прием связка рентген в шахматах"
    })

    return detected

async def fetch_recent_games_async(username: str, platform: str, limit: int = 10) -> list:
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    games = []
    timeout = aiohttp.ClientTimeout(total=5)
    
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            if platform == "chesscom":
                archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
                async with session.get(archives_url) as res:
                    if res.status == 200:
                        data = await res.json()
                        archives = data.get("archives", [])
                        if archives:
                            async with session.get(archives[-1]) as g_res:
                                if g_res.status == 200:
                                    g_data = await g_res.json()
                                    games = g_data.get("games", [])[-limit:]
            else: # Lichess
                url = f"https://lichess.org/api/games/user/{username}?max={limit}&pgnInBody=true"
                headers_lic = {'Accept': 'application/x-ndjson'}
                async with session.get(url, headers=headers_lic) as res:
                    if res.status == 200:
                        text = await res.text()
                        for line in text.strip().split('\n'):
                            if line:
                                games.append(json.loads(line))
    except Exception as e:
        print(f"Ошибка асинхронной загрузки партий: {e}")
        
    return games

def search_youtube_videos(query_topic: str, lang: str = "ru", max_results: int = 2) -> list:
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
            videos.append({
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            })
    except Exception as e:
        print(f"Ошибка YouTube API: {e}")
    return videos

def get_settings_keyboard(user_id: int):
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    
    plat_text = "♟ Chess.com" if platform == "chesscom" else "🐴 Lichess"
    lang_text = LANG_FLAGS.get(lang, "🇷🇺 Русский")
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Platform: {plat_text}", callback_data="toggle_platform"),
            InlineKeyboardButton(text=f"Language: {lang_text}", callback_data="toggle_lang")
        ]
    ])

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
    set_user_setting(user_id, "lang", new_lang)
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
    
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    await message.answer(t["analyzing"].format(username=username, platform=platform_name))
    
    games = await fetch_recent_games_async(username, platform, limit=10)
    
    if not games:
        await message.answer(t["not_found"].format(platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    detected_issues = []
    yt_queries = []
    trainer_keys = []

    for game in games:
        pgn_text = game.get("pgn", "")
        if pgn_text:
            pgn = chess.pgn.read_game(io.StringIO(pgn_text))
            if pgn:
                moves = list(pgn.mainline_moves())
                if len(moves) > 10:
                    board = pgn.board()
                    for m in moves[:len(moves)//2]:
                        board.push(m)
                    
                    concepts = analyze_board_concepts(board)
                    for item in concepts:
                        if item["topic"] not in detected_issues:
                            detected_issues.append(item["topic"])
                            yt_queries.append(item["query"])
                            trainer_keys.append(item["key"])

    detected_issues = detected_issues[:3]
    yt_queries = yt_queries[:3]
    trainer_keys = trainer_keys[:3]

    if not detected_issues:
        detected_issues = [
            "🎯 **Расчет вариантов:** Предупреждение зевков и точный выбор ходов.",
            "🎯 **Связки и рентгены:** Защита фигур, стоящих на одной линии."
        ]
        yt_queries = [
            "как не делать зевки в шахматах",
            "тактический прием связка рентген в шахматах"
        ]
        trainer_keys = ["undefended", "pin"]

    # Добавляем универсальный тренажер по эндшпилю
    if "endgame" not in trainer_keys:
        trainer_keys.append("endgame")

    # Собираем видео
    all_videos = []
    for q in yt_queries:
        vids = search_youtube_videos(q, lang=lang, max_results=2)
        for v in vids:
            if not any(existing['url'] == v['url'] for existing in all_videos):
                all_videos.append(v)

    all_videos = all_videos[:5]

    # Формируем текст
    text = t["header"].format(username=username, platform=platform_name, count=len(games))
    text += t["weak_header"]
    for issue in detected_issues:
        text += f"{issue}\n"

    text += t["plan_header"]
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += t["no_videos"]

    # Добавляем тренажеры
    text += t["trainers_header"]
    for key in trainer_keys:
        if key in TRAINER_DATABASE:
            tr = TRAINER_DATABASE[key]
            text += f"• [{tr['title']}]({tr['url']})\n"

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
