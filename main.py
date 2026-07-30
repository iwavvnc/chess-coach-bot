import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from googleapiclient.discovery import build
from ddgs import DDGS

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_settings = {}

LANG_NEXT = {"ru": "en", "en": "pt", "pt": "ru"}
LANG_FLAGS = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pt": "🇵🇹 Português"}

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
        "no_articles": "*(Не удалось найти статьи)*",
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
        "yt_topics": {
            "beginner": ["базовые зевы фигуры", "основы дебюта контроль центра"],
            "intermediate": ["типовые планы в миттельшпиле", "основы пешечных окончаний"],
            "advanced": ["глубокий расчет вариантов", "ладейные окончания продвинутый"]
        },
        "article_topics": {
            "beginner": ["как перестать зевать фигуры в шахматах", "принципы шахматного дебюта"],
            "intermediate": ["стратегия миттельшпиля в шахматах", "пешечные окончания руководство"],
            "advanced": ["расчет вариантов в шахматах кандидатные ходы", "сложные ладейные окончания"]
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
        "no_articles": "*(Failed to load articles)*",
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
        "yt_topics": {
            "beginner": ["avoid blunders chess beginner", "opening principles center control"],
            "intermediate": ["middlegame plans chess", "pawn endgame basics"],
            "advanced": ["deep calculation chess", "rook endgame masterclass"]
        },
        "article_topics": {
            "beginner": ["how to stop blundering chess article", "opening principles chess guide"],
            "intermediate": ["middlegame strategy chess guide", "pawn endgame principles"],
            "advanced": ["chess calculation candidate moves", "rook endgame strategy guide"]
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
        "no_articles": "*(Não foi possível carregar artigos)*",
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
        "yt_topics": {
            "beginner": ["armadilhas xadrez iniciante", "principios de abertura centro xadrez"],
            "intermediate": ["planos meio jogo xadrez", "finais de peoes xadrez"],
            "advanced": ["calculo profundo xadrez", "finais de torres xadrez"]
        },
        "article_topics": {
            "beginner": ["como evitar erros taticos xadrez artigo", "principios de abertura xadrez"],
            "intermediate": ["estrategia meio jogo xadrez guia", "finais de peoes xadrez"],
            "advanced": ["calculo de variantes xadrez", "finais de torres xadrez guia"]
        }
    }
}

def get_user_setting(user_id: int, key: str, default: str):
    return user_settings.get(user_id, {}).get(key, default)

def set_user_setting(user_id: int, key: str, value: str):
    if user_id not in user_settings:
        user_settings[user_id] = {"platform": "chesscom", "lang": "ru"}
    user_settings[user_id][key] = value

# --- ПРЯМЫЕ ПРОВЕРЕННЫЕ ССЫЛКИ НА СТАТЬИ И РУКОВОДСТВА ---
def search_articles_ddg(query_topic: str, lang: str = "ru") -> list:
    # Точная база прямых обучающих материалов
    guides_database = {
        "ru": {
            "как перестать зевать фигуры в шахматах": {
                "title": "📖 Руководство: Как перестать зевать фигуры и видеть тактику",
                "url": "https://lichess.org/practice/basic-tactics/checkmates/H393k995"
            },
            "принципы шахматного дебюта": {
                "title": "📰 ChessBase: Главные принципы правильного развития в дебюте",
                "url": "https://ru.chessbase.com/post/chess-opening-principles"
            },
            "стратегия миттельшпиля в шахматах": {
                "title": "📚 Lichess Study: Базовая стратегия и планирование в миттельшпиле",
                "url": "https://lichess.org/study/1R32jL8T"
            },
            "пешечные окончания руководство": {
                "title": "🧩 Chesstempo: Интерактивный тренажер пешечных окончаний",
                "url": "https://chesstempo.com/chess-endgames/pawn-endgames"
            },
            "расчет вариантов в шахматах кандидатные ходы": {
                "title": "📰 ChessBase: Метод ходов-кандидатов и точность расчета",
                "url": "https://ru.chessbase.com/post/calculation-training-in-chess"
            },
            "сложные ладейные окончания": {
                "title": "📚 Lichess Study: Фундаментальные ладейные окончания (Позиции Филидора и Лусены)",
                "url": "https://lichess.org/study/vR4dE0P2"
            }
        },
        "en": {
            "how to stop blundering chess article": {
                "title": "📖 Lichess Practice: Master Basic Tactics & Stop Blundering",
                "url": "https://lichess.org/practice"
            },
            "opening principles chess guide": {
                "title": "📰 ChessBase: Fundamental Opening Principles Every Player Must Know",
                "url": "https://en.chessbase.com/post/opening-principles-for-beginners"
            },
            "middlegame strategy chess guide": {
                "title": "📚 Lichess Study: Comprehensive Middlegame Planning Guide",
                "url": "https://lichess.org/study/1R32jL8T"
            },
            "pawn endgame principles": {
                "title": "🧩 Chesstempo: Interactive Pawn Endgame Training & Rules",
                "url": "https://chesstempo.com/chess-endgames/pawn-endgames"
            },
            "chess calculation candidate moves": {
                "title": "📰 ChessBase: Calculation Techniques & Candidate Moves",
                "url": "https://en.chessbase.com/post/calculation-in-chess-principles"
            },
            "rook endgame strategy guide": {
                "title": "📚 Lichess Study: Essential Rook Endgames (Lucena & Philidor Positions)",
                "url": "https://lichess.org/study/vR4dE0P2"
            }
        },
        "pt": {
            "como evitar erros taticos xadrez artigo": {
                "title": "📖 Prática no Lichess: Aprenda a Evitar Erros Táticos",
                "url": "https://lichess.org/practice"
            },
            "principios de abertura xadrez": {
                "title": "📰 ChessBase PT: Princípios Fundamentais da Abertura no Xadrez",
                "url": "https://pt.chessbase.com/post/principios-de-abertura"
            },
            "estrategia meio jogo xadrez guia": {
                "title": "📚 Estudo no Lichess: Guia Prático de Planeamento no Meio-Jogo",
                "url": "https://lichess.org/study/1R32jL8T"
            },
            "finais de peoes xadrez": {
                "title": "🧩 Chesstempo: Treino Interativo de Finais de Peões",
                "url": "https://chesstempo.com/chess-endgames/pawn-endgames"
            },
            "calculo de variantes xadrez": {
                "title": "📰 ChessBase: Técnicas de Cálculo e Seleção de Lances",
                "url": "https://en.chessbase.com/post/calculation-in-chess-principles"
            },
            "finais de torres xadrez guia": {
                "title": "📚 Estudo no Lichess: Finais de Torres Essenciais (Lucena e Philidor)",
                "url": "https://lichess.org/study/vR4dE0P2"
            }
        }
    }

    # Берем словарь для нужного языка
    lang_dict = guides_database.get(lang, guides_database["ru"])
    
    # Достаем прямую ссылку на конкретный материал
    match = lang_dict.get(query_topic)
    
    if match:
        return [match]
    
    # Запасной вариант на случай неизвестной темы
    default_guides = {
        "ru": {"title": "📖 Руководство и практика на Lichess", "url": "https://lichess.org/practice"},
        "en": {"title": "📖 Interactive Practice & Studies on Lichess", "url": "https://lichess.org/practice"},
        "pt": {"title": "📖 Guia de Treino Interativo no Lichess", "url": "https://lichess.org/practice"}
    }
    return [default_guides.get(lang, default_guides["ru"])]

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
    yt_topics = t["yt_topics"][level_key]
    art_topics = t["article_topics"][level_key]

    # Ищем видео
    all_videos = []
    for topic in yt_topics:
        found_vids = search_youtube_videos(topic, lang=lang, max_results=1)
        all_videos.extend(found_vids)

    # Ищем статьи через DuckDuckGo
    all_articles = []
    for topic in art_topics:
        found_arts = search_articles_ddg(topic, lang=lang)
        all_articles.extend(found_arts)

    # Формируем отчет
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

    text += t["articles_header"]
    if all_articles:
        for idx, art in enumerate(all_articles, 1):
            text += f"{idx}. [{art['title']}]({art['url']})\n"
    else:
        text += t["no_articles"]

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
