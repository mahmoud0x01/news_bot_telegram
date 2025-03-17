import aiohttp
from config import NEWS_SOURCES, NEWSAPI_KEY

async def fetch_news(source_name):
    api_source = NEWS_SOURCES.get(source_name)
    if not api_source:
        print(f"No API source mapped for {source_name}")
        return []

    url = f"https://newsapi.org/v2/top-headlines?sources={api_source}&apiKey={NEWSAPI_KEY}"
    print(f"Fetching news from {source_name} via NewsAPI at {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"HTTP Status for {source_name}: {response.status}")
                if response.status != 200:
                    print(f"Failed to fetch {source_name}: HTTP {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return []
                data = await response.json()
                if data["status"] != "ok":
                    print(f"NewsAPI error for {source_name}: {data.get('message', 'Unknown error')}")
                    return []
                headlines = [
                    {"title": article["title"], "link": article["url"], "source": source_name}
                    for article in data.get("articles", [])[:5]
                ]
                print(f"Fetched {len(headlines)} headlines from {source_name}: {headlines}")
                return headlines
    except Exception as e:
        print(f"Error fetching news from {source_name}: {e}")
        return []