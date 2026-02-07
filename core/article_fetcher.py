"""
Article Fetcher — Retrieves and extracts content from online article URLs.
Supports generic web articles with intelligent text extraction.
Includes strategies to bypass bot detection (headers, retries, JS rendering).
"""

from typing import Optional, Tuple
from urllib.parse import urlparse
import requests
from pathlib import Path
import time

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def extract_article_title_and_text(html: str, url: str = "") -> Tuple[str, str]:
    """
    Extract article title and text from HTML.
    
    Args:
        html: The HTML content of the page
        url: The URL (used as fallback for title)
    
    Returns:
        Tuple of (title, text_content)
    """
    if not BeautifulSoup:
        raise RuntimeError("BeautifulSoup4 not installed — run: pip install beautifulsoup4")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try to extract title
    title = ""
    
    # Try og:title meta tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title = og_title['content']
    
    # Try regular title tag
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.string.strip() if title_tag.string else ""
    
    # Try h1
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
    
    # Try data-title attribute (some sites use this)
    if not title:
        h_elem = soup.find(attrs={'data-title': True})
        if h_elem:
            title = h_elem.get('data-title', "").strip()
    
    # Fallback to domain from URL
    if not title and url:
        domain = urlparse(url).netloc
        title = domain or "Article"
    
    if not title:
        title = "Article"
    
    # Remove common suffix patterns from title
    title = title.replace(" | Medium", "").replace(" - DEV Community", "").strip()
    # Remove site name patterns
    title = title.split(" | ")[0].split(" - ")[0].strip()
    
    # Remove script and style elements
    for script in soup(["script", "style", "meta", "link"]):
        script.decompose()
    
    # Try common article content selectors
    article_text = ""
    
    content_selectors = [
        'article',
        '[role="article"]',
        'main',
        '.post-content',
        '.article-content',
        '.entry-content',
        '.content',
        '.post__body',
        '.post-body',
        '[class*="article-body"]',
        '[class*="post-body"]',
        '[class*="entry-content"]',
        '[class*="article-text"]',
        '[data-testid="storyBody"]',  # Medium
        '.essay',  # Some blogs
        '.post',
        '.story',
    ]
    
    content_elem = None
    for selector in content_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            break
    
    if content_elem:
        # Remove common non-content elements
        for elem in content_elem.find_all(['nav', 'footer', 'aside', 'ads', 'script', 'style']):
            elem.decompose()
        
        article_text = content_elem.get_text(separator='\n', strip=True)
    else:
        # Fallback: get all text from body, removing common noise
        body = soup.find('body')
        if body:
            # Remove common non-content sections
            for elem in body.find_all(['nav', 'footer', 'header', 'script', 'style', 'noscript']):
                elem.decompose()
            article_text = body.get_text(separator='\n', strip=True)
        else:
            article_text = soup.get_text(separator='\n', strip=True)
    
    # Clean up whitespace
    lines = [line.strip() for line in article_text.split('\n') if line.strip()]
    article_text = '\n'.join(lines)
    
    # Remove very short lines that are likely navigation/metadata
    paragraphs = article_text.split('\n\n')
    cleaned_paragraphs = [p for p in paragraphs if len(p) > 40]
    article_text = '\n\n'.join(cleaned_paragraphs)
    
    return title, article_text


def fetch_article(url: str, timeout: int = 10) -> Optional[Tuple[str, str, str]]:
    """
    Fetch an article from a URL and extract its title and content.
    Includes multiple strategies to bypass bot detection and handle protected content.
    
    Args:
        url: The article URL
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (url, title, content) or None if fetch fails
    """
    if not url.strip():
        print("❌ Empty URL provided")
        return None
    
    url = url.strip()
    
    # Validate URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Try multiple strategies
    strategies = [
        ("direct request with browser headers", lambda: _fetch_with_headers(url, timeout)),
        ("request with retries", lambda: _fetch_with_retries(url, timeout)),
        ("Jina Reader API", lambda: _fetch_with_jina(url, timeout)),
        ("JavaScript rendering (Playwright)", lambda: _fetch_with_playwright(url, timeout)),
    ]
    
    for strategy_name, strategy_func in strategies:
        try:
            print(f"📥 Attempting: {strategy_name}...")
            result = strategy_func()
            
            if result:
                title, content = result
                if len(content) > 100:
                    print(f"✅ Success with {strategy_name}")
                    print(f"📝 Content length: {len(content):,} characters")
                    return (url, title, content)
        except Exception as e:
            error_msg = str(e)[:80]
            print(f"   ⚠️  Failed: {error_msg}")
            continue
    
    print("❌ Could not extract article content — all strategies failed")
    print("💡 The site may require authentication or have strict bot protection")
    print("💡 Try a different article URL or copy-paste the content manually")
    return None


def _get_browser_headers() -> dict:
    """Return headers that mimic a real browser."""
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def _fetch_with_headers(url: str, timeout: int) -> Optional[Tuple[str, str]]:
    """Try basic request with proper browser headers."""
    headers = _get_browser_headers()
    response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
    response.raise_for_status()
    
    title, content = extract_article_title_and_text(response.text, url)
    return (title, content) if len(content) > 100 else None


def _fetch_with_retries(url: str, timeout: int, max_retries: int = 3) -> Optional[Tuple[str, str]]:
    """Try request with retries and exponential backoff."""
    headers = _get_browser_headers()
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"   ⏳ Retry {attempt}/{max_retries - 1}, waiting {wait_time}s...")
                time.sleep(wait_time)
            
            response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            title, content = extract_article_title_and_text(response.text, url)
            if len(content) > 100:
                return (title, content)
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
    
    return None


def _fetch_with_jina(url: str, timeout: int) -> Optional[Tuple[str, str]]:
    """
    Use Jina Reader API (free, works with most sites including Medium).
    Converts any URL to clean, readable content without needing JavaScript.
    
    Falls back to Mercury API if Jina fails.
    """
    # Try Jina first
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            'Accept': 'application/json',
            'User-Agent': _get_browser_headers().get('User-Agent', 'Mozilla/5.0'),
        }
        
        response = requests.get(jina_url, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        content = data.get('data', {}).get('content', '')
        title = data.get('data', {}).get('title', '')
        
        if not title:
            title = urlparse(url).netloc or 'Article'
        
        if content and len(content) > 100:
            return (title, content)
    except Exception as e:
        pass  # Try fallback
    
    # Fallback: Try Mercury API (alternative free service)
    try:
        mercury_url = f"https://api.mercury.com/parse?url={requests.utils.quote(url, safe='')}"
        headers = _get_browser_headers()
        
        response = requests.get(mercury_url, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        content = data.get('content', '')
        title = data.get('title', '')
        
        if not title:
            title = urlparse(url).netloc or 'Article'
        
        if content and len(content) > 100:
            return (title, content)
    except Exception:
        pass  # Both APIs failed
    
    raise Exception("Jina/Mercury APIs unavailable or rate-limited")


def _fetch_with_playwright(url: str, timeout: int) -> Optional[Tuple[str, str]]:
    """
    Use Playwright to render JavaScript-heavy sites (like Medium).
    Requires: pip install playwright && playwright install chromium
    """
    if not sync_playwright:
        raise Exception("Playwright not installed. Install with: pip install playwright && playwright install")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set a realistic user agent
            page.set_extra_http_headers(_get_browser_headers())
            
            print(f"   ⏳ Loading page with browser...")
            page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
            
            # Wait for content to render
            page.wait_for_timeout(2000)
            
            html = page.content()
            browser.close()
            
            title, content = extract_article_title_and_text(html, url)
            if len(content) > 100:
                return (title, content)
            return None
    except Exception as e:
        raise Exception(f"Playwright error: {str(e)[:60]}")



def validate_article_url(url: str) -> bool:
    """Check if a URL looks like it could be an article."""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip().lower()
    
    # Must start with http/https
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Reject obviously non-article URLs
    blocked_domains = [
        'youtube.com', 'youtu.be',  # Videos
        'github.com',  # Code repos
        'reddit.com',  # Social media
    ]
    
    for domain in blocked_domains:
        if domain in url:
            return False
    
    return True
