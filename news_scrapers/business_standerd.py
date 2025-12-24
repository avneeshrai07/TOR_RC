import asyncio
from typing import Optional, Dict, Any, List

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from configurations.basic_configurations import USER_AGENT
from pyvirtualdisplay import Display

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_from_html(html: str) -> Optional[Dict[str, Any]]:
    """Shared HTML parsing (works for both requests + playwright content)."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title - try multiple strategies
    title_tag = soup.find("h1", class_=lambda x: x and "MainStory_stryhd" in str(x) if x else False)
    if not title_tag:
        title_tag = soup.find("h1", class_=lambda x: x and "stryhd" in str(x) if x else False)
    if not title_tag:
        title_tag = soup.find("h1")
    
    title = title_tag.get_text(strip=True) if title_tag else None
    
    print(f"DEBUG: Title found: {title}")

    # Extract content from <p> tags
    content_parts: List[str] = []
    
    # Try multiple selectors for the content container
    story_div = soup.find("div", class_=lambda x: x and "MainStory_storycontent" in str(x) if x else False)
    if not story_div:
        story_div = soup.find("div", class_=lambda x: x and "storycontent" in str(x) if x else False)
    
    print(f"DEBUG: Story div found: {story_div is not None}")
    
    if story_div:
        # Find the parent_top_div
        parent_div = story_div.find("div", id="parent_top_div")
        
        if not parent_div:
            parent_div = story_div
        
        print(f"DEBUG: Parent div found: {parent_div is not None}")
        
        if parent_div:
            # Remove unwanted elements
            for unwanted in parent_div.find_all("span", style=True):
                if "display:block" in unwanted.get("style", ""):
                    unwanted.decompose()
            
            for ad_div in parent_div.find_all("div", id=lambda x: x and "between_article_content" in x if x else False):
                ad_div.decompose()
            
            for spacing_div in parent_div.find_all("div", class_="mb-20"):
                spacing_div.decompose()
            
            for br in parent_div.find_all("br"):
                br.decompose()
            
            # Extract all <p> tags
            for p in parent_div.find_all("p"):
                text = p.get_text(strip=True)
                if text:
                    content_parts.append(text)

    content = "\n\n".join(content_parts) if content_parts else None
    
    print(f"DEBUG: Content paragraphs found: {len(content_parts)}")

    if title and content:
        return {"title": title, "content": content}
    return None


async def scrape_with_requests_async(url: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
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
    display = None
    try:
        print("Falling back to Playwright (async)...")
        
        # Start virtual display if on headless server
        import os
        if os.getenv('DISPLAY') is None:
            display = Display(visible=0, size=(1920, 1080))
            display.start()
            print("Started virtual display")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,  # Now this works!
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            html = await page.content()
            await browser.close()
            
        if display:
            display.stop()

        parsed = _extract_from_html(html)
        if parsed:
            print("✓ Successfully scraped with Playwright (async)")
            return {**parsed, "method": "playwright"}
        else:
            print("✗ Playwright method didn't extract complete data")
            return None

    except Exception as e:
        if display:
            display.stop()
        print(f"✗ Playwright method failed: {e}")
        return None


async def scrape_businessstandard(url: str) -> Optional[Dict[str, Any]]:
    """Main method: try async HTTP first, then fallback to async Playwright."""
    result = await scrape_with_requests_async(url)
    if not result:
        result = await scrape_with_playwright_async(url)
    return result
