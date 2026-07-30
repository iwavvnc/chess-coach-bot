import os
import asyncio
import aiohttp
import chess
import chess.pgn
import io
import json
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from googleapiclient.discovery import build

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище настроек пользователей
user_settings = {}

LANG_NEXT = {"ru": "en", "en": "pt", "pt": "ru"}
LANG_FLAGS = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pt": "🇵🇹 Português"}

# Цитаты
CHESS_QUOTES = {
    "ru": [
        "«Если видишь хороший ход — не спеши, поищи ход лучше.» — *Эмануил Ласкер*",
        "«Самое трудное в шахматах — выиграть выигранную позицию.» — *Эмануил Ласкер*",
        "«Шахматы — это трагедия одного хода.» — *Савелий Тартаковер*",
        "«Учитесь играть эндшпиль. Дебют лишь показывает, как надо начинать, а эндшпиль — чем заканчивать.» — *Хосе Рауль Капабланка*",
        "«Никто никогда не выигрывал партию, сдавшись.» — *Савелий Тартаковер*"
    ],
    "en": [
        "\"When you see a good move, look for a better one.\" — *Emanuel Lasker*",
        "\"The hardest game to win is a won game.\" — *Emanuel Lasker*",
        "\"Chess is a tragedy of one move.\" — *Savielly Tartakower*",
        "\"You may learn much more from a game you lose than from a game you win.\" — *José Raúl Capablanca*",
        "\"No one ever won a game by resigning.\" — *Savielly Tartakower*"
    ],
    "pt": [
        "\"Quando vir uma boa jogada, procure uma melhor.\" — *Emanuel Lasker*",
        "\"O jogo mais difícil de vencer é um jogo ganho.\" — *Emanuel Lasker*",
        "\"O xadrez é uma tragédia de uma jogada.\" — *Savielly Tartakower*",
        "\"Pode aprender muito mais com uma partida que perde do que com uma que vence.\" — *José Raúl Capablanca*"
    ]
}

# Мультиязычный интерфейс и разборы ошибок
LANG_DATA = {
    "ru": {
        "welcome": "👋 Привет! Я твой AI-тренер по шахматам.\n\nДавай настроим платформу и язык, а затем напиши мне свой **никнейм**, и я разберу твои последние партии!",
        "analyzing": "🧠 Так-так, посмотрим... Загружаю твои последние партии `{username}` с {platform}. Дай мне пару секунд, раскладу всё по полочкам!",
        "not_found": "❌ Слушай, я не смог найти игрока `{username}` на {platform}. Проверь, нет ли опечатки!",
        "header": "📋 **РАЗБОР ТВОИХ ПАРТИЙ ОТ AI-ТРЕНЕРА ({count} игр)**\nИгрок: `{username}` ({platform})\n\nСлушай, я внимательно изучил твои последние игры. Вот что я заметил:\n\n",
        "plan_header": "\n🎬 **Видео для разбора (обязательно глянь на досуге):**\n",
        "trainers_header": "\n🧩 **Задание в приложении ({platform}):**\n",
        "weekly_task": "\n📝 **ТВОЁ ТРЕНЕРСКОЕ ЗАДАНИЕ НА ЭТУ НЕДЕЛЮ:**\n",
        "quote_header": "\n💡 **Мудрость недели:**\n",
        "no_videos": "*(Видео не подгрузились, но рекомендации ниже всё равно в силе!)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Зевки под прямой удар.** Ты периодически оставляешь фигуры без защиты или отдаешь их сопернику буквально в один ход.",
                "task": "Перед каждым ходом задавай себе один простой вопрос: *«А куда теперь напал мой соперник?»*. Сделай паузу в 3–5 секунд перед тем, как отпустить фигуру.",
                "yt": "как не делать зевки в шахматах"
            },
            "back_rank": {
                "topic": "🚨 **Опасность на последней горизонтали.** Твой король любит сидеть в рокировке за пешками без «форточки». Чужая ладья залетает на 8-ю горизонталь — и конец.",
                "task": "В миттельшпиле, как только позиции стабилизируются, сделай профилактический ход пешкой (`h3` или `g3`), чтобы дать королю воздуху.",
                "yt": "мат по последней горизонтали форточка шахматы"
            },
            "fork": {
                "topic": "🐴 **Коневые вилки.** Конь соперника ходит коварно, и ты регулярно пропускаешь двойные удары на короля и ценные фигуры.",
                "task": "Помни: конь меняет цвет поля при каждом ходе! Если твои ценные фигуры стоят на полях одного цвета — конь может поставить им вилку.",
                "yt": "коневая вилка двойной удар шахматы"
            },
            "pin": {
                "topic": "🧲 **Пропуск связок.** Ты забываешь про фигуры, которые прикрывают короля или ферзя, и делаешь ими ход, из-за чего летит материал.",
                "task": "Никогда не ходи связанной фигурой! Проверяй линии слонов и ладей противника перед тем, как сделать ход.",
                "yt": "тактический прием связка рентген в шахматах"
            }
        }
    },
    "en": {
        "welcome": "👋 Hi! I am your AI chess coach.\n\nSet up your platform and language, then send me your **username** and let's review your recent games!",
        "analyzing": "🧠 Let's see... Fetching recent games for `{username}` from {platform}. Give me a few seconds to analyze!",
        "not_found": "❌ Couldn't find player `{username}` on {platform}. Double check the spelling!",
        "header": "📋 **AI COACH GAME REVIEW ({count} games)**\nPlayer: `{username}` ({platform})\n\nHere is what I noticed in your recent games:\n\n",
        "plan_header": "\n🎬 **Recommended Lessons:**\n",
        "trainers_header": "\n🧩 **Practice in ({platform}):**\n",
        "weekly_task": "\n📝 **YOUR COACHING TASK FOR THIS WEEK:**\n",
        "quote_header": "\n💡 **Quote of the Week:**\n",
        "no_videos": "*(Failed to load videos, but practice tasks remain active!)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Hanging Pieces.** You occasionally leave pieces undefended or give them away in a single move. Don't rush!",
                "task": "Before every move, ask yourself one simple question: *'Where is my opponent attacking right now?'*. Pause for 3–5 seconds before moving.",
                "yt": "how to stop hanging pieces chess"
            },
            "back_rank": {
                "topic": "🚨 **Back-Rank Vulnerability.** Your king gets trapped behind its own pawns. An opponent's rook lands on the 8th rank — game over.",
                "task": "In the middlegame, make a prophylactic pawn move (`h3` or `g3` / `h6` or `g6`) to give your king some breathing room.",
                "yt": "back rank mate weakness chess"
            },
            "fork": {
                "topic": "🐴 **Knight Forks.** Opposing knights are sneaky, and you frequently miss double attacks on your king and heavy pieces.",
                "task": "Remember: a knight changes square color with every move! Keep your valuable pieces on different colored squares.",
                "yt": "tactics knight fork chess lesson"
            },
            "pin": {
                "topic": "🧲 **Missing Pins.** You tend to move pinned pieces that are shielding your king or queen, losing material as a result.",
                "task": "Never move a pinned piece! Always check the lines of enemy bishops and rooks before executing your move.",
                "yt": "pin tactics chess guide"
            }
        }
    },
    "pt": {
        "welcome": "👋 Olá! Sou o teu treinador de xadrez com IA.\n\nConfigura a plataforma e o idioma, e depois envia o teu **nome de utilizador**!",
        "analyzing": "🧠 Deixa ver... A descarregar partidas de `{username}` no {platform}. Dá-me uns segundos!",
        "not_found": "❌ Não encontrei o jogador `{username}` no {platform}. Confirma o nome!",
        "header": "📋 **ANÁLISE DO TREINADOR IA ({count} partidas)**\nJogador: `{username}` ({platform})\n\nEis o que notei nas tuas partidas recentes:\n\n",
        "plan_header": "\n🎬 **Aulas Recomendadas:**\n",
        "trainers_header": "\n🧩 **Exercícios em ({platform}):**\n",
        "weekly_task": "\n📝 **A TUA TAREFA DA SEMANA:**\n",
        "quote_header": "\n💡 **Citação da Semana:**\n",
        "no_videos": "*(Vídeos indisponíveis)*",
        "topics": {
            "undefended": {
                "topic": "👀 **Peças Penduradas.** Às vezes deixas peças sem defesa ou dás de bandeja num só lance.",
                "task": "Antes de cada lance, faz uma pergunta simples: *'Para onde está a atacar o meu adversário?'*. Faz uma pausa de 3 a 5 segundos.",
                "yt": "como nao pendurar pecas xadrez"
            },
            "back_rank": {
                "topic": "🚨 **Mate na Última Fileira.** O teu rei fica preso atrás dos próprios peões. Uma torre inimiga entra na 8ª fileira e é o fim.",
                "task": "No meio-jogo, faz um lance preventivo de peão (`h3` ou `g3`) para dar ar ao teu rei.",
                "yt": "mate da ultima fileira xadrez"
            },
            "fork": {
                "topic": "🐴 **Garfos de Cavalo.** O cavalo inimigo é traiçoeiro e estás a perder duplos ataques no rei e em peças valiosas.",
                "task": "Lembra-te: o cavalo muda a cor da casa a cada lance! Mantém as tuas peças valiosas em casas de cores diferentes.",
                "yt": "garfo de cavalo ataque duplo xadrez"
            },
            "pin": {
                "topic": "🧲 **Esquecimento de Cravagens.** Estás a mover peças cravadas que protegem o teu rei ou rainha.",
                "task": "Nunca movas uma peça cravada! Verifica as linhas de bispos e torres inimigas antes de jogar.",
                "yt": "tactica cravagem xadrez"
            }
        }
    }
}

TRAINER_DATABASE = {
    "lichess": {
        "ru": {
            "undefended": "⚡ **Зевки:** Зайди в `Обучение` ➔ `Практика` ➔ модуль **«Hanging pieces»**.",
            "back_rank": "🧱 **Мат по 8-й:** Открой `Задачи` ➔ `Темы задач` ➔ **«Мат на последней горизонтали»**.",
            "fork": "🐴 **Вилки:** Открой `Обучение` ➔ `Практика` ➔ модуль **«Knight Fork»**.",
            "pin": "🧲 **Связки:** Зайди в `Обучение` ➔ `Практика` ➔ модуль **«The Pin»**.",
            "endgame": "♔ **Эндшпиль:** Открой `Обучение` ➔ `Практика` ➔ **«Пешечные окончания»**."
        },
        "en": {
            "undefended": "⚡ **Hanging pieces:** Go to `Learn` ➔ `Practice` ➔ **«Hanging pieces»** module.",
            "back_rank": "🧱 **Back Rank:** Go to `Puzzles` ➔ `Puzzle Themes` ➔ **«Back Rank Mate»**.",
            "fork": "🐴 **Forks:** Go to `Learn` ➔ `Practice` ➔ **«Knight Fork»**.",
            "pin": "🧲 **Pins:** Go to `Learn` ➔ `Practice` ➔ **«The Pin»**.",
            "endgame": "♔ **Endgame:** Go to `Learn` ➔ `Practice` ➔ **«Pawn Endgames»**."
        },
        "pt": {
            "undefended": "⚡ **Peças penduradas:** Vai a `Aprender` ➔ `Prática` ➔ **«Hanging pieces»**.",
            "back_rank": "🧱 **Mate na 8ª:** Vai a `Exercícios` ➔ `Temas` ➔ **«Mate na última fileira»**.",
            "fork": "🐴 **Garfos:** Vai a `Aprender` ➔ `Prática` ➔ **«Knight Fork»**.",
            "pin": "🧲 **Cravagens:** Vai a `Aprender` ➔ `Prática` ➔ **«The Pin»**.",
            "endgame": "♔ **Final:** Vai a `Aprender` ➔ `Prática` ➔ **«Finais de Peões»**."
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

def get_user_setting(user_id: int, key: str, default: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    return user_settings[user_id].get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

def analyze_board_concepts(board: chess.Board) -> list:
    detected = []

    # 1. Зависающие фигуры
    undefended = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type != chess.KING:
            if board.is_attacked_by(not p.color, sq) and not board.is_attacked_by(p.color, sq):
                undefended += 1
    if undefended >= 1:
        detected.append("undefended")

    # 2. Безопасность короля
    for color, sqs in [(chess.WHITE, [chess.F1, chess.G1, chess.H1]), (chess.BLACK, [chess.F8, chess.G8, chess.H8])]:
        if board.king(color) in [chess.G1, chess.H1, chess.G8, chess.H8]:
            if sum(1 for sq in sqs if board.piece_at(sq) == chess.Piece(chess.PAWN, color)) == 3:
                detected.append("back_rank")
                break

    # 3. Коневые вилки
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

    # 4. Связка
    detected.append("pin")

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
        print(f"Ошибка загрузки партий: {e}")
        
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
    
    # Жестко считываем текущие настройки пользователя
    platform = get_user_setting(user_id, "platform", "chesscom")
    lang = get_user_setting(user_id, "lang", "ru")
    
    # Безопасное извлечение словаря для конкретного языка
    t = LANG_DATA.get(lang, LANG_DATA["ru"])
    
    username = message.text.strip()
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    
    await message.answer(t["analyzing"].format(username=username, platform=platform_name))
    
    games = await fetch_recent_games_async(username, platform, limit=10)
    
    if not games:
        await message.answer(t["not_found"].format(username=username, platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    detected_keys = []

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
                    for key in concepts:
                        if key not in detected_keys:
                            detected_keys.append(key)

    detected_keys = detected_keys[:2]

    if not detected_keys:
        detected_keys = ["undefended", "pin"]

    # Ролики YouTube строго под язык
    all_videos = []
    topics_dict = t.get("topics", LANG_DATA["ru"]["topics"])
    
    for key in detected_keys:
        topic_info = topics_dict.get(key, topics_dict.get("undefended"))
        yt_query = topic_info.get("yt", "chess tactics")
        vids = search_youtube_videos(yt_query, lang=lang, max_results=1)
        all_videos.extend(vids)

    # Формируем отчет строго на нужном языке
    text = t["header"].format(username=username, platform=platform_name, count=len(games))
    
    # 1. Пояснение проблем
    for key in detected_keys:
        info = topics_dict.get(key, topics_dict.get("undefended"))
        text += f"{info['topic']}\n\n"

    # 2. Видео-уроки
    text += t["plan_header"]
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += t["no_videos"]

    # 3. Инструкции по тренировкам
    text += t["trainers_header"].format(platform=platform_name)
    plat_trainers = TRAINER_DATABASE.get(platform, {}).get(lang, TRAINER_DATABASE["chesscom"]["ru"])
    for key in detected_keys:
        if key in plat_trainers:
            text += f"• {plat_trainers[key]}\n"
    if "endgame" in plat_trainers:
        text += f"• {plat_trainers['endgame']}\n"

    # 4. Задание на неделю
    text += t["weekly_task"]
    main_key = detected_keys[0]
    task_desc = topics_dict.get(main_key, topics_dict.get("undefended"))["task"]
    text += f"👉 {task_desc}\n"

    # 5. Цитата в конце
    quotes_list = CHESS_QUOTES.get(lang, CHESS_QUOTES["ru"])
    random_quote = random.choice(quotes_list)
    text += t["quote_header"]
    text += f"{random_quote}\n"

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
    
    print("🚀 БОТ УСПЕШНО ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
