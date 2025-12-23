import re
import logging
from typing import List, Dict, Iterable, Callable, Optional

import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


# -------------------------------
# PARSING LOGIC
# -------------------------------
def _clean_paragraph_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def extract_pr_newswire_content(soup: BeautifulSoup) -> str:
    selectors: List[str] = [
        "div#main-content p",
        "div.release-body p",
        "div.news-release-content p",
        "article p",
        "div.l-container p",
        ".article-content p",
        ".release-body-component p",
        ".col-sm-12 p",
        ".col-lg-10 p",
    ]

    paragraphs: List[str] = []
    seen: set[str] = set()

    for selector in selectors:
        for tag in soup.select(selector):
            for noise in tag.select("script, style, .ad, .social-share"):
                noise.decompose()

            text = _clean_paragraph_text(tag.get_text())
            if not text:
                continue

            if re.match(
                r"^(SOURCE|Contact|View original|View source)",
                text,
                re.IGNORECASE,
            ):
                continue

            if len(text) < 40:
                continue

            if text in seen:
                continue

            seen.add(text)
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


# -------------------------------
# PLAYWRIGHT FALLBACK
# -------------------------------
async def get_page_source_with_playwright(url: str, timeout_ms: int = 25000) -> str:
    """
    Pure HTTP Playwright, no Tor here.
    You can run Playwright behind Tor by setting proxy in `new_context`.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            context = await browser.new_context(user_agent=USER_AGENT)

            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{get: () => undefined})"
            )

            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            await page.wait_for_timeout(2000)

            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        logger.error("Playwright failed for %s: %s", url, e)
        return ""


# -------------------------------
# CLASS-BASED SCRAPER
# -------------------------------
class PRNewswireScraper:
    """
    Scrapes full PR Newswire article text using:
    - request_func (Tor / pool / normal requests)
    - Playwright fallback when static HTML is insufficient.

    request_func signature: (method: str, url: str, **kwargs) -> Response
    """

    def __init__(
        self,
        request_func: Callable[..., object],
        min_words_requests: int = 80,
    ):
        self.request_func = request_func
        self.min_words_requests = min_words_requests

    def fetch_html_with_requests(self, url: str, timeout: int = 15) -> str:
        """
        First try using injected request_func (Tor aware).
        """
        try:
            logger.info("PRNewswire (requests) fetching %s", url)
            resp = self.request_func(
                "GET",
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception as e:
            logger.warning("PRNewswire (requests) failed for %s: %s", url, e)
        return ""

    async def scrape_article(self, url: str) -> str:
        """
        End-to-end scrape for a single PR Newswire article URL.
        """
        # 1) Requests via request_func (Tor / pool)
        html_req = self.fetch_html_with_requests(url)
        content_req = ""

        if html_req:
            soup_req = BeautifulSoup(html_req, "html.parser")
            content_req = extract_pr_newswire_content(soup_req)

        if len(content_req.split()) >= self.min_words_requests:
            logger.info("PRNewswire: static HTML sufficient for %s", url)
            return content_req

        # 2) Playwright fallback if static not enough
        logger.info("PRNewswire: fallback to Playwright for %s", url)
        html_pw = await get_page_source_with_playwright(url)
        content_pw = ""

        if html_pw:
            soup_pw = BeautifulSoup(html_pw, "html.parser")
            content_pw = extract_pr_newswire_content(soup_pw)

        return (
            content_pw
            if len(content_pw.split()) > len(content_req.split())
            else content_req
        )


# Optional: quick manual test
if __name__ == "__main__":
    from tor.session_manager import tor_session_manager  # or your pool

    async def _test():
        test_url = (
            "https://www.prnewswire.com/news-releases/"
            "toyota-indiana-completes-1-3-billion-modernization-project-includes-550-new-jobs-300988459.html"
        )
        scraper = PRNewswireScraper(request_func=tor_session_manager.request)
        text = await scraper.scrape_article(test_url)
        print(text)

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_test())
