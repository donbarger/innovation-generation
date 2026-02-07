#!/usr/bin/env python3
"""
Test script to demonstrate bot detection bypass strategies.
Shows which strategy successfully fetches content from protected sites.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.article_fetcher import (
    _fetch_with_headers,
    _fetch_with_retries,
    _fetch_with_jina,
    _get_browser_headers,
)


def test_strategies(url: str):
    """Test each fetch strategy independently."""
    print(f"\n{'='*70}")
    print(f"Testing fetch strategies for: {url}")
    print(f"{'='*70}\n")
    
    # Strategy 1: Direct headers
    print("1️⃣  Direct request with browser headers...")
    try:
        result = _fetch_with_headers(url, timeout=10)
        if result:
            title, content = result
            print(f"   ✅ Success! Title: {title[:50]}")
            print(f"   📝 Content: {len(content)} chars\n")
            return
        else:
            print("   ⚠️  No content extracted\n")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)[:60]}\n")
    
    # Strategy 2: Retries with backoff
    print("2️⃣  Request with retries and exponential backoff...")
    try:
        result = _fetch_with_retries(url, timeout=10)
        if result:
            title, content = result
            print(f"   ✅ Success! Title: {title[:50]}")
            print(f"   📝 Content: {len(content)} chars\n")
            return
        else:
            print("   ⚠️  No content extracted\n")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)[:60]}\n")
    
    # Strategy 3: Jina Reader API
    print("3️⃣  Jina Reader API (free, no JS required)...")
    try:
        result = _fetch_with_jina(url, timeout=10)
        if result:
            title, content = result
            print(f"   ✅ Success! Title: {title[:50]}")
            print(f"   📝 Content: {len(content)} chars\n")
            return
        else:
            print("   ⚠️  No content extracted\n")
    except Exception as e:
        print(f"   ❌ Failed: {str(e)[:60]}\n")
    
    print("   💡 All strategies failed.")
    print("   Try installing Playwright for JavaScript support:")
    print("      pip install playwright && playwright install")
    print()


if __name__ == "__main__":
    test_urls = [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://www.medium.com/@example/article",  # Protected (will show fallback)
    ]
    
    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]
    
    for url in test_urls:
        test_strategies(url)
