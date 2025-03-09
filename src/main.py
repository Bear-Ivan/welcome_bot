import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import (
    CommandStart,
    IS_MEMBER,
    IS_NOT_MEMBER,
    ChatMemberUpdatedFilter,
)
from aiogram.types import Message, ChatMemberUpdated
from aiogram.exceptions import TelegramBadRequest

TOKEN = os.getenv("TOKEN")
dp = Dispatcher()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

waiting_users = {}
welcome_messages = {}
control_question = os.getenv("CONTROL_QUESTION")
correct_answer = os.getenv("CORRECT_ANSWER", "").lower()


async def check_answer(chat_id_user_id: str) -> None:
    global waiting_users
    await asyncio.sleep(int(os.getenv("EXPIRED_TIME")))
    if chat_id_user_id not in waiting_users:
        return  # Если пользователь уже ответил, выходим из функции

    # Если пользователь не ответил за минуту, удаляем его
    chat = waiting_users[chat_id_user_id]["chat"]
    messages = waiting_users[chat_id_user_id]["messages"]
    await chat.ban(waiting_users[chat_id_user_id]["user_id"])
    await chat.delete_message(messages)  # question from bot
    try:
        global welcome_messages
        if welcome_message := welcome_messages.get(chat_id_user_id):
            await chat.delete_message(welcome_message)  # joined the group
            del welcome_messages[chat_id_user_id]
    except TelegramBadRequest:
        pass
    del waiting_users[chat_id_user_id]  # Удаляем пользователя из списка ожидающих


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def welcome(message: ChatMemberUpdated):
    global waiting_users
    user = message.new_chat_member.user
    message_question = await message.answer(
        f"""Добро пожаловать, <b>{user.first_name}!</b>
{control_question}"""
    )
    waiting_users[f"{message.chat.id}_{user.id}"] = {
        "time": asyncio.get_event_loop().time(),
        "user_id": user.id,
        "chat": message.chat,
        "messages": message_question.message_id,
    }
    asyncio.create_task(check_answer(f"{message.chat.id}_{user.id}"))


@dp.message(F.text.regexp(r".*"))
async def receive_answer(message: Message) -> None:
    global waiting_users
    user_id = message.from_user.id
    chat_id = message.chat.id
    # Проверяем, есть ли пользователь в списке ожидающих
    if f"{chat_id}_{user_id}" in waiting_users:
        messages = waiting_users[f"{chat_id}_{user_id}"]["messages"]
        answer = message.text.strip().lower()
        if answer in correct_answer.split(","):
            await message.chat.delete_message(messages)  # question from bot
            await message.delete()  # answer to question
        else:
            await message.chat.ban(user_id)
            await message.chat.delete_message(messages)  # question from bot
            await message.delete()  # answer to question
            try:
                global welcome_messages
                if welcome_message := welcome_messages.get(f"{chat_id}_{user_id}"):
                    await message.chat.delete_message(
                        welcome_message
                    )  # joined the group
                    del welcome_messages[f"{chat_id}_{user_id}"]
            except TelegramBadRequest:
                pass
        del waiting_users[f"{chat_id}_{user_id}"]


@dp.message()
async def new_chat_member(message: Message) -> None:
    if message.text is None:
        global welcome_messages
        try:
            for user in message.new_chat_members:
                user_id = user.id
                message_id = message.message_id
                chat_id = message.chat.id
                welcome_messages[f"{chat_id}_{user_id}"] = message_id
        except Exception:
            pass


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
