import os

import telebot
from db import DB
from dotenv import load_dotenv
from emoji import emojize

load_dotenv()

bot = telebot.TeleBot(os.environ['TG_TOKEN'])
db = DB(os.environ['MONGO'], os.environ['ES'], False)

keyboard1 = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
keyboard1.row('Разработчик', 'Пользователь')

categories = ["книги", "фильмы", "соцсети", "мессенджеры", "видеоредакторы", "фоторедакторы", "навигация", "IT",
              "браузеры", "облачные хранилища", "музыка", "учёба", "магазины", "спорт", "продуктивность", "новости",
              "медицина", "финансы", "знакомства", "транспорт"]

cat_keyboard = telebot.types.InlineKeyboardMarkup()
for i, txt in enumerate(categories):
    cat_keyboard.add(telebot.types.InlineKeyboardButton(text=txt, callback_data=txt.lower()))

sel_keyboard = telebot.types.InlineKeyboardMarkup()

user_states = {}
IDLE = 0
WAIT_FOR_QUERY = 1

polls = {}


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет! Выбери: ты разработчик или пользователь.', reply_markup=keyboard1)


@bot.message_handler(content_types=['text'])
def send_text(message):
    uid = message.from_user.id
    return_keyboard = telebot.types.ReplyKeyboardMarkup()
    return_keyboard.row('Назад')

    bot.send_message(message.chat.id, 'Отлично', reply_markup=return_keyboard)
    if message.text == 'Разработчик':
        keyboard3 = telebot.types.InlineKeyboardMarkup()
        keyboard3.add(telebot.types.InlineKeyboardButton(text='Мои приложения', callback_data='dev1'))
        keyboard3.add(telebot.types.InlineKeyboardButton(text='Добавить приложение', callback_data='dev2'))
        bot.send_message(uid, 'Ты в режиме разработчика\nВыбери, что тебя интересует', reply_markup=keyboard3)
    elif message.text in ['Пользователь', 'Назад']:
        user_states[uid] = IDLE
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton(text='Поиск', callback_data='do_search'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='Выбор категории', callback_data='do_category'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='Оставить отзыв', callback_data='do_review'))
        # keyboard.add(telebot.types.InlineKeyboardButton(text='Рекомендации', callback_data='do_recommend'))
        bot.send_message(uid, text='Что будем делать?', reply_markup=keyboard)
    elif user_states.get(uid, IDLE) == WAIT_FOR_QUERY:
        user_states[uid] = message.text
        process_search(uid, message.text)


def send_rating(uid, data, limit=10):
    if len(data) == 0:
        bot.send_message(uid, "К сожалению, мне не удалось найти такие приложения")
    for i, data in enumerate(data[:limit]):
        kb = telebot.types.InlineKeyboardMarkup(
            [[telebot.types.InlineKeyboardButton(text='Открыть', url=data["link"])]])
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
def callback_worker(msg):
    if msg.data == 'do_category':
        bot.send_message(msg.from_user.id, 'Лови подборку!', reply_markup=cat_keyboard)
    elif msg.data == 'do_search':
        bot.send_message(msg.from_user.id, 'Кратко напиши, что ты ищешь')
        user_states[msg.from_user.id] = WAIT_FOR_QUERY


@bot.callback_query_handler(func=lambda x: x.data in categories)
def callback_worker(msg):
    bot.send_message(msg.from_user.id, "Вот что я могу предложить в рамках этой категории:")
    res = db.category_search(msg.data)
    send_rating(msg.from_user.id, res)


bot.polling()
