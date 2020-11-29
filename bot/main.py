import os
from random import shuffle

import telebot
from db import DB
from dotenv import load_dotenv
from emoji import emojize
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

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
    cat_kb.row(*[InlineKeyboardButton(text=j, callback_data=j) for j in categories[i: i + 3]])

revtype_kb = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="Большой отзыв", callback_data="review_long")],
    [InlineKeyboardButton(text="Рассказ о фичах", callback_data="review_short")],
    [InlineKeyboardButton(text="Откажусь", callback_data="review_ign")],
])

user_profiles = {}
USER_MODE = 2
DEV_MODE = 3

user_states = {}
IDLE = 0
WAIT_FOR_QUERY = 1
WAIT_FOR_REVIEW_A = 2
WAIT_FOR_REVIEW_B = 3
WAIT_FOR_REVIEW_C = 4

polls = {}
opened_rev = {}


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет! Выбери: ты разработчик или пользователь', reply_markup=ud_kb)


@bot.message_handler(content_types=['text'])
def send_text(message):
    uid = message.from_user.id
    return_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    return_keyboard.row('На главную')

    cur_state = user_states.get(uid, IDLE)

    if cur_state in [WAIT_FOR_REVIEW_B, WAIT_FOR_REVIEW_C]:
        user_states[uid] = IDLE
        bot.send_message(message.chat.id, 'Твой отзыв отправлен на проверку пользователям. Спасибо.')
        db.save_review(opened_rev[uid], message.text, cur_state == WAIT_FOR_REVIEW_C)
    elif message.text == 'Разработчик' or \
            message.text == 'На главную' and user_profiles.get(uid, USER_MODE) == DEV_MODE:
        user_profiles[uid] = DEV_MODE
        bot.send_message(message.chat.id, 'Вы - разработчик', reply_markup=return_keyboard)
        dev_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(text='Мои приложения', callback_data='dev1'),
            InlineKeyboardButton(text='Добавить приложение', callback_data='dev2')
        ]])
        bot.send_message(uid, 'Выбери, что тебя интересует', reply_markup=dev_kb)
    elif message.text == 'Пользователь' or \
            message.text == 'На главную' and user_profiles.get(uid, USER_MODE) == USER_MODE:
        user_profiles[uid] = USER_MODE
        user_states[uid] = IDLE
        bot.send_message(message.chat.id, 'Отлично', reply_markup=return_keyboard)
        user_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(text='Поиск', callback_data='do_search')],
            [InlineKeyboardButton(text='Выбор категории', callback_data='do_category')],
            [InlineKeyboardButton(text='Оставить отзыв', callback_data='do_review'),
             InlineKeyboardButton(text='Проверить отзыв', callback_data='do_check')],
        ])
        bot.send_message(uid, text='Что будем делать?', reply_markup=user_kb)
    elif cur_state == WAIT_FOR_QUERY:
        user_states[uid] = message.text
        process_search(uid, message.text)


def send_rating(uid, data, limit=10):
    if len(data) == 0:
        bot.send_message(uid, "К сожалению, мне не удалось найти такие приложения")
        return
    for i, data in enumerate(data[:limit]):
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text='Открыть', url=data["link"]),
              InlineKeyboardButton(text='Отзывы',
                                   callback_data="showreview_" + data.get("extid", str(data.get("_id"))))]])
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
    uid = msg.from_user.id
    if msg.data == 'do_category':
        bot.send_message(uid, 'Лови подборку!', reply_markup=cat_kb)
    elif msg.data == 'do_search':
        bot.send_message(uid, 'Кратко напиши, что ты ищешь')
        user_states[uid] = WAIT_FOR_QUERY
    elif msg.data == 'do_review':
        rev = db.get_pending_app()
        opened_rev[uid] = str(rev["_id"])
        bot.send_message(uid,
                         'Сегодня предлагаю написать отзыв на приложение '
                         '"{}" которое ты недавно скачал(-а)\nПродолжим?'
                         'Ты можешь написать полный отзыв, а можешь указать нам 3 ключевые особенности приложения'
                         ''.format(db.get_app_by_id(rev["_id"])['title']), reply_markup=revtype_kb)
        user_states[uid] = WAIT_FOR_REVIEW_A
    elif msg.data == 'do_check':
        rev = db.get_pending_review()
        if rev is None:
            bot.send_message(uid, "Пока нет отзывов, требующих проверки")
        else:
            yn_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(text=emojize(":white_check_mark:", use_aliases=True),
                                      callback_data="check_ok_" + str(rev["_id"]))],
                [InlineKeyboardButton(text=emojize(":x:", use_aliases=True),
                                      callback_data="check_fail_" + str(rev["_id"]))],
            ])
            bot.send_message(uid,
                             'Согласен ли ты с отзывом на приложение "{}"\n{}\n{}'
                             .format(db.get_app_by_id(rev["aid"])['title'].strip(),
                                     emojize(":interrobang:", use_aliases=True),
                                     rev["text"]),
                             reply_markup=yn_kb)


@bot.callback_query_handler(func=lambda x: x.data.startswith("check_"))
def callback_worker_check_answer(msg):
    bot.send_message(msg.from_user.id, "Спасибо, твой голос учтен")
    if 'ok' in msg.data:
        db.approve_review(msg.data.split("_")[2])


@bot.callback_query_handler(func=lambda x: x.data.startswith("showreview_"))
def callback_worker_show_review(msg):
    res = db.get_app_by_id(msg.data.split("_")[1])
    bot.send_message(msg.from_user.id, emojize(":exclamation:  Отзывы на {}".format(res["title"]), use_aliases=True))
    fb = res["feedbacks"]
    shuffle(fb)
    for j in fb[:4]:
        bot.send_message(msg.from_user.id, emojize(":arrow_down:\n{}".format(j), use_aliases=True))


@bot.callback_query_handler(func=lambda x: x.data.startswith("review_"))
def callback_worker_review(msg):
    uid = msg.from_user.id
    txt = msg.data

    if txt == 'review_ign':
        bot.send_message(uid, "Жаль.")
    elif txt == 'review_short':
        user_states[uid] = WAIT_FOR_REVIEW_B
        bot.send_message(uid, "Назови ключевую особенность приложения не более чем в 3 слова")
    else:
        user_states[uid] = WAIT_FOR_REVIEW_C
        bot.send_message(uid, "Расскажи о своем опыте как можно больше")


@bot.callback_query_handler(func=lambda x: x.data in categories)
def callback_worker_cat(msg):
    bot.send_message(msg.from_user.id, "Вот что я могу предложить в рамках этой категории:")
    res = db.category_search(msg.data)
    send_rating(msg.from_user.id, res)


bot.polling()
