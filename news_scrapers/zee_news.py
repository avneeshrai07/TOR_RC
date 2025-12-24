import asyncio
from typing import Optional, Dict, Any, List

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from configurations.basic_configurations import USER_AGENT


HEADERS = {"User-Agent": USER_AGENT}


def _extract_from_html(html: str) -> Optional[Dict[str, Any]]:
    """Shared HTML parsing (works for both requests + playwright content)."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title from h1 tag
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Extract content from <p> tags inside the specific div
    content_parts: List[str] = []
    article_div = soup.find("div", {"class": "article_content article_description", "id": "fullArticle"})
    
    if article_div:
        for p in article_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                content_parts.append(text)

    content = "\n\n".join(content_parts) if content_parts else None

    if title and content:
        return {"title": title, "content": content}
    return None


async def scrape_with_requests_async(url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Try scraping with async HTTP first."""
    try:
        print("Attempting to scrape with async HTTP (httpx)...")
        async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        parsed = _extract_from_html(resp.text)
        if parsed:
            print("✓ Successfully scraped with async HTTP")
            return {**parsed, "method": "httpx"}
        else:
            print("✗ Async HTTP method didn't extract complete data")
            return None

    except Exception as e:
        print(f"✗ Async HTTP method failed: {e}")
        return None


async def scrape_with_playwright_async(url: str) -> Optional[Dict[str, Any]]:
    """Fallback to Playwright async for dynamic content."""
    try:
        print("Falling back to Playwright (async)...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)  # small buffer for dynamic content

            html = await page.content()
            await browser.close()

        parsed = _extract_from_html(html)
        if parsed:
            print("✓ Successfully scraped with Playwright (async)")
            return {**parsed, "method": "playwright"}
        else:
            print("✗ Playwright method didn't extract complete data")
            return None

    except Exception as e:
        print(f"✗ Playwright method failed: {e}")
        return None


async def scrape_zeenews(url: str) -> Optional[Dict[str, Any]]:
    """Main method: try async HTTP first, then fallback to async Playwright."""
    result = await scrape_with_requests_async(url)
    if not result:
        result = await scrape_with_playwright_async(url)
    return result


# Example usage
if __name__ == "__main__":
    test_url = "https://zeenews.india.com/aviation/delhi-airport-gets-modernized-t1-terminal-check-facilities-here-2437904.html"

    async def _main():
        result = await scrape_zeenews(test_url)
        if result:
            print("\n" + "=" * 80)
            print(f"Method used: {result['method'].upper()}")
            print("=" * 80)
            print(f"\nTITLE:\n{result['title']}")
            print(f"\nCONTENT (first 800 chars):\n{result['content']}")
        else:
            print("\nFailed to scrape the article")

    asyncio.run(_main())
