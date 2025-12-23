import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import requests
import asyncio

# -------------------------------
# FETCH: Simple Requests First
# -------------------------------
def get_page_source_with_requests(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass

    return ""


# -------------------------------
# FETCH: Playwright Fallback
# -------------------------------
async def get_page_source_with_playwright(url: str) -> str:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                )
            )

            # Stealth patch
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=25000)
            await page.wait_for_timeout(2000)

            html = await page.content()
            await browser.close()

            return html

    except Exception:
        return ""


# -------------------------------
# PARSING LOGIC
# -------------------------------
def extract_pr_newswire_content(soup: BeautifulSoup) -> str:
    # Try multiple layouts
    selectors = [
        "div#main-content p",
        "div.release-body p",
        "div.news-release-content p",     # main PR Newswire body
        "article p",
        "div.l-container p",
        ".article-content p",
        ".release-body-component p",
        ".col-sm-12 p",
        ".col-lg-10 p",
    ]

    paragraphs, seen = [], set()

    for selector in selectors:
        for tag in soup.select(selector):
            # remove noise
            for noise in tag.select("script, style, .ad, .social-share"):
                noise.decompose()

            text = tag.get_text(strip=True)
            text = re.sub(r"\s+", " ", text).strip()

            # Skip SOURCE or CONTACT info
            if re.match(r"^(SOURCE|Contact)", text, re.IGNORECASE):
                continue

            if text and len(text) > 40 and text not in seen:
                paragraphs.append(text)
                seen.add(text)

    return "\n\n".join(paragraphs)


# -------------------------------
# MAIN SCRAPER
# -------------------------------
async def scrape_pr_newswire(url: str) -> str:

    # 1️⃣ TRY SIMPLE REQUEST FIRST
    html_requests = get_page_source_with_requests(url)

    if html_requests:
        soup_req = BeautifulSoup(html_requests, "html.parser")
        content_req = extract_pr_newswire_content(soup_req)
    else:
        content_req = ""

    # If Requests gives enough content → return immediately
    if len(content_req.split()) > 80:
        return content_req

    # 2️⃣ PLAYWRIGHT FALLBACK
    html_pw = await get_page_source_with_playwright(url)

    if html_pw:
        soup_pw = BeautifulSoup(html_pw, "html.parser")
        content_pw = extract_pr_newswire_content(soup_pw)
    else:
        content_pw = ""

    # Return whichever is better
    return content_pw if len(content_pw.split()) > len(content_req.split()) else content_req


# Example standalone usage
if __name__ == "__main__":
    url = "https://www.prnewswire.com/news-releases/toyota-indiana-completes-1-3-billion-modernization-project-includes-550-new-jobs-300988459.html"
    content = asyncio.run(scrape_pr_newswire(url))
    print(content)
