from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TELEGRAM_TOKEN, NEWS_SOURCES
from modules.news_fetcher import fetch_news
from modules.db import get_session, User, Subscription
import urllib.parse
import asyncio

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Store active subscription tasks
subscription_tasks = {}

@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    chat_id = str(message.chat.id)
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
        if not user:
            user = User(telegram_chat_id=chat_id)
            session.add(user)
            session.commit()
            await message.reply("Welcome to the News Bot! You’ve been registered.\n\n" + get_help_message())
        else:
            await message.reply("Welcome back to the News Bot!\n\n" + get_help_message())
    finally:
        session.close()

def get_help_message():
    return (
        "Commands:\n"
        "/news <source> - Get news (e.g., /news bbc)\n"
        "/setsource <source> - Set default news source\n"
        "/subscribe - Start subscription setup\n"
        "/unsubscribe <source> - Cancel subscription\n"
        "/listsources - List available news sources\n"
        "/listsubscriptions - List your active subscriptions\n"
    )
@dp.message_handler(commands=["setsource"])
async def setsource_command(message: types.Message):
    chat_id = str(message.chat.id)
    source = message.get_args()
    if not source:
        await message.reply("Please specify a source (e.g., /setsource bbc)")
        return
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
        if source not in NEWS_SOURCES:
            await message.reply(f"Invalid source. Use /listsources to see available options.")
            return
        sub = session.query(Subscription).filter_by(user_id=user.id, interval_hours=0).first()
        if sub:
            sub.source = source
        else:
            session.add(Subscription(user_id=user.id, source=source, interval_hours=0))
        session.commit()
        await message.reply(f"Default source set to {source}")
    finally:
        session.close()

@dp.message_handler(commands=["subscribe"])
async def subscribe_command(message: types.Message):
    chat_id = str(message.chat.id)
    # Show available news sources as inline buttons
    keyboard = InlineKeyboardMarkup(row_width=2)
    for source in NEWS_SOURCES.keys():
        keyboard.add(InlineKeyboardButton(source, callback_data=f"sub_source_{source}"))
    await message.reply("Choose a news source to subscribe to:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("sub_source_"))
async def process_source_selection(callback_query: types.CallbackQuery):
    source = callback_query.data.split("_")[2]
    chat_id = str(callback_query.message.chat.id)
    
    # Show time interval options
    intervals = [
        ("1m", 1), ("15m", 15), ("1h", 60), ("3h", 180),
        ("6h", 360), ("12h", 720), ("1d", 1440)
    ]
    keyboard = InlineKeyboardMarkup(row_width=3)
    for label, minutes in intervals:
        keyboard.add(InlineKeyboardButton(label, callback_data=f"sub_interval_{source}_{minutes}"))
    
    await bot.edit_message_text(
        f"Selected source: {source}\nChoose an interval:",
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data.startswith("sub_interval_"))
async def process_interval_selection(callback_query: types.CallbackQuery):
    chat_id = str(callback_query.message.chat.id)
    data_parts = callback_query.data.split("_")
    source, interval_minutes = data_parts[2], int(data_parts[3])

    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
        sub = session.query(Subscription).filter_by(user_id=user.id, source=source).first()
        if sub and sub.interval_hours > 0:
            sub.interval_hours = interval_minutes
            action = "Updated"
        else:
            session.add(Subscription(user_id=user.id, source=source, interval_hours=interval_minutes))
            action = "Subscribed to"
        session.commit()

        # Cancel existing task if it exists
        task_key = (chat_id, source)
        if task_key in subscription_tasks:
            subscription_tasks[task_key].cancel()

        # Start new subscription task
        interval_seconds = interval_minutes * 60
        task = asyncio.create_task(send_news_periodically(chat_id, source, interval_seconds))
        subscription_tasks[task_key] = task

        interval_display = f"{interval_minutes // 60}h" if interval_minutes >= 60 else f"{interval_minutes}m"
        await bot.edit_message_text(
            f"{action} {source} every {interval_display}",
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )
    finally:
        session.close()
    await bot.answer_callback_query(callback_query.id)

@dp.message_handler(commands=["unsubscribe"])
async def unsubscribe_command(message: types.Message):
    chat_id = str(message.chat.id)
    source = message.get_args()
    if not source:
        await message.reply("Please specify a source (e.g., /unsubscribe bbc)")
        return
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
        sub = session.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.source == source,
            Subscription.interval_hours > 0
        ).first()
        if sub:
            session.delete(sub)
            session.commit()
            task_key = (chat_id, source)
            if task_key in subscription_tasks:
                subscription_tasks[task_key].cancel()
                del subscription_tasks[task_key]
            await message.reply(f"Unsubscribed from {source}")
        else:
            await message.reply(f"No subscription found for {source}")
    finally:
        session.close()

@dp.message_handler(commands=["news"])
async def news_command(message: types.Message):
    chat_id = str(message.chat.id)
    source = message.get_args()
    if not source:
        session = get_session()
        try:
            user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
            if user:
                default_sub = session.query(Subscription).filter_by(user_id=user.id, interval_hours=0).first()
                source = default_sub.source if default_sub else "bloomberg"
            else:
                source = "bloomberg"
        finally:
            session.close()

    headlines = await fetch_news(source)
    if not headlines:
        await message.reply("No news found!")
        return

    reserved_chars = "_*[]()~`#+-=|{}.!"
    def escape_md2(text):
        return "".join(f"\\{c}" if c in reserved_chars else c for c in text)

    formatted_news = []
    for item in headlines:
        title = escape_md2(item["title"])
        domain = escape_md2(urllib.parse.urlparse(item["link"]).netloc)
        formatted_news.append(f"*{title}* \\([{domain}]({item['link']})\\)")

    response = "\n".join(formatted_news)
    await message.reply(response, parse_mode=types.ParseMode.MARKDOWN_V2)

@dp.message_handler(commands=["listsources"])
async def listsources_command(message: types.Message):
    sources = NEWS_SOURCES.keys()
    response = "Available news sources:\n" + "\n".join(f"- {source}" for source in sources)
    await message.reply(response)

@dp.message_handler(commands=["listsubscriptions"])
async def listsubscriptions_command(message: types.Message):
    chat_id = str(message.chat.id)
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_chat_id=chat_id).first()
        subs = session.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.interval_hours > 0
        ).all()
        if not subs:
            await message.reply("You have no active subscriptions.")
            return
        response = "Your active subscriptions:\n"
        for sub in subs:
            interval_display = f"{sub.interval_hours // 60}h" if sub.interval_hours >= 60 else f"{sub.interval_hours}m"
            response += f"- {sub.source} every {interval_display}\n"
        await message.reply(response)
    finally:
        session.close()

async def send_news_periodically(chat_id, source, interval_seconds):
    while True:
        try:
            headlines = await fetch_news(source)
            if headlines:
                reserved_chars = "_*[]()~`#+-=|{}.!"
                def escape_md2(text):
                    return "".join(f"\\{c}" if c in reserved_chars else c for c in text)
                formatted_news = [f"*{escape_md2(h['title'])}* \\([{escape_md2(urllib.parse.urlparse(h['link']).netloc)}]({h['link']})\\)" for h in headlines]
                response = "\n".join(formatted_news)
                await bot.send_message(chat_id, response, parse_mode=types.ParseMode.MARKDOWN_V2)
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error sending news to {chat_id} for {source}: {e}")
            await asyncio.sleep(interval_seconds)

async def on_startup(_):
    print("Initializing database...")
    init_db()
    print("Loading subscriptions...")
    session = get_session()
    try:
        for sub in session.query(Subscription).filter(Subscription.interval_hours > 0).all():
            user = session.query(User).filter_by(id=sub.user_id).first()
            if user:
                chat_id = user.telegram_chat_id
                source = sub.source
                interval_minutes = sub.interval_hours
                task_key = (chat_id, source)
                task = asyncio.create_task(send_news_periodically(chat_id, source, interval_minutes * 60))
                subscription_tasks[task_key] = task
    finally:
        session.close()
    print("Bot started!")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)