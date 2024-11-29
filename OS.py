import random
import requests
from itertools import combinations
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import BadRequest

# Ваши API ключи
TELEGRAM_API_KEY = " "
KINOPOISK_API_KEY = " "

# Словарь жанров
GENRES = {
    "😂Комедия": 13,
    "👻Ужасы": 17,
    "🐭Мультфильм": 18,
    "🚀Фантастика": 6,
    "😢Драма": 2,
    "💥Боевик": 3,
    "🗺️Приключения": 5,
    "👨‍👩‍👧‍👦Семейный": 19,
}

# Хранилище жанров пользователей
user_genres = {}
# Хранилище для отслеживания показанных фильмов
shown_movies = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_genres[user_id] = []
    shown_movies[user_id] = set()

    keyboard = [
        [InlineKeyboardButton("🎭 Выбрать жанры всей семьёй", callback_data="choose_genres")],
        [InlineKeyboardButton("🎲 Рандомный фильм", callback_data="random_movie")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Добро пожаловать! Что вы хотите сделать?"

    # Упрощение обработки: проверяем, откуда пришёл вызов
    if update.callback_query:
        query = update.callback_query
        await query.answer()  # Обязательно подтверждаем callback
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except BadRequest:
            # Если сообщение нельзя редактировать, отправляем новое
            await query.message.reply_text(text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def choose_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    buttons = [
        [InlineKeyboardButton(f"{genre} {'✅' if GENRES[genre] in user_genres.get(query.from_user.id, []) else ''}",
                              callback_data=f"add_genre_{GENRES[genre]}")]
        for genre in GENRES
    ]
    buttons.append([InlineKeyboardButton("Закончить выбор", callback_data="finish_selection")])
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        await query.message.edit_text(
            "Выберите жанры, которые вас интересуют:",
            reply_markup=reply_markup
        )
    except BadRequest:
        await query.message.reply_text(
            "Выберите жанры, которые вас интересуют:",
            reply_markup=reply_markup
        )


async def add_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    genre_id = int(query.data.split("_")[-1])
    if user_id not in user_genres:
        user_genres[user_id] = []

    if genre_id in user_genres[user_id]:
        user_genres[user_id].remove(genre_id)
    else:
        user_genres[user_id].append(genre_id)

    selected_genres = [genre for genre, gid in GENRES.items() if gid in user_genres[user_id]]
    selected_genres_text = ", ".join(selected_genres) if selected_genres else "Жанры не выбраны"

    await query.answer(f"Текущие жанры: {selected_genres_text}")
    await choose_genres(update, context)


def call_kinopoisk_api(genre_ids, page=1):
    """Вызов API Кинопоиска."""
    url = "https://kinopoiskapiunofficial.tech/api/v2.2/films"
    headers = {"X-API-KEY": KINOPOISK_API_KEY}
    params = {
        "genres": ','.join(map(str, genre_ids)) if genre_ids else '',
        "order": "RATING",
        "type": "ALL",
        "ratingFrom": 7,
        "ratingTo": 10,
        "page": page
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        return data.get('items', [])
    else:
        print(f"Ошибка при вызове API: {response.status_code}")
        return []


def get_movie_details(movie_id):
    """Получение детальной информации о фильме."""
    url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films/{movie_id}"
    headers = {"X-API-KEY": KINOPOISK_API_KEY}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    return None


def search_movies(genres):
    all_movies = []

    # Пробуем найти фильмы с текущей комбинацией жанров
    movies = call_kinopoisk_api(genres)
    if movies:
        all_movies.extend(movies)

    # Если фильмов не найдено, пробуем уменьшать количество жанров
    if not all_movies and len(genres) > 1:
        for r in range(len(genres) - 1, 0, -1):
            for genre_combo in combinations(genres, r):
                movies = call_kinopoisk_api(list(genre_combo))
                if movies:
                    all_movies.extend(movies)
                    break
            if all_movies:
                break

    return all_movies


async def show_movie(update: Update, context: ContextTypes.DEFAULT_TYPE, movies, user_id, is_random):
    if not movies:
        try:
            await update.callback_query.message.reply_text(
                "😔 К сожалению, не удалось найти подходящие фильмы. Попробуйте другие жанры или рандомный поиск.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в начало", callback_data="start")
                ]])
            )
        except:
            await update.message.reply_text(
                "😔 К сожалению, не удалось найти подходящие фильмы. Попробуйте другие жанры или рандомный поиск.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в начало", callback_data="start")
                ]])
            )
        return

    if user_id not in shown_movies:
        shown_movies[user_id] = set()

    unseen_movies = [m for m in movies if m.get('kinopoiskId') not in shown_movies[user_id]]
    if not unseen_movies:
        shown_movies[user_id].clear()
        unseen_movies = movies

    movie = random.choice(unseen_movies)
    movie_id = movie.get('kinopoiskId')
    shown_movies[user_id].add(movie_id)

    # Получаем детальную информацию о фильме
    movie_details = get_movie_details(movie_id)

    if movie_details:
        rating = movie_details.get('ratingKinopoisk', 'Не указан')
        duration = movie_details.get('filmLength', 'Не указано')
        description = movie_details.get('description', 'Описание отсутствует') or 'Описание отсутствует'
    else:
        rating = movie.get('rating', 'Не указан')
        duration = movie.get('filmLength', 'Не указано')
        description = 'Описание отсутствует'

    # Ограничение длины строки
    if len(description) > 800:
        description = description[:800] + "..."

    genre_ids = movie.get('genres', [])
    movie_genres = ", ".join([g.get('genre', 'Не указан') for g in genre_ids])
    year = movie.get('year', 'Не указан')

    keyboard = [
        [InlineKeyboardButton("🎲 Другой фильм",
                              callback_data="next_random_movie" if is_random else "next_selected_movie")],
        [InlineKeyboardButton("🏠 Вернуться в начало", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        f"🎬 *Название*: {movie.get('nameRu', 'Не указано')}\n"
        f"📅 *Год*: {year}\n"
        f"⭐ *Рейтинг КиноПоиск*: {rating}\n"
        f"⏱ *Длительность*: {duration} мин\n"
        f"🎭 *Жанры*: {movie_genres}\n\n"
        f"📝 *Описание*: {description}\n\n"
        f"🔗 [Ссылка на фильм](https://www.kinopoisk.ru/film/{movie_id})"
    )

    try:
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=movie.get('posterUrlPreview', ''),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_photo(
                photo=movie.get('posterUrlPreview', ''),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Error sending movie info: {e}")
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"Критическая ошибка: {e}")


async def next_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()  # Обязательно отвечаем на callback-запрос

    try:
        if query.data == "next_random_movie":
            movies = call_kinopoisk_api([])
            await show_movie(update, context, movies, user_id, is_random=True)
        else:  # next_selected_movie
            selected_genres = user_genres.get(user_id, [])
            movies = search_movies(selected_genres)
            await show_movie(update, context, movies, user_id, is_random=False)
    except Exception as e:
        print(f"Ошибка в next_movie: {e}")
        # Если не удалось отредактировать сообщение, просто показываем новый фильм
        if query.data == "next_random_movie":
            movies = call_kinopoisk_api([])
            await show_movie(update, context, movies, user_id, is_random=True)
        else:
            selected_genres = user_genres.get(user_id, [])
            movies = search_movies(selected_genres)
            await show_movie(update, context, movies, user_id, is_random=False)


async def finish_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in user_genres or not user_genres[user_id]:
        await query.answer("Вы ещё не выбрали ни одного жанра!", show_alert=True)
        return

    selected_genres = user_genres[user_id]
    movies = search_movies(selected_genres)

    if not movies:
        await query.edit_message_text(
            "😔 Не удалось найти фильмы по выбранным жанрам. Попробуйте выбрать другие жанры.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Выбрать другие жанры", callback_data="choose_genres"),
                InlineKeyboardButton("🏠 Вернуться в начало", callback_data="start")
            ]])
        )
        return

    await show_movie(update, context, movies, user_id, is_random=False)


async def random_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    movies = call_kinopoisk_api([])  # Пустой список жанров для случайного выбора
    await show_movie(update, context, movies, user_id, is_random=True)


# Создание приложения и обработчиков
application = Application.builder().token(TELEGRAM_API_KEY).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(choose_genres, pattern="^choose_genres$"))
application.add_handler(CallbackQueryHandler(add_genre, pattern="^add_genre_"))
application.add_handler(CallbackQueryHandler(finish_selection, pattern="^finish_selection$"))
application.add_handler(CallbackQueryHandler(random_movie, pattern="^random_movie$"))
application.add_handler(CallbackQueryHandler(next_movie, pattern="^next_random_movie$"))
application.add_handler(CallbackQueryHandler(next_movie, pattern="^next_selected_movie$"))
application.add_handler(CallbackQueryHandler(start, pattern="^start$"))

if __name__ == "__main__":
    application.run_polling()

