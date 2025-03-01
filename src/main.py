import os
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.CRITICAL,
)
logger = logging.getLogger(__name__)


class ControlQuestionBot:
    def __init__(self, token: str):
        self.application = ApplicationBuilder().token(token).build()
        self.waiting_users = {}
        self.control_question = os.getenv("CONTROL_QUESTION")
        self.correct_answer = os.getenv("CORRECT_ANSWER", "").lower()
        # Регистрация обработчиков
        self.register_handlers()

    def register_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome)
        )
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_answer)
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Бот запущен!")

    async def welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        for member in update.message.new_chat_members:
            await update.message.reply_text(
                f"Добро пожаловать, {member.first_name}! {self.control_question}"
            )
            self.waiting_users[member.id] = {
                "time": asyncio.get_event_loop().time(),
                "context": context,
            }
            # Запускаем задачу для проверки ответа
            asyncio.create_task(self.check_answer(member.id))

    async def check_answer(self, user_id: int) -> None:
        await asyncio.sleep(int(os.getenv("EXPIRED_TIME")))
        if user_id not in self.waiting_users:
            return  # Если пользователь уже ответил, выходим из функции

        # Если пользователь не ответил за минуту, удаляем его
        context = self.waiting_users[user_id]["context"]
        await context.bot.ban_chat_member(chat_id=context._chat_id, user_id=user_id)
        del self.waiting_users[user_id]  # Удаляем пользователя из списка ожидающих
        logger.info(
            f"Пользователь {user_id} был удален из группы за отсутствие ответа."
        )

    async def receive_answer(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id
        answer = update.message.text.strip().lower()

        # Проверяем, есть ли пользователь в списке ожидающих
        if user_id in self.waiting_users:
            if answer in self.correct_answer.split(","):
                await update.message.reply_text("Добро пожаловать!")
            else:
                await context.bot.ban_chat_member(
                    chat_id=update.message.chat.id, user_id=user_id
                )
            del self.waiting_users[user_id]

    def run(self):
        self.application.run_polling()


if __name__ == "__main__":
    TOKEN = os.getenv("TOKEN")
    if TOKEN:
        bot = ControlQuestionBot(TOKEN)
        bot.run()
