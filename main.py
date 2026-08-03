import os
import asyncio
import aiohttp
import chess
import chess.pgn
import io
import json
import random
import sqlite3
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from googleapiclient.discovery import build

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    # Таблица настроек
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            platform TEXT DEFAULT 'chesscom',
            lang TEXT DEFAULT 'ru'
        )
    """)
    # Таблица истории прогресса пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            platform TEXT,
            openings_json TEXT,
            last_check_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_user_setting(user_id: int, key: str, default: str) -> str:
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT {key} FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return default

def set_user_setting(user_id: int, key: str, value: str):
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (user_id, platform, lang) 
        VALUES (?, 'chesscom', 'ru')
        ON CONFLICT(user_id) DO UPDATE SET {key} = ?
    """.format(key=key), (user_id, value))
    conn.commit()
    conn.close()

def get_saved_progress(user_id: int) -> dict:
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    cursor.execute("SELECT openings_json FROM user_progress WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return {}

def save_progress(user_id: int, username: str, platform: str, openings_stats: dict):
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    openings_json = json.dumps(openings_stats)
    cursor.execute("""
        INSERT INTO user_progress (user_id, username, platform, openings_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            username = excluded.username,
            platform = excluded.platform,
            openings_json = excluded.openings_json,
            last_check_timestamp = CURRENT_TIMESTAMP
    """, (user_id, username, platform, openings_json))
    conn.commit()
    conn.close()

# --- ШАХМАТНЫЙ И ЯЗЫКОВОЙ КОНФИГ ---
LANG_NEXT = {"ru": "en", "en": "pt", "pt": "ru"}
LANG_FLAGS = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pt": "🇵🇹 Português"}

OPENING_PATTERNS = {
    "e4 e5 Nf3 Nc6 Bc4": "Итальянская партия",
    "e4 e5 Nf3 Nc6 Bb5": "Испанская партия",
    "e4 c5": "Сицилианская защита",
    "e4 e6": "Французская защита",
    "e4 c6": "Защита Каро-Канн",
    "d4 d5 c4": "Ферзевый гамбит",
    "d4 Nf6 c4 g6": "Староиндийская защита",
    "d4 Nf6 c4 e6": "Защита Нимцовича",
    "e4 e5 Nf3 Nf6": "Русская партия",
    "e4 d5": "Скандинавская защита",
    "c4": "Английское начало",
    "Nf3": "Дебют Рети",
    "d4 d5": "Дебют ферзевых пешек",
    "e4 e5": "Открытый дебют"
}

CHESS_QUOTES = {
    "ru": [
        "«Если видишь хороший ход — не спеши, поищи ход лучше.» — *Эмануил Ласкер*",
        "«Самое трудное в шахматах — выиграть выигранную позицию.» — *Эмануил Ласкер*",
        "«Шахматы — это трагедия одного хода.» — *Савелий Тартаковер*"
    ],
    "en": [
        "\"When you see a good move, look for a better one.\" — *Emanuel Lasker*",
        "\"The hardest game to win is a won game.\" — *Emanuel Lasker*"
    ],
    "pt": [
        "\"Quando vir uma boa jogada, procure uma melhor.\" — *Emanuel Lasker*",
        "\"O jogo mais difícil de vencer é um jogo ganho.\" — *Emanuel Lasker*"
    ]
}

LANG_DATA = {
    "ru": {
        "welcome": "👋 Привет! Я твой персональный AI-тренер по шахматам.\n\nЯ помню твой прогресс и динамику! Выбери платформу и напиши свой **никнейм**, чтобы начать разбор.",
        "analyzing": "🧠 Анализирую последние партии `{username}` с {platform} и сравниваю с твоими прошлыми результатами...",
        "not_found": "❌ Не смог найти игрока `{username}` на {platform}. Проверь написание!",
        "header": "📋 **ОТЧЕТ ПЕРСОНАЛЬНОГО ТРЕНЕРА ({count} игр)**\nИгрок: `{username}` ({platform})\n\n",
        "progress_header": "📈 **ДИНАМИКА ТВОЕГО ПРОГРЕССА:**\n",
        "first_time": "🆕 *Это наша первая полноценная проверка! Я сохранил твои данные. В следующий раз я покажу подробный прогресс по каждому дебюту.*\n\n",
        "opening_header": "📖 **ТЕКУЩИЙ ДЕБЮТНЫЙ РЕПЕРТУАР:**\n",
        "best_opening": "🟢 **Твой лучший дебют:** {opening} (Побед: {winrate}%)\n",
        "worst_opening": "🔴 **Проблемный дебют:** {opening} (Побед: {winrate}%)\n👉 *Рекомендация:* Посмотри теорию, здесь теряются очки!\n\n",
        "single_opening": "📊 **Основной дебют:** {opening} (Побед: {winrate}%)\n\n",
        "opening_videos_header": "\n📘 **Видео по дебюту ({opening}):**\n",
        "plan_header": "\n🎬 **Рекомендуемые уроки:**\n",
        "trainers_header": "\n🧩 **Задания в приложении ({platform}):**\n",
        "weekly_task": "\n📝 **ТРЕНЕРСКОЕ ЗАДАНИЕ:**\n",
        "quote_header": "\n💡 **Мудрость:**\n",
        "no_videos": "*(Видео не подгрузились, но задания ниже активны)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Зевки под прямой удар.** Ты периодически оставляешь фигуры без защиты.",
                "task": "Задавай себе вопрос перед каждым ходом: *«Куда напал соперник?»*.",
                "yt": "как не зевать фигуры шахматы"
            },
            "back_rank": {
                "topic": "🚨 **Слабость 8-й горизонтали.** Король заперт за пешками.",
                "task": "Делай форточку (`h3` или `g3`) при первой возможности.",
                "yt": "мат на последней горизонтали шахматы"
            },
            "fork": {
                "topic": "🐴 **Коневые вилки.** Пропускаешь двойные удары.",
                "task": "Следи за полями одного цвета — конь ставит вилку только на них.",
                "yt": "коневая вилка шахматы"
            },
            "pin": {
                "topic": "🧲 **Пропуск связок.** Ходишь связанными фигурами.",
                "task": "Проверяй линии связок перед каждым ходом.",
                "yt": "связка в шахматах"
            }
        }
    },
    "en": {
        "welcome": "👋 Hi! I am your personal AI chess coach.\n\nI track your progress over time! Set your platform and send me your **username**.",
        "analyzing": "🧠 Analyzing recent games for `{username}` on {platform} and comparing with previous records...",
        "not_found": "❌ Couldn't find player `{username}` on {platform}.",
        "header": "📋 **PERSONAL COACH REPORT ({count} games)**\nPlayer: `{username}` ({platform})\n\n",
        "progress_header": "📈 **YOUR PROGRESS DYNAMICS:**\n",
        "first_time": "🆕 *This is our first assessment! I've stored your baseline. Next time I'll show your rating dynamics and opening improvements.*\n\n",
        "opening_header": "📖 **CURRENT OPENING REPERTOIRE:**\n",
        "best_opening": "🟢 **Best opening:** {opening} (Winrate: {winrate}%)\n",
        "worst_opening": "🔴 **Trouble opening:** {opening} (Winrate: {winrate}%)\n👉 *Advice:* Study theory for this opening!\n\n",
        "single_opening": "📊 **Main opening:** {opening} (Winrate: {winrate}%)\n\n",
        "opening_videos_header": "\n📘 **Opening Lessons ({opening}):**\n",
        "plan_header": "\n🎬 **Tactics Lessons:**\n",
        "trainers_header": "\n🧩 **Practice in ({platform}):**\n",
        "weekly_task": "\n📝 **COACHING TASK:**\n",
        "quote_header": "\n💡 **Quote:**\n",
        "no_videos": "*(Failed to load videos)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Hanging Pieces.** Undefended pieces left behind.",
                "task": "Ask yourself: *'What is opponent attacking?'* before every move.",
                "yt": "stop hanging pieces chess"
            },
            "back_rank": {
                "topic": "🚨 **Back-Rank Vulnerability.** King trapped behind pawns.",
                "task": "Make a prophylactic pawn move (`h3` / `g3`).",
                "yt": "back rank mate chess"
            },
            "fork": {
                "topic": "🐴 **Knight Forks.** Missing double attacks.",
                "task": "Keep valuable pieces on different colored squares.",
                "yt": "knight fork tactics chess"
            },
            "pin": {
                "topic": "🧲 **Missing Pins.** Moving pinned pieces.",
                "task": "Never move a pinned piece!",
                "yt": "pin tactics chess"
            }
        }
    },
    "pt": {
        "welcome": "👋 Olá! Sou o teu treinador pessoal de xadrez.\n\nAcompanho o teu progresso ao longo do tempo! Configura a plataforma e envia o teu **nome de utilizador**.",
        "analyzing": "🧠 A analisar partidas recentes de `{username}` no {platform}...",
        "not_found": "❌ Não encontrei o jogador `{username}` no {platform}.",
        "header": "📋 **RELATÓRIO DO TREINADOR PESSOAL ({count} partidas)**\nJogador: `{username}` ({platform})\n\n",
        "progress_header": "📈 **A TUA EVOLUÇÃO:**\n",
        "first_time": "🆕 *Esta é a nossa primeira avaliação! Guardei os teus dados. Da próxima vez verás a comparação de desempenho.*\n\n",
        "opening_header": "📖 **REPERTÓRIO DE ABERTURA:**\n",
        "best_opening": "🟢 **Melhor abertura:** {opening} (Vitórias: {winrate}%)\n",
        "worst_opening": "🔴 **Abertura problemática:** {opening} (Vitórias: {winrate}%)\n👉 *Conselho:* Estuda a teoria desta abertura!\n\n",
        "single_opening": "📊 **Abertura principal:** {opening} (Vitórias: {winrate}%)\n\n",
        "opening_videos_header": "\n📘 **Vídeos da Abertura ({opening}):**\n",
        "plan_header": "\n🎬 **Vídeos de Táctica:**\n",
        "trainers_header": "\n🧩 **Exercícios em ({platform}):**\n",
        "weekly_task": "\n📝 **TAREFA:**\n",
        "quote_header": "\n💡 **Citação:**\n",
        "no_videos": "*(Vídeos indisponíveis)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Peças Penduradas.** Lances desatentos.",
                "task": "Pergunta-te: *'O que o adversário está a atacar?'*.",
                "yt": "peças penduradas xadrez"
            },
            "back_rank": {
                "topic": "🚨 **Mate na Última Fileira.** Rei preso.",
                "task": "Faz um lance preventivo de peão (`h3` / `g3`).",
                "yt": "mate da ultima fileira xadrez"
            },
            "fork": {
                "topic": "🐴 **Garfos de Cavalo.** Ataques duplos esquecidos.",
                "task": "Mantém peças valiosas em casas de cores diferentes.",
                "yt": "garfo de cavalo xadrez"
            },
            "pin": {
                "topic": "🧲 **Esquecimento de Cravagens.** Mover peças cravadas.",
                "task": "Nunca movas uma peça cravada!",
                "yt": "cravagem xadrez"
            }
        }
    }
}

TRAINER_DATABASE = {
    "lichess": {
        "ru": {
            "undefended": "⚡ **Зевки:** `Обучение` ➔ `Практика` ➔ **«Hanging pieces»**.",
            "back_rank": "🧱 **Мат по 8-й:** `Задачи` ➔ `Темы задач` ➔ **«Мат на последней горизонтали»**.",
            "fork": "🐴 **Вилки:** `Обучение` ➔ `Практика` ➔ **«Knight Fork»**.",
            "pin": "🧲 **Связки:** `Обучение` ➔ `Практика` ➔ **«The Pin»**.",
            "endgame": "♔ **Эндшпиль:** `Обучение` ➔ `Практика` ➔ **«Пешечные окончания»**."
        },
        "en": {
            "undefended": "⚡ **Hanging pieces:** `Learn` ➔ `Practice` ➔ **«Hanging pieces»**.",
            "back_rank": "🧱 **Back Rank:** `Puzzles` ➔ `Puzzle Themes` ➔ **«Back Rank Mate»**.",
            "fork": "🐴 **Forks:** `Learn` ➔ `Practice` ➔ **«Knight Fork»**.",
            "pin": "🧲 **Pins:** `Learn` ➔ `Practice` ➔ **«The Pin»**.",
            "endgame": "♔ **Endgame:** `Learn` ➔ `Practice` ➔ **«Pawn Endgames»**."
        },
        "pt": {
            "undefended": "⚡ **Peças penduradas:** `Aprender` ➔ `Prática` ➔ **«Hanging pieces»**.",
            "back_rank": "🧱 **Mate na 8ª:** `Exercícios` ➔ `Temas` ➔ **«Mate na última fileira»**.",
            "fork": "🐴 **Garfos:** `Aprender` ➔ `Prática` ➔ **«Knight Fork»**.",
            "pin": "🧲 **Cravagens:** `Aprender` ➔ `Prática` ➔ **«The Pin»**.",
            "endgame": "♔ **Final:** `Aprender` ➔ `Prática` ➔ **«Finais de Peões»**."
        }
    },
    "chesscom": {
        "ru": {
            "undefended": "⚡ **Зевки:** `Задачи` ➔ `Настраиваемые задачи` ➔ **«Незащищенная фигура»**.",
            "back_rank": "🧱 **Мат по 8-й:** `Задачи` ➔ `Настраиваемые задачи` ➔ **«Слабость последней горизонтали»**.",
            "fork": "🐴 **Вилки:** `Задачи` ➔ `Настраиваемые задачи` ➔ **«Двойной удар / Вилка»**.",
            "pin": "🧲 **Связки:** `Задачи` ➔ `Настраиваемые задачи` ➔ **«Связка (Pin)»**.",
            "endgame": "♔ **Эндшпиль:** `Обучение` ➔ `Тренировка (Drills)` ➔ **Пешечные окончания**."
        },
        "en": {
            "undefended": "⚡ **Hanging pieces:** `Puzzles` ➔ `Custom Puzzles` ➔ **«Hanging Piece»**.",
            "back_rank": "🧱 **Back Rank:** `Puzzles` ➔ `Custom Puzzles` ➔ **«Back-Rank Mate»**.",
            "fork": "🐴 **Forks:** `Puzzles` ➔ `Custom Puzzles` ➔ **«Fork / Double Attack»**.",
            "pin": "🧲 **Pins:** `Puzzles` ➔ `Custom Puzzles` ➔ **«Pin»**.",
            "endgame": "♔ **Endgame:** `Learn` ➔ `Drills` ➔ **Pawn Endgames**."
        },
        "pt": {
            "undefended": "⚡ **Peças penduradas:** `Exercícios` ➔ `Personalizados` ➔ **«Peça Pendurada»**.",
            "back_rank": "🧱 **Mate na 8ª:** `Exercícios` ➔ `Personalizados` ➔ **«Mate na Última Fileira»**.",
            "fork": "🐴 **Garfos:** `Exercícios` ➔ `Personalizados` ➔ **«Garfo / Duplo»**.",
            "pin": "🧲 **Cravagens:** `Exercícios` ➔ `Personalizados` ➔ **«Cravagem»**.",
            "endgame": "♔ **Final:** `Aprender` ➔ `Treino (Drills)` ➔ **Finais de Peões**."
        }
    }
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def extract_opening_name(pgn_obj, game_raw, platform) -> str:
    if pgn_obj:
        opening_tag = pgn_obj.headers.get("Opening", "")
        if opening_tag and opening_tag != "?":
            clean_name = opening_tag.split(":")[0].split(",")[0].strip()
            if "unknown" not in clean_name.lower():
                return clean_name

    if platform == "chesscom":
        eco_url = game_raw.get("eco", "")
        if eco_url:
            parts = eco_url.split("/")
            if parts:
                name = parts[-1].replace("-", " ").title()
                if "unknown" not in name.lower():
                    return name
    elif platform == "lichess":
        opening_json = game_raw.get("opening", {}).get("name", "")
        if opening_json:
            clean_name = opening_json.split(":")[0].split(",")[0].strip()
            if "unknown" not in clean_name.lower():
                return clean_name

    if pgn_obj:
        board = pgn_obj.board()
        moves_san = []
        for move in list(pgn_obj.mainline_moves())[:6]:
            moves_san.append(board.san(move))
            board.push(move)
        moves_str = " ".join(moves_san)
        for pattern, name in OPENING_PATTERNS.items():
            if moves_str.startswith(pattern):
                return name

    return None

def analyze_board_concepts(board: chess.Board) -> list:
    detected = []
    undefended = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type != chess.KING:
            if board.is_attacked_by(not p.color, sq) and not board.is_attacked_by(p.color, sq):
                undefended += 1
    if undefended >= 1:
        detected.append("undefended")

    for color, sqs in [(chess.WHITE, [chess.F1, chess.G1, chess.H1]), (chess.BLACK, [chess.F8, chess.G8, chess.H8])]:
        if board.king(color) in [chess.G1, chess.H1, chess.G8, chess.H8]:
            if sum(1 for sq in sqs if board.piece_at(sq) == chess.Piece(chess.PAWN, color)) == 3:
                detected.append("back_rank")
                break

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
        detected.append("fork")

    detected.append("pin")
    return detected

async def fetch_recent_games_async(username: str, platform: str, limit: int = 15) -> list:
    headers = {'User-Agent': 'ChessCoachBot/1.0'}
    games = []
    timeout = aiohttp.ClientTimeout(total=8)
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
                url = f"https://lichess.org/api/games/user/{username}?max={limit}&pgnInBody=true&opening=true"
                headers_lic = {'Accept': 'application/x-ndjson'}
                async with session.get(url, headers=headers_lic) as res:
                    if res.status == 200:
                        text = await res.text()
                        for line in text.strip().split('\n'):
                            if line:
                                games.append(json.loads(line))
    except Exception as e:
        print(f"Ошибка загрузки партий: {e}")
    return games

def search_youtube_videos(query_topic: str, lang: str = "ru", max_results: int = 1) -> list:
    if not YOUTUBE_API_KEY:
        return []
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=query_topic, part="snippet", maxResults=max_results, type="video", relevanceLanguage=lang
        )
        response = request.execute()
        
        if not response.get("items"):
            request = youtube.search().list(
                q=f"{query_topic} chess lesson", part="snippet", maxResults=max_results, type="video"
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

# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_setting(user_id, "lang", "ru")
    t = LANG_DATA.get(lang, LANG_DATA["ru"])
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
    t = LANG_DATA.get(new_lang, LANG_DATA["ru"])
    await callback.message.edit_text(t["welcome"], reply_markup=get_settings_keyboard(user_id))
    await callback.answer()

@dp.message()
async def analyze_player(message: types.Message):
    user_id = message.from_user.id
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    t = LANG_DATA.get(lang, LANG_DATA["ru"])
    
    username = message.text.strip()
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    
    await message.answer(t["analyzing"].format(username=username, platform=platform_name))
    
    games = await fetch_recent_games_async(username, platform, limit=15)
    
    if not games:
        await message.answer(t["not_found"].format(username=username, platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    detected_keys = []
    current_openings = defaultdict(lambda: {"total": 0, "wins": 0})

    for game in games:
        pgn_text = game.get("pgn", "")
        pgn = chess.pgn.read_game(io.StringIO(pgn_text)) if pgn_text else None
        
        opening_name = extract_opening_name(pgn, game, platform)
        
        if opening_name:
            is_win = False
            if platform == "chesscom":
                white_user = game.get("white", {}).get("username", "").lower()
                white_result = game.get("white", {}).get("result", "")
                black_result = game.get("black", {}).get("result", "")
                is_win = (white_result == "win") if username.lower() == white_user else (black_result == "win")
            else: # Lichess
                winner = game.get("winner", "")
                players = game.get("players", {})
                white_user = players.get("white", {}).get("user", {}).get("name", "").lower()
                is_win = (winner == "white") if username.lower() == white_user else (winner == "black")

            current_openings[opening_name]["total"] += 1
            if is_win:
                current_openings[opening_name]["wins"] += 1

        if pgn:
            moves = list(pgn.mainline_moves())
            if len(moves) > 10:
                board = pgn.board()
                for m in moves[:len(moves)//2]:
                    board.push(m)
                concepts = analyze_board_concepts(board)
                for key in concepts:
                    if key not in detected_keys:
                        detected_keys.append(key)

    detected_keys = detected_keys[:2]
    if not detected_keys:
        detected_keys = ["undefended", "pin"]

    # --- РАСЧЕТ ДИНАМИКИ И ИСТОРИИ (ОБРАБОТКА ПРОГРЕССА) ---
    past_progress = get_saved_progress(user_id)
    progress_text = ""

    if past_progress:
        progress_text += t["progress_header"]
        for op_name, curr_data in current_openings.items():
            curr_wr = int((curr_data["wins"] / curr_data["total"]) * 100) if curr_data["total"] > 0 else 0
            if op_name in past_progress:
                past_data = past_progress[op_name]
                past_wr = int((past_data["wins"] / past_data["total"]) * 100) if past_data["total"] > 0 else 0
                diff = curr_wr - past_wr
                
                if diff > 0:
                    progress_text += f"📈 **{op_name}:** Винрейт вырос с {past_wr}% до **{curr_wr}%** (+{diff}%)! Отличная работа!\n"
                elif diff < 0:
                    progress_text += f"📉 **{op_name}:** Винрейт просел с {past_wr}% до **{curr_wr}%** ({diff}%). Стоит повторить теорию!\n"
                else:
                    progress_text += f"➡️ **{op_name}:** Винрейт стабилен на уровне **{curr_wr}%**.\n"
            else:
                progress_text += f"🆕 **{op_name}:** Новый дебют в твоем репертуаре (Винрейт: **{curr_wr}%**).\n"
        progress_text += "\n"
    else:
        progress_text = t["first_time"]

    # Сохраняем новые данные в базу для следующей проверки
    save_progress(user_id, username, platform, current_openings)

    # --- ТАКТИЧЕСКИЕ ВИДЕО ---
    tactics_videos = []
    topics_dict = t.get("topics", LANG_DATA["ru"]["topics"])
    for key in detected_keys:
        topic_info = topics_dict.get(key, topics_dict.get("undefended"))
        yt_query = topic_info.get("yt", "chess tactics")
        vids = search_youtube_videos(yt_query, lang=lang, max_results=1)
        tactics_videos.extend(vids)

    # --- СБОРКА ТЕКСТА ОТЧЕТА ---
    text = t["header"].format(username=username, platform=platform_name, count=len(games))
    text += progress_text

    target_opening_for_video = None
    if current_openings:
        text += t["opening_header"]
        sorted_openings = sorted(
            current_openings.items(), 
            key=lambda item: (item[1]["wins"] / item[1]["total"]) if item[1]["total"] > 0 else 0, 
            reverse=True
        )
        
        best = sorted_openings[0]
        best_winrate = int((best[1]["wins"] / best[1]["total"]) * 100) if best[1]["total"] > 0 else 0
        
        if len(sorted_openings) > 1:
            worst = sorted_openings[-1]
            worst_winrate = int((worst[1]["wins"] / worst[1]["total"]) * 100) if worst[1]["total"] > 0 else 0
            text += t["best_opening"].format(opening=best[0], winrate=best_winrate)
            text += t["worst_opening"].format(opening=worst[0], winrate=worst_winrate)
            target_opening_for_video = worst[0]
        else:
            text += t["single_opening"].format(opening=best[0], winrate=best_winrate)
            target_opening_for_video = best[0]

    if target_opening_for_video:
        opening_query = f"{target_opening_for_video} chess" if lang == "en" else f"{target_opening_for_video} шахматы"
        opening_vids = search_youtube_videos(opening_query, lang=lang, max_results=2)
        if opening_vids:
            text += t["opening_videos_header"].format(opening=target_opening_for_video)
            for idx, vid in enumerate(opening_vids, 1):
                text += f"{idx}. [{vid['title']}]({vid['url']})\n"

    text += "\n"
    for key in detected_keys:
        info = topics_dict.get(key, topics_dict.get("undefended"))
        text += f"{info['topic']}\n\n"

    text += t["plan_header"]
    if tactics_videos:
        for idx, vid in enumerate(tactics_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += t["no_videos"]

    text += t["trainers_header"].format(platform=platform_name)
    plat_trainers = TRAINER_DATABASE.get(platform, {}).get(lang, TRAINER_DATABASE["chesscom"]["ru"])
    for key in detected_keys:
        if key in plat_trainers:
            text += f"• {plat_trainers[key]}\n"
    if "endgame" in plat_trainers:
        text += f"• {plat_trainers['endgame']}\n"

    text += t["weekly_task"]
    main_key = detected_keys[0]
    task_desc = topics_dict.get(main_key, topics_dict.get("undefended"))["task"]
    text += f"👉 {task_desc}\n"

    quotes_list = CHESS_QUOTES.get(lang, CHESS_QUOTES["ru"])
    text += t["quote_header"]
    text += f"{random.choice(quotes_list)}\n"

    await message.answer(
        text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True, 
        reply_markup=get_settings_keyboard(user_id)
    )

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def main():
    init_db() # Инициализируем БД при старте
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    print("🚀 БОТ С ПЕРСОНАЛЬНОЙ ПАМЯТЬЮ УСПЕШНО ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
