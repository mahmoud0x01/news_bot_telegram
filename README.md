# Telegram News Bot

A Telegram bot built with Python and `aiogram` that fetches news from various sources, allows users to set default news sources, and provides subscription-based news updates at customizable intervals.

## Features

- Fetch news on-demand with `/news <source>` (e.g., `/news bbc`).
- Set a default news source with `/setsource <source>`.
- Subscribe to periodic news updates with `/subscribe` and choose intervals (e.g., every 1 minute, 1 hour, or 1 day).
- Unsubscribe from news sources with `/unsubscribe <source>`.
- List available news sources with `/listsources`.
- View active subscriptions with `/listsubscriptions`.
- Persistent storage of user preferences and subscriptions using a database.
- Docker Compose support for easy deployment.

## Prerequisites

- Python 3.8+
- A Telegram Bot Token (obtained from [BotFather](https://t.me/BotFather))
- Docker (optional, if using Docker Compose)
- NEWSAPI KEYS (obtained from [NEWSAPI](https://newsapi.org/)_


## Setup

1. Clone the Repository

```bash
git clone https://github.com/yourusername/telegram-news-bot.git
cd telegram-news-bot
```

2. Configure the Bot

- in `config.py` setup your news sources accordingly`
```python
NEWS_SOURCES = {
    "bloomberg": "bloomberg",
    "kommersant": "kommersant",
    "reuters": "reuters",
    "bbc": "bbc-news"  # Adjusted to match NewsAPI source IDs
}
```

**The bot uses a database postgresql (via SQLAlchemy) to store users and subscriptions. By default, it initializes on startup:**

- Ensure your `modules/db.py` file is configured with a database URL (e.g., SQLite or PostgreSQL).

- Create a `.env` file in the project root if not existed :

  ```text
  TELEGRAM_TOKEN=your-telegram-bot-token-here
  NEWSAPI_KEY=NEWSAPIKEY
  ```
- Edit `docker-compose.yml` to include also **TELEGRAM_TOKEN , NEWSAPI_KEY , DB_USER , DB_PASSWORD,** :
```text
    environment:
      - TELEGRAM_TOKEN=your-telegram-bot-token-here
      - NEWSAPI_KEY=NEWSAPIKEY
      ........

```

3. Build and run:
  ```bash
  docker-compose up --build -d
  ```

## Usage

1. Start the bot by messaging /start on Telegram.
2. Use the commands listed in the help message:
   - /news bbc - Fetch latest BBC news.
   - /setsource bloomberg - Set Bloomberg as your default source.
   - /subscribe - Start the subscription setup process (select source and interval via inline buttons).
   - /unsubscribe bbc - Stop BBC news updates.
   - /listsources - See all available news sources.
   - /listsubscriptions - View your active subscriptions.


## screenshots 
can be found at [screenshots](/screenshots/)

# Database Schema

The Telegram News Bot uses a PostgreSQL database managed via SQLAlchemy to store user information and subscription preferences. Below is the schema for the database models defined in `modules/db.py`.

## Overview

The database consists of two tables:
- **`users`**: Stores Telegram user information.
- **`subscriptions`**: Tracks user subscriptions to news sources with delivery intervals.

The schema is lightweight, designed to support automatic user registration and flexible subscription management without storing news articles.

## Schema Details

### Table: `users`

**Purpose**: Stores unique Telegram users based on their chat ID.

| Column            | Type      | Constraints         | Description                          |
|-------------------|-----------|---------------------|--------------------------------------|
| `id`             | Integer   | Primary Key         | Unique identifier for each user.     |
| `telegram_chat_id` | String    | Unique, Not Null    | Telegram chat ID of the user.        |

- **Primary Key**: `id` (auto-incremented).
- **Unique Constraint**: `telegram_chat_id` ensures no duplicate users.

### Table: `subscriptions`

**Purpose**: Manages user subscriptions to news sources, including their preferred delivery intervals. Also used to store the default news source (with `interval_hours = 0`).

| Column          | Type      | Constraints         | Description                          |
|-----------------|-----------|---------------------|--------------------------------------|
| `id`           | Integer   | Primary Key         | Unique identifier for each subscription. |
| `user_id`      | Integer   | Foreign Key (users.id), Not Null | References the user who owns this subscription. |
| `source`       | String    | Not Null            | News source (e.g., "bbc", "reuters"). |
| `interval_hours` | Integer   | Not Null            | Delivery interval in minutes (despite the name, repurposed from hours). 0 indicates default source. |

- **Primary Key**: `id` (auto-incremented).
- **Foreign Key**: `user_id` links to `users(id)` with a cascading relationship.
- **Notes**:
  - `interval_hours` is named historically but represents minutes in the current implementation (e.g., 15 for 15 minutes, 1440 for 1 day).
  - A subscription with `interval_hours = 0` denotes the user’s default news source, not an active periodic subscription.

## Relationships

- **One-to-Many**: One `User` can have multiple `Subscription` entries (e.g., subscriptions to different sources or a default source).
  - `users.id` → `subscriptions.user_id`.


Extending the Bot

- Add new news sources in config.py and update news_fetcher.py to handle them.
- Modify modules/db.py to use a different database (e.g., PostgreSQL) by updating the SQLALCHEMY_DATABASE_URL.
