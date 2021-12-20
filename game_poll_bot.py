import datetime
import logging
import json
import pytz
from typing import Tuple, Optional

from telegram import (
    Update,
    Chat,
    ChatMember,
    ChatMemberUpdated
)

from telegram.ext import (
    Updater,
    Filters,
    MessageHandler,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
)

CONFIG_FILE = 'config.json'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


# Определить статус добавления в чат
def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> Optional[Tuple[bool, bool]]:
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member",
                                                                       (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = (
        old_status
        in [
            ChatMember.MEMBER,
            ChatMember.CREATOR,
            ChatMember.ADMINISTRATOR,
        ]
        or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    )
    is_member = (
        new_status
        in [
            ChatMember.MEMBER,
            ChatMember.CREATOR,
            ChatMember.ADMINISTRATOR,
        ]
        or (new_status == ChatMember.RESTRICTED and new_is_member is True)
    )

    return was_member, is_member


class GamePollBot:
    def __init__(self):
        with open(CONFIG_FILE) as cfg_file:
            self.config = json.load(cfg_file)

        if len(self.config['poll_options']) < 2:
            raise Exception("Poll options count can't be smaller than 2")

        self.updater = Updater(self.config['token'])

        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, self.help_cmd))
        dispatcher.add_handler(CommandHandler('help', self.help_cmd))
        dispatcher.add_handler(CommandHandler('start', self.help_cmd))
        dispatcher.add_handler(CommandHandler(
            'poll', self.poll_cmd, pass_chat_data=True))
        dispatcher.add_handler(CommandHandler('add', self.add_cmd))
        dispatcher.add_handler(CommandHandler('del', self.del_cmd))
        dispatcher.add_handler(CommandHandler('list', self.list_cmd))
        dispatcher.add_handler(CommandHandler('daily', self.daily_cmd))
        dispatcher.add_handler(ChatMemberHandler(
            self.chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER))
        dispatcher.add_handler(MessageHandler(Filters.command, self.help_cmd))

    # Запуск бота
    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    # Помощь
    def help_cmd(self, update: Update, context: CallbackContext):
        update.message.reply_text(
            'Команды бота:\n'
            '/poll - создать голосование\n'
            '/add <вариант> - добавить вариант в опрос\n'
            '/del <вариант> - удалить вариант опроса\n'
            '/list - получить список вариантов опроса\n'
            '/daily - создать ежедневную задачу на запуск голосования\n'
        )

    def chat_member_handler(self, update: Update, context: CallbackContext):
        result = extract_status_change(update.my_chat_member)
        if result is None:
            return
        was_member, is_member = result

        cause_name = update.effective_user.full_name
        chat = update.effective_chat

        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if not was_member and is_member:
                logger.info("%s added the bot to the group %s",
                            cause_name, chat.title)
                if not chat.id in self.config['chats']:
                    self.config['chats'].append(chat.id)
                    self.update_config_file()
            elif was_member and not is_member:
                logger.info("%s removed the bot from the group %s",
                            cause_name, chat.title)
                if chat.id in self.config['chats']:
                    self.config['chats'].remove(chat.id)
                    self.update_config_file()

    # Отправить боту запрос на создание опроса
    def send_poll(self, context: CallbackContext):
        for chat in self.config['chats']:
            context.bot.send_poll(
                chat_id=chat,
                question='Во что играем?',
                options=self.config['poll_options'],
                is_anonymous=False
            )

    # Создать задачу для бота на запуск голосования в определенные дни
    def daily_cmd(self, update: Update, context: CallbackContext):
        for job in context.job_queue.get_jobs_by_name('daily'):
            job.schedule_removal()

        context.job_queue.run_daily(self.send_poll, datetime.time(hour=12, minute=30, tzinfo=pytz.timezone(
            'Europe/Moscow')), days=(0, 1, 2, 3, 4), name='daily')

        update.message.reply_text(
            'Создана ежедневная задача на запуск голосования')

    # Создать опрос
    def poll_cmd(self, update: Update, context: CallbackContext):
        self.send_poll(context)
        update.message.reply_text('Опросы созданы')

    # Добавить вариант опроса
    def add_cmd(self, update: Update, context: CallbackContext):
        option = ' '.join(context.args).strip()

        if not option:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Не указано название варианта опроса')
            return

        if option in self.config['poll_options']:
            ans_text = f'Вариант {option} уже существует'
        else:
            self.config['poll_options'].append(option)
            self.update_config_file()
            ans_text = f'В список вариантов опроса добавлен {option}'

        ans_text += ('\nТекущий список: {}'.format(
            ', '.join(self.config['poll_options'])))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Удалить вариант опроса
    def del_cmd(self, update: Update, context: CallbackContext):
        option = ' '.join(context.args).strip()

        if not option:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Не указано название варианта опроса')
            return

        if len(self.config['poll_options']) == 2:
            context.bot.send_message(
                chat_id=update.effective_chat.id, text='Число вариантов опроса не может быть меньше 2')
            return

        if option not in self.config['poll_options']:
            ans_text = f'Вариант {option} не найден в списке вариантов опроса'
        else:
            self.config['poll_options'].remove(option)
            self.update_config_file()
            ans_text = f'Вариант {option} удален из списка вариантов опроса'

        ans_text += ('\nТекущий список: {}'.format(
            ', '.join(self.config['poll_options'])))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Получить текущий список вариантов опроса
    def list_cmd(self, update: Update, context: CallbackContext):
        ans_text = 'Текущий список вариантов опроса: {}'.format(
            ', '.join(self.config['poll_options']))
        context.bot.send_message(
            chat_id=update.effective_chat.id, text=ans_text)

    # Обновить конфигурационный файл
    def update_config_file(self):
        with open(CONFIG_FILE, 'w') as cfg_file:
            json.dump(self.config, cfg_file, indent=4)


if __name__ == '__main__':
    bot = GamePollBot()
    bot.run()
