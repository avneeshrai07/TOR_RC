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

    # Extract title
    title_tag = soup.find("h1", class_=lambda x: x and "article-heading" in x if x else False)
    if not title_tag:
        title_tag = soup.find("h1")
    
    title = title_tag.get_text(strip=True) if title_tag else None

    # Extract content from <p> tags
    content_parts: List[str] = []
    
    # Find the article element by id
    article_elem = soup.find("article", id=lambda x: x and "article" in x.lower() if x else False)
    
    if article_elem:
        # Remove unwanted sections before processing
        unwanted_selectors = [
            {"class_": lambda x: x and "shorts-widget" in str(x) if x else False},
            {"class_": lambda x: x and "ad-slots" in str(x) if x else False},
            {"class_": lambda x: x and "also-read" in str(x) if x else False},
            {"class_": lambda x: x and "figcaption" in str(x) if x else False},
            {"class_": lambda x: x and "publisher-wrap" in str(x) if x else False},
            {"class_": lambda x: x and "article-leadimage" in str(x) if x else False},
        ]
        
        for selector in unwanted_selectors:
            for unwanted in article_elem.find_all("div", **selector):
                unwanted.decompose()
        
        # Also remove style tags
        for style in article_elem.find_all("style"):
            style.decompose()
        
        # Now extract all remaining <p> tags
        for p in article_elem.find_all("p"):
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


async def scrape_freepressjournal(url: str) -> Optional[Dict[str, Any]]:
    """Main method: try async HTTP first, then fallback to async Playwright."""
    result = await scrape_with_requests_async(url)
    if not result:
        result = await scrape_with_playwright_async(url)
    return result


# Example usage
# if __name__ == "__main__":
#     test_url = "https://www.freepressjournal.in/business/infosys-forges-long-term-collaboration-with-tk-elevator-for-digital-transformation"
#
#     async def _main():
#         result = await scrape_freepressjournal(test_url)
#         if result:
#             print("\n" + "=" * 80)
#             print(f"Method used: {result['method'].upper()}")
#             print("=" * 80)
#             print(f"\nTITLE:\n{result['title']}")
#             print(f"\nCONTENT (first 800 chars):\n{result['content'][:800]}...")
#         else:
#             print("\nFailed to scrape the article")
#
#     asyncio.run(_main())
