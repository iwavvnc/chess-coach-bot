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

# Настройки пользователей: {user_id: {"platform": "chesscom"|"lichess", "lang": "ru"|"en"|"pt"}}
user_settings = {}

LANG_NEXT = {"ru": "en", "en": "pt", "pt": "ru"}
LANG_FLAGS = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pt": "🇵🇹 Português"}

# --- СЛОВАРЬ ЛОКАЛИЗАЦИИ И ПРЯМЫХ ССЫЛОК НА СТАТЬИ ---
TEXTS = {
    "ru": {
        "welcome": "👋 Привет! Я твой персональный шахматный тренер.\n\nНастрой платформу и язык, а затем отправь свой **никнейм**:",
        "analyzing": "🔍 Провожу глубокий анализ профиля `{username}` на {platform}...",
        "not_found": "❌ Игрок не найден на {platform}. Проверь написание никнейма!",
        "no_games": "📊 Игрок **{username}** найден на {platform}, но у него нет сыгранных партий.",
        "header": "📊 **ГЛУБОКИЙ АНАЛИЗ ПРОФИЛЯ:** `{username}` ({platform})\n🎖️ Уровень: **{level}** (Макс. ELO: **{rating}**)\n\n",
        "ratings": "📌 **Оценки контролей времени:**\n",
        "rapid": "• Рапид: **{rating} ELO**\n",
        "blitz": "• Блиц: **{rating} ELO**\n",
        "bullet": "• Пуля: **{rating} ELO**\n\n",
        "weak_header": "🔍 **Выявленные слабые места в игре:**\n",
        "plan_header": "\n🎬 **Персональный учебный план (Видео):**\n",
        "articles_header": "\n📚 **Рекомендованные статьи и гайды:**\n",
        "no_videos": "*(Не удалось подгрузить видео из YouTube API)*",
        "levels": {
            "beginner": "Начинающий уровень",
            "intermediate": "Любительский уровень",
            "advanced": "Продвинутый уровень"
        },
        "weak_points": {
            "beginner": [
                "⚠️ **Тактика и зевы:** Регулярная потеря незащищенных фигур и пропуск простых матов в 1-2 хода.",
                "⚠️ **Дебют:** Отсутствие контроля центра, слишком частые ходы одной и той же фигурой в начале.",
                "⚠️ **Тайм-менеджмент:** Паника при нехватке времени, спешка в простых позициях."
            ],
            "intermediate": [
                "⚠️ **Дебютная подготовка:** Слабое знание типовых планов и пешечных структур после 5-7 ходов.",
                "⚠️ **Миттельшпиль:** Трудности с построением долгосрочного плана игры и атаки на короля.",
                "⚠️ **Эндшпиль:** Недостаток техники в реализации материального перевеса (пешечные и ладейные окончания)."
            ],
            "advanced": [
                "⚠️ **Глубокий расчет:** Нехватка точности в форсированных вариантах на 3+ ходов вперед.",
                "⚠️ **Сложные эндшпили:** Погрешности в ладейных и фигурных окончаниях при равном материале.",
                "⚠️ **Профилактика:** Недостаточный учет контригры соперника."
            ]
        },
        "topics": {
            "beginner": ["базовые зевы фигуры", "основы дебюта контроль центра", "как перестать спешить в шахматах"],
            "intermediate": ["типовые планы в миттельшпиле", "основы пешечных окончаний", "шахматная стратегия средний уровень"],
            "advanced": ["глубокий расчет вариантов", "ладейные окончания продвинутый", "профилактическое мышление в шахматах"]
        },
        "articles": {
            "beginner": [
                {"title": "📖 Принципы шахматного дебюта (Chess.com)", "url": "https://www.chess.com/ru/terms/shakhmatnyi-debiut"},
                {"title": "📖 Базовые матовые паттерны (Lichess)", "url": "https://lichess.org/practice/checkmates/checkmate-patterns/A8A21Maa/3_6d8dmd"}
            ],
            "intermediate": [
                {"title": "📖 Миттельшпиль в шахматах (Chess.com)", "url": "https://www.chess.com/ru/terms/mittelshpil-v-shakhmatakh"},
                {"title": "📖 Практика эндшпиля: Пешечные окончания (Lichess)", "url": "https://lichess.org/practice/pawn-endgames/key-squares/L9ed4uI3/l529EawB"}
            ],
            "advanced": [
                {"title": "📖 Расчет вариантов и кандидаты ходов (Chess.com)", "url": "https://www.chess.com/ru/article/view/kandidaty-v-khody-v-shakhmatakh"},
                {"title": "📖 Курс по ладейным окончаниям (Lichess Study)", "url": "https://lichess.org/study/vQWfGzO7"}
            ]
        }
    },
    "en": {
        "welcome": "👋 Hi! I am your personal chess coach.\n\nConfigure your platform and language, then send your **username**:",
        "analyzing": "🔍 Performing deep profile analysis for `{username}` on {platform}...",
        "not_found": "❌ Player not found on {platform}. Check your username spelling!",
        "no_games": "📊 Player **{username}** found on {platform}, but has no played games.",
        "header": "📊 **DEEP PROFILE ANALYSIS:** `{username}` ({platform})\n🎖️ Level: **{level}** (Max ELO: **{rating}**)\n\n",
        "ratings": "📌 **Time Control Ratings:**\n",
        "rapid": "• Rapid: **{rating} ELO**\n",
        "blitz": "• Blitz: **{rating} ELO**\n",
        "bullet": "• Bullet: **{rating} ELO**\n\n",
        "weak_header": "🔍 **Identified Weaknesses:**\n",
        "plan_header": "\n🎬 **Personal Training Plan (Videos):**\n",
        "articles_header": "\n📚 **Recommended Articles & Guides:**\n",
        "no_videos": "*(Failed to load videos from YouTube API)*",
        "levels": {
            "beginner": "Beginner Level",
            "intermediate": "Intermediate Level",
            "advanced": "Advanced Level"
        },
        "weak_points": {
            "beginner": [
                "⚠️ **Tactics & Blunders:** Frequently hanging pieces and missing basic 1-2 move mates.",
                "⚠️ **Opening:** Lack of center control, moving the same piece multiple times early on.",
                "⚠️ **Time Management:** Panic under low time, rushing in simple positions."
            ],
            "intermediate": [
                "⚠️ **Opening Prep:** Weak knowledge of standard plans and pawn structures after 5-7 moves.",
                "⚠️ **Middlegame:** Difficulty constructing long-term attack plans.",
                "⚠️ **Endgame:** Lack of technique in converting material advantage (pawn and rook endgames)."
            ],
            "advanced": [
                "⚠️ **Calculation:** Inaccuracies in forced lines 3+ moves ahead.",
                "⚠️ **Complex Endgames:** Small errors in rook/piece endgames with equal material.",
                "⚠️ **Prophylaxis:** Insufficient awareness of opponent's counterplay."
            ]
        },
        "topics": {
            "beginner": ["avoid blunders chess beginner", "opening principles center control", "chess time management"],
            "intermediate": ["middlegame plans chess", "pawn endgame basics", "chess strategy intermediate"],
            "advanced": ["deep calculation chess", "rook endgame masterclass", "prophylaxis in chess"]
        },
        "articles": {
            "beginner": [
                {"title": "📖 Opening Principles in Chess (Chess.com)", "url": "https://www.chess.com/terms/chess-openings"},
                {"title": "📖 Basic Checkmate Patterns Practice (Lichess)", "url": "https://lichess.org/practice/checkmates/checkmate-patterns/A8A21Maa/3_6d8dmd"}
            ],
            "intermediate": [
                {"title": "📖 Middlegame Strategy Fundamentals (Chess.com)", "url": "https://www.chess.com/terms/chess-middlegame"},
                {"title": "📖 Pawn Endgames Practice (Lichess)", "url": "https://lichess.org/practice/pawn-endgames/key-squares/L9ed4uI3/l529EawB"}
            ],
            "advanced": [
                {"title": "📖 Candidate Moves & Calculation (Chess.com)", "url": "https://www.chess.com/article/view/candidate-moves-chess"},
                {"title": "📖 Comprehensive Rook Endgames Course (Lichess Study)", "url": "https://lichess.org/study/vQWfGzO7"}
            ]
        }
    },
    "pt": {
        "welcome": "👋 Olá! Sou o seu treinador pessoal de xadrez.\n\nConfigure a plataforma e o idioma e, em seguida, envie o seu **nome de utilizador**:",
        "analyzing": "🔍 A realizar análise detalhada do perfil `{username}` no {platform}...",
        "not_found": "❌ Jogador não encontrado no {platform}. Verifique o nome de utilizador!",
        "no_games": "📊 Jogador **{username}** encontrado no {platform}, mas sem partidas jogadas.",
        "header": "📊 **ANÁLISE DETALHADA DO PERFIL:** `{username}` ({platform})\n🎖️ Nível: **{level}** (ELO Máx: **{rating}**)\n\n",
        "ratings": "📌 **Classificações por Controlo de Tempo:**\n",
        "rapid": "• Semi-Rápidas: **{rating} ELO**\n",
        "blitz": "• Blitz: **{rating} ELO**\n",
        "bullet": "• Bullet: **{rating} ELO**\n\n",
        "weak_header": "🔍 **Pontos Fracos Identificados:**\n",
        "plan_header": "\n🎬 **Plano de Treino Personalizado (Vídeos):**\n",
        "articles_header": "\n📚 **Artigos e Guias Recomendados:**\n",
        "no_videos": "*(Não foi possível carregar vídeos do YouTube API)*",
        "levels": {
            "beginner": "Nível Iniciante",
            "intermediate": "Nível Intermédio",
            "advanced": "Nível Avançado"
        },
        "weak_points": {
            "beginner": [
                "⚠️ **Tática e Erros Crassos:** Perda frequente de peças desprotegidas e falta de visão de xeque-mate simples.",
                "⚠️ **Abertura:** Falta de controlo do centro e mover a mesma peça várias vezes no início.",
                "⚠️ **Gestão de Tempo:** Pânico com pouco tempo e precipitação em posições simples."
            ],
            "intermediate": [
                "⚠️ **Preparação de Abertura:** Pouco conhecimento de planos típicos e estruturas de peões após 5-7 lances.",
                "⚠️ **Meio-Jogo:** Dificuldades em construir um plano de ataque a longo prazo.",
                "⚠️ **Final:** Falta de técnica na conversão de vantagem material (finais de peões e torres)."
            ],
            "advanced": [
                "⚠️ **Cálculo Profundo:** Falta de precisão em variantes forçadas a 3+ lances de distância.",
                "⚠️ **Finais Complexos:** Pequenos erros em finais de torres e peças com material igual.",
                "⚠️ **Perfilaxia:** Atenção insuficiente ao contra-jogo do adversário."
            ]
        },
        "topics": {
            "beginner": ["armadilhas xadrez iniciante", "principios de abertura centro xadrez", "gestao de tempo xadrez"],
            "intermediate": ["planos meio jogo xadrez", "finais de peoes xadrez", "estrategia de xadrez"],
            "advanced": ["calculo profundo xadrez", "finais de torres xadrez", "perfilaxia no xadrez"]
        },
        "articles": {
            "beginner": [
                {"title": "📖 Princípios da Abertura no Xadrez (Chess.com)", "url": "https://www.chess.com/pt-BR/terms/abertura-de-xadrez"},
                {"title": "📖 Treino Prático de Padrões de Mate (Lichess)", "url": "https://lichess.org/practice/checkmates/checkmate-patterns/A8A21Maa/3_6d8dmd"}
            ],
            "intermediate": [
                {"title": "📖 Estratégia de Meio-Jogo (Chess.com)", "url": "https://www.chess.com/pt-BR/terms/meio-jogo-xadrez"},
                {"title": "📖 Prática de Finais de Peões (Lichess)", "url": "https://lichess.org/practice/pawn-endgames/key-squares/L9ed4uI3/l529EawB"}
            ],
            "advanced": [
                {"title": "📖 Cálculo de Variantes e Lances Candidatos (Chess.com)", "url": "https://www.chess.com/pt-BR/article/view/calculo-de-variantes"},
                {"title": "📖 Estudo Completo de Finais de Torres (Lichess)", "url": "https://lichess.org/study/vQWfGzO7"}
            ]
        }
    }
}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

def search_youtube_videos(query_topic: str, lang: str = "ru", max_results: int = 1) -> list:
    if not YOUTUBE_API_KEY:
        return []
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        prefix = "Xadrez" if lang == "pt" else ("Chess" if lang == "en" else "Шахматы")
        search_query = f"{prefix} {query_topic}"
        
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
    
    platform_name = "Chess.com" if platform == "chesscom" else "Lichess"
    await message.answer(t["analyzing"].format(username=username, platform=platform_name))
    
    stats = get_chesscom_stats(username) if platform == "chesscom" else get_lichess_stats(username)
        
    if not stats:
        await message.answer(t["not_found"].format(platform=platform_name), reply_markup=get_settings_keyboard(user_id))
        return

    rapid_rating = stats.get('rapid', 0)
    blitz_rating = stats.get('blitz', 0)
    bullet_rating = stats.get('bullet', 0)
    
    current_rating = max(rapid_rating, blitz_rating, bullet_rating)

    if current_rating == 0:
        await message.answer(t["no_games"].format(username=username, platform=platform_name))
        return

    rating_offset = 200 if platform == "lichess" else 0
    
    if current_rating < (1000 + rating_offset):
        level_key = "beginner"
    elif current_rating < (1600 + rating_offset):
        level_key = "intermediate"
    else:
        level_key = "advanced"

    level_name = t["levels"][level_key]
    weak_points = t["weak_points"][level_key]
    search_topics = t["topics"][level_key]
    article_list = t["articles"][level_key]

    # Ищем видео
    all_videos = []
    for topic in search_topics:
        found_vids = search_youtube_videos(topic, lang=lang, max_results=1)
        all_videos.extend(found_vids)

    # Формируем текст отчета
    text = t["header"].format(username=username, platform=platform_name, level=level_name, rating=current_rating)
    text += t["ratings"]
    
    if rapid_rating: text += t["rapid"].format(rating=rapid_rating)
    if blitz_rating: text += t["blitz"].format(rating=blitz_rating)
    if bullet_rating: text += t["bullet"].format(rating=bullet_rating)
    text += "\n"

    text += t["weak_header"]
    for wp in weak_points:
        text += f"{wp}\n"

    text += t["plan_header"]
    if all_videos:
        for idx, vid in enumerate(all_videos, 1):
            text += f"{idx}. [{vid['title']}]({vid['url']})\n"
    else:
        text += t["no_videos"]

    # Блок прямых проверенных ссылок на статьи и интерактивные гиды
    text += t["articles_header"]
    for idx, art in enumerate(article_list, 1):
        text += f"{idx}. [{art['title']}]({art['url']})\n"

    await message.answer(
        text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True, 
        reply_markup=get_settings_keyboard(user_id)
    )

# Фейковый веб-сервер для UptimeRobot / Render
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
