import asyncio
import logging
from typing import List, Dict

from tor.session_manager import tor_session_manager
from news_scrapers.pr_news_wire import PRNewswireScraper

TEST_URL = "https://www.prnewswire.com/news-releases/toyota-indiana-completes-1-3-billion-modernization-project-includes-550-new-jobs-300988459.html"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Starting Tor-based news scraper")

    scraper = PRNewswireScraper(request_func=tor_session_manager.request)

    # ✅ Single-article test (async)
    text = await scraper.scrape_article(TEST_URL)
    print("\n--- ARTICLE TEXT  ---\n")
    print(text)

    # ✅ If run() is sync, call it normally
    results: List[Dict] = scraper.run()

    logger.info("Scraped %d items total", len(results))

    for item in results[:20]:
        print(f"[{item.get('source')}] {item.get('title')}")

    # ✅ close tor session manager
