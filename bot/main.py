import telebot
import os

bot = telebot.TeleBot(os.environ['TG_TOKEN'])


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message, "1")


bot.polling()
