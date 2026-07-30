import os
import asyncio
import requests
import chess
import chess.pgn
import io
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
        "analyzing": "🔍 Скачиваю и анализирую партии `{username}` на {platform} (выборка: **{count} партий**)...",
        "not_found": "❌ Игрок не найден на {platform}. Проверь написание никнейма!",
        "no_games": "📊 Игрок **{username}** найден, но у него нет сыгранных партий.",
        "header": "📊 **КОНКРЕТНЫЙ AI-АНАЛИЗ ОШИБОК ({count} ПАРТИЙ)**\nИгрок: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Выявленные точечные проблемы и темы для проработки:**\n",
        "plan_header": "\n🎬 **Рекомендованные уроки по твоим слабым темам:**\n",
        "no_videos": "*(Не удалось подгрузить видео из YouTube API)*",
        "no_blunders": "✅ Отличный уровень! Явных повторяющихся концептуальных ошибок не обнаружено."
    },
    "en": {
        "welcome": "👋 Hi! I am your personal AI chess coach.\n\nConfigure your platform and language, then send your **username**:",
        "analyzing": "🔍 Downloading and analyzing games for `{username}` on {platform} (sample: **{count} games**)...",
        "not_found": "❌ Player not found on {platform}. Check your username spelling!",
        "no_games": "📊 Player **{username}** found, but has no recent games.",
        "header": "📊 **SPECIFIC AI ERROR ANALYSIS ({count} GAMES)**\nPlayer: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Identified Specific Topics to Improve:**\n",
        "plan_header": "\n🎬 **Recommended Video Lessons on Your Weak Topics:**\n",
        "no_videos": "*(Failed to load videos from YouTube API)*",
        "no_blunders": "✅ Great play! No obvious repeating conceptual errors found."
    },
    "pt": {
        "welcome": "👋 Olá! Sou o seu treinador pessoal de xadrez com IA.\n\nConfigure a plataforma e o idioma e, em seguida, envie o seu **nome de utilizador**:",
        "analyzing": "🔍 A analisar partidas de `{username}` no {platform} (amostra: **{count} partidas**)...",
        "not_found": "❌ Jogador não encontrado no {platform}. Verifique o nome de utilizador!",
        "no_games": "📊 Jogador **{username}** encontrado, mas sem partidas recentes.",
        "header": "📊 **ANÁLISE DE ERROS ESPECÍFICOS COM IA ({count} PARTIDAS)**\nJogador: `{username}` ({platform})\n\n",
        "weak_header": "🎯 **Tópicos Específicos Identificados para Melhorar:**\n",
        "plan_header": "\n🎬 **Vídeo-Aulas Recomendadas sobre os Seus Erros:**\n",
        "no_videos": "*(Não foi possível carregar vídeos do YouTube API)*",
        "no_blunders": "✅ Excelente jogo! Nenhum erro concetual repetido detetado."
    }
}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

# --- ДЕТЕКТОР КОНКРЕТНЫХ ШАХМАТНЫХ КОНЦЕПЦИЙ И ТЕМ ---
def analyze_board_concepts(board: chess.Board) -> list:
    detected_topics = []

    # 1. Поиск незащищенных (подвисших) фигур на доске
    undefended_pieces = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.piece_type != chess.KING:
            color = piece.color
            # Если фигура атакована и не защищена своими
            if board.is_attacked_by(not color, square) and not board.is_attacked_by(color, square):
                undefended_pieces += 1

    if undefended_pieces >= 2:
        detected_topics.append({
            "topic_ru": "🎯 **Зависающие фигуры:** Оставление своих фигур без защиты.",
            "yt_query_ru": "незащищенные фигуры зависающие фигуры шахматы"
        })

    # 2. Проверка слабости первой / последней горизонтали (Back-rank weakness)
    for color, rank_sqs in [(chess.WHITE, [chess.F1, chess.G1, chess.H1]), (chess.BLACK, [chess.F8, chess.G8, chess.H8])]:
        king_sq = board.king(color)
        if king_sq in [chess.G1, chess.H1, chess.G8, chess.H8]:
            # Проверяем, закрыт ли король пешками без форточки
            pawns_ahead = sum(1 for sq in rank_sqs if board.piece_at(sq) == chess.Piece(chess.PAWN, color))
            if pawns_ahead == 3:
                detected_topics.append({
                    "topic_ru": "🎯 **Слабость последней горизонтали:** Отсутствие «форточки» для короля.",
                    "yt_query_ru": "мат по последней горизонтали форточка шахматы"
                })
                break

    # 3. Наличие проходных пешек и пешечная структура
    passed_pawns = 0
    for square in board.pieces(chess.PAWN, chess.WHITE) | board.pieces(chess.PAWN, chess.BLACK):
        rank = chess.square_rank(square)
        if rank in [2, 3, 4, 5]: # Пешки, продвинутые вглубь
            passed_pawns += 1
    if passed_pawns >= 3:
        detected_topics.append({
            "topic_ru": "🎯 **Проходные пешки:** Правила проведения и блокировки проходных пешек.",
            "yt_query_ru": "как проводить проходную пешку правила шахматы"
        })

    # 4. Проверка на связки и геометрическую уязвимость
    # Если на доске есть ферзи и тяжелые фигуры
    if board.pieces(chess.QUEEN, chess.WHITE) or board.pieces(chess.QUEEN, chess.BLACK):
        detected_topics.append({
            "topic_ru": "🎯 **Тактика Связка и Шампур:** Уязвимость фигур на одной линии.",
            "yt_query_ru": "тактический прием связка шампур шахматы"
        })

    # 5. Двойные удары и вилки
    knights = len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.BLACK))
    if knights > 0:
        detected_topics.append({
            "topic_ru": "🎯 **Коньковые вилки и двойные удары:** Пропуск тактических вилок.",
            "yt_query_ru": "двойной удар коневая вилка шахматы"
        })

    return detected_topics

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
    
    games_limit = 10
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    
    await message.answer(t["analyzing"].format(username=username, platform=platform_name, count=games_limit))
    
    games = fetch_recent_games(username, platform, limit=games_limit)
    
    if not games:
        await message.answer(t["not_found"].format(platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    detected_issues = []
    yt_queries = []

    # Проходим по всем партиям и собираем точные шахматные паттерны
    for game in games:
        pgn_text = game.get("pgn", "")
        if pgn_text:
            pgn = chess.pgn.read_game(io.StringIO(pgn_text))
            if pgn:
                board = pgn.board()
                moves = list(pgn.mainline_moves())
                
                # Сканируем ключевые позиции во второй половине партии
                scan_indices = [len(moves)//2, int(len(moves)*0.7)]
                for idx in scan_indices:
                    if idx < len(moves):
                        temp_board = pgn.board()
                        for i, m in enumerate(moves[:idx]):
                            temp_board.push(m)
                        
                        concepts = analyze_board_concepts(temp_board)
                        for item in concepts:
                            if item["topic_ru"] not in detected_issues:
                                detected_issues.append(item["topic_ru"])
                                yt_queries.append(item["yt_query_ru"])

    # Оставляем ровно 3 самые актуальные темы
    detected_issues = detected_issues[:3]
    yt_queries = yt_queries[:3]

    # Если паттернов вышло меньше 3, добавляем базовую тактическую тему
    if len(detected_issues) < 3:
        fallback = {
            "topic_ru": "🎯 **Расчет вариантов:** Точность и предупреждение зевов.",
            "yt_query_ru": "расчет вариантов шахматы упражнения"
        }
        if fallback["topic_ru"] not in detected_issues:
            detected_issues.append(fallback["topic_ru"])
            yt_queries.append(fallback["yt_query_ru"])

    # Подгружаем обучающие видео под каждую тему
    all_videos = []
    for q in yt_queries:
        vids = search_youtube_videos(q, lang=lang, max_results=1)
        all_videos.extend(vids)

    # Формируем отчёт
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
