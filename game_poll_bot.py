import datetime
import logging
import json
import pytz

from telegram import (
    Update
)

from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
)

GAMES_FILE = 'games.json'
TOKEN_FILE = 'bot_token.txt'
CHAT_ID_FILE = 'chat_id.txt'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


class GamePollBot:
    def __init__(self):
        games_file = open(GAMES_FILE)

        self.games = json.load(games_file)

        if len(self.games) < 2:
            raise Exception("Games count can't be smaller than 2")

        with open(TOKEN_FILE) as f:
            token = ''.join(f.readlines())

        with open(CHAT_ID_FILE) as f:
            self.chat_id = ''.join(f.readlines())

        self.updater = Updater(token)

        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(CommandHandler('help', self.help_cmd))
        dispatcher.add_handler(CommandHandler('start', self.help_cmd))
        dispatcher.add_handler(CommandHandler('poll', self.poll_cmd))
        dispatcher.add_handler(CommandHandler('add', self.add_cmd))
        dispatcher.add_handler(CommandHandler('del', self.del_cmd))
        dispatcher.add_handler(CommandHandler('list', self.list_cmd))
        dispatcher.add_handler(CommandHandler(
            'daily_job', self.daily_job_cmd))

    # Запуск бота
    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    # Помощь
    def help_cmd(self, update: Update, context: CallbackContext):
        update.message.reply_text(
            'Команды бота:\n'
            '/poll - создать голосование в группе\n'
            '/add <игра> - добавить игру\n'
            '/del <игра> - удалить игру\n'
            '/list - получить список игр\n'
            '/daily_job - создать ежедневную задачу на запуск голосования\n'
        )

    # Отправить боту запрос на создание опроса
    def send_poll(self, context: CallbackContext):
        context.bot.send_poll(
            chat_id=self.chat_id,
            question='Во что играем?',
            options=self.games,
            is_anonymous=False
        )

    # Создать задачу для бота на запуск голосования в определенные дни
    def daily_job_cmd(self, update: Update, context: CallbackContext):
        context.job_queue.run_daily(self.send_poll, datetime.time(hour=12, minute=00, tzinfo=pytz.timezone(
            'Europe/Moscow')), days=(0, 1, 2, 3, 4), context=self.chat_id)

        update.message.reply_text('Создана ежедневная задача на запуск голосования в группе')

    # Создать опрос
    def poll_cmd(self, update: Update, context: CallbackContext):
        self.send_poll(context)

    # Добавить игру
    def add_cmd(self, update: Update, context: CallbackContext):
        game = ' '.join(context.args)

        if not game:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Не указано название игры')
            return

        if game in self.games:
            ans_text = f'Игра {game} уже существует в списке игр'
        else:
            self.games.append(game)
            self.update_games_file()
            ans_text = f'В список игр добавлена игра {game}'

        ans_text += ('\nТекущий список игр: {}'.format(', '.join(self.games)))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Удалить игру
    def del_cmd(self, update: Update, context: CallbackContext):
        game = ' '.join(context.args)

        if not game:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Не указано название игры')
            return

        if len(self.games) == 2:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Число игр не может быть меньше 2')
            return

        if game not in self.games:
            ans_text = f'Игра {game} не найдена в списке игр'
        else:
            self.games.remove(game)
            self.update_games_file()
            ans_text = f'Игра {game} удалена из списка игр'

        ans_text += ('\nТекущий список игр: {}'.format(', '.join(self.games)))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Получить текущий список игр
    def list_cmd(self, update: Update, context: CallbackContext):
        ans_text = 'Текущий список игр: {}'.format(', '.join(self.games))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Обновить файл со списком игр
    def update_games_file(self):
        with open(GAMES_FILE, 'w') as f:
            json.dump(self.games, f)


if __name__ == '__main__':
    bot = GamePollBot()
    bot.run()
