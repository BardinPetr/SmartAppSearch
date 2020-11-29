import os

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import telebot
from db import DB
from dotenv import load_dotenv
from emoji import emojize
from random import choices, shuffle

load_dotenv()

bot = telebot.TeleBot(os.environ['TG_TOKEN'])
db = DB(os.environ['MONGO'], os.environ['ES'], False)

ud_kb = ReplyKeyboardMarkup(one_time_keyboard=True)
ud_kb.row('Разработчик', 'Пользователь')

categories = ["книги", "фильмы", "соцсети", "мессенджеры", "видеоредакторы", "фоторедакторы", "навигация", "IT",
              "браузеры", "облачные хранилища", "музыка", "учёба", "магазины", "спорт", "продуктивность", "новости",
              "медицина", "финансы", "знакомства", "транспорт"]

cat_kb = InlineKeyboardMarkup(row_width=3)
for i in range(0, len(categories), 3):
    cat_kb.row(*[InlineKeyboardButton(text=j, callback_data=j) for j in categories[i: i+3]])

user_states = {}
user_profiles = {}
IDLE = 0
WAIT_FOR_QUERY = 1
USER_MODE = 2
DEV_MODE = 3

polls = {}


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет! Выбери: ты разработчик или пользователь', reply_markup=ud_kb)


@bot.message_handler(content_types=['text'])
def send_text(message):
    uid = message.from_user.id
    return_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    return_keyboard.row('На главную')

    if message.text == 'Разработчик' or message.text == 'На главную' and user_profiles.get(uid, USER_MODE) == DEV_MODE:
        user_profiles[uid] = DEV_MODE
        bot.send_message(message.chat.id, 'Вы - разработчик', reply_markup=return_keyboard)
        dev_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(text='Мои приложения', callback_data='dev1'),
            InlineKeyboardButton(text='Добавить приложение', callback_data='dev2')
        ]])
        bot.send_message(uid, 'Выбери, что тебя интересует', reply_markup=dev_kb)
    elif message.text == 'Пользователь' or message.text == 'На главную' and user_profiles.get(uid, USER_MODE) == USER_MODE:
        user_profiles[uid] = USER_MODE
        user_states[uid] = IDLE
        bot.send_message(message.chat.id, 'Отлично', reply_markup=return_keyboard)
        user_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(text='Поиск', callback_data='do_search')],
            [InlineKeyboardButton(text='Выбор категории', callback_data='do_category')],
            [InlineKeyboardButton(text='Оставить отзыв', callback_data='do_review')]
        ])
        bot.send_message(uid, text='Что будем делать?', reply_markup=user_kb)
    elif user_states.get(uid, IDLE) == WAIT_FOR_QUERY:
        user_states[uid] = message.text
        process_search(uid, message.text)


def send_rating(uid, data, limit=10):
    if len(data) == 0:
        bot.send_message(uid, "К сожалению, мне не удалось найти такие приложения")
    for i, data in enumerate(data[:limit]):
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text='Открыть', url=data["link"]),
              InlineKeyboardButton(text='Отзывы', callback_data="review_" + data["extid"])]])
        bot.send_message(uid,
                         emojize(":keycap_{}: {}\n{}:thumbs_up:  {}:thumbs_down:\n\n{}"
                                 .format(i,
                                         data["title"],
                                         data["pos_feedbacks"],
                                         data["neg_feedbacks"],
                                         data["description"])),
                         reply_markup=kb)


def process_search(uid, txt):
    res = db.combine_tags(txt)
    if len(res) == 0:
        send_rating(uid, db.query_by_tags(txt, []))
    else:
        poll = bot.send_poll(uid, "Какие функции вам больше всего интересны", res, allows_multiple_answers=True)
        polls[poll.poll.id] = {
            "uid": uid,
            "mid": poll.message_id,
            "cid": poll.chat.id
        }


@bot.poll_handler(lambda x: not x.is_closed)
def process_search_end(poll_res):
    data = polls[poll_res.id]
    res = [j.text for j in poll_res.options if j.voter_count > 0]
    bot.stop_poll(data['cid'], data['mid'])

    send_rating(data['uid'], db.query_by_tags(user_states[data['uid']], res))
    user_states[data['uid']] = IDLE
    del polls[poll_res.id]


@bot.callback_query_handler(func=lambda x: x.data.startswith("do_"))
def callback_worker_do(msg):
    if msg.data == 'do_category':
        bot.send_message(msg.from_user.id, 'Лови подборку!', reply_markup=cat_kb)
    elif msg.data == 'do_search':
        bot.send_message(msg.from_user.id, 'Кратко напиши, что ты ищешь')
        user_states[msg.from_user.id] = WAIT_FOR_QUERY


@bot.callback_query_handler(func=lambda x: x.data.startswith("review_"))
def callback_worker_review(msg):
    res = db.get_by_id(msg.data.split("_")[1])
    bot.send_message(msg.from_user.id, emojize(":exclamation:  Отзывы на {}".format(res["title"]), use_aliases=True))
    fb = res["feedbacks"]
    shuffle(fb)
    for j in fb[:4]:
        bot.send_message(msg.from_user.id, emojize(":arrow_down:\n{}".format(j), use_aliases=True))


@bot.callback_query_handler(func=lambda x: x.data in categories)
def callback_worker_cat(msg):
    bot.send_message(msg.from_user.id, "Вот что я могу предложить в рамках этой категории:")
    res = db.category_search(msg.data)
    send_rating(msg.from_user.id, res)


bot.polling()
