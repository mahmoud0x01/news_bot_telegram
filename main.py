import asyncio
from aiogram import executor
from modules.bot_handlers import dp
from modules.db import init_db

async def on_startup(_):
    init_db()
    print("Bot started!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)