import asyncio
import logging
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_schema.news_schema import NewsResult
from tor.session_manager import tor_session_manager
from configurations.select_news_scraper import scrapers
from contextlib import asynccontextmanager
TEST_URL = "https://www.prnewswire.com/news-releases/toyota-indiana-completes-1-3-billion-modernization-project-includes-550-new-jobs-300988459.html"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

@asynccontextmanager
async def lifespan(app: FastAPI):

    # start DB pool
    try:
        tor_session_manager.start_session()
        print("✅ TOR SESSION START")
    except Exception as e:
        print("❌ TOR SESSION START failed:", e)
        raise


    
    yield  # 🚀 app runs here

    try:
        tor_session_manager.close()
        print("✅ TOR SESSION CLOSED")
    except Exception as e:
        print("❌ TOR SESSION CLOSED failed:", e)
        raise


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


# @app.get("/news_scraper")
# async def news_scraper(request_body: NewsResult, request: Request):
async def news_scraper(all_news_results):
    print("STARTED....................")
    # all_news_results: List[dict] = request_body.all_news_results or []
    for single_news in all_news_results:
        # search_type = single_news.get("search_type")
        engine_name = single_news.get("engine_name")
        link = single_news.get("link")
        scraper_function = scrapers[engine_name]
        if not callable(scraper_function):
            print(f"⚠️ SKIP: No callable '{scraper_function}'")
            continue
        full_news = await scraper_function(link)
        single_news["full_title"] = full_news['title']
        single_news["full_news"] = full_news['content']
        print(single_news)
        # websockets se result le lunga
    return {"message": "API is working in fastapi server. V2.2.1"}


async def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Starting Tor-based news scraper")




    test = [
        {
            "search_type": "GOOGLE",
            "search_term": "factory modernization project",
            "engine_name": "PR_NEWSWIRE",
            "title": "Emerson's New Engineering Software Accelerates Plant ...",
            "link": "https://www.prnewswire.com/news-releases/emersons-new-engineering-software-accelerates-plant-modernization-using-artificial-intelligence-301910424.html",
            "description": "/PRNewswire/ -- Global technology and software leader Emerson (NYSE: EMR) is helping customers more quickly and efficiently transition legacy technology to...",
            "publish_date": "2023-08-29",
            "full_title": "",
            "full_news": ""  
        }
    ]

    await news_scraper(test)
    # tor_session_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
