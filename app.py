import logging
from typing import List, Dict

from config import NEWS_SITES
from tor.session_manager import tor_session_manager
from news_scrapers.pr_news_wire import scrape_pr_newswire


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    setup_logging()
    logger = logging.getLogger("main")

    logger.info("Starting Tor-based news scraper")

    scraper = scrape_pr_newswire(
        base_urls=NEWS_SITES,
        request_func=tor_session_manager.request,
    )

    results: List[Dict] = scraper.run()

    logger.info("Scraped %d items total", len(results))

    # For demo, just print a few
    for item in results[:20]:
        print(f"[{item['source']}] {item['title']}")

    tor_session_manager.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
