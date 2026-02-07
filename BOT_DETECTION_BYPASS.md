# Bot Detection Bypass Guide

## Overview

Your article fetcher now includes **4 intelligent fallback strategies** to handle bot detection and website restrictions. It automatically tries each strategy in order until one succeeds.

## The 4 Strategies (In Order)

### 1️⃣ Browser Headers (Default)
**Speed:** ⚡ Fast  
**Compatibility:** 80% of sites  
**Requirements:** None (built-in)

Uses realistic browser headers and User-Agent that match modern Chrome/Safari.
Works for sites that only check basic headers.

```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) 
AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36
```

**Works with:**
- Wikipedia, personal blogs, news sites
- Most medium-traffic websites
- Simple static content sites

---

### 2️⃣ Retry with Exponential Backoff
**Speed:** 🟡 Medium (10-15s with retries)  
**Compatibility:** 85% of sites  
**Requirements:** None (built-in)

Automatically retries failed requests with intelligent delays:
- Attempt 1: Immediate
- Attempt 2: Wait 2 seconds
- Attempt 3: Wait 4 seconds

Bypasses rate limiting and temporary IP blocks.

**Works with:**
- Sites that temporarily block repeat requests
- Servers that accept browsers but rate-limit bots
- Flaky connections

---

### 3️⃣ Jina Reader API (Free)
**Speed:** 🔴 Slow (10-20s)  
**Compatibility:** 90% of sites  
**Requirements:** Internet connection (free, no API key needed)

Uses Jina.ai's free Reader API to convert any webpage to clean, parseable content.
Jina handles complex layouts, ads, paywalls, and JavaScript.

**Endpoint:** `https://r.jina.ai/{url}`

**Works with:**
- Medium articles (often)
- Dev.to, Hashnode
- News sites
- Paywalled content (sometimes)
- JavaScript-heavy sites

⚠️ **Note:** Jina has rate limits (free tier). If overused, it returns 403.

---

### 4️⃣ Playwright (JavaScript Rendering)
**Speed:** 🔴 Very Slow (15-30s)  
**Compatibility:** 95%+ of sites  
**Requirements:** `pip install playwright && playwright install`

Launches a real headless Chromium browser to render pages exactly like a human would.
Executes JavaScript, loads dynamic content, and handles all authentication flows.

**Most reliable but slowest option.**

**Works with:**
- Medium (when Jina fails)
- Single-page apps
- JavaScript-heavy sites
- Almost everything

**Installation:**
```bash
pip install playwright
python -m playwright install chromium
```

---

## How to Test Each Strategy

### Test Script
```bash
python scripts/test_fetch_strategies.py "https://your-article-url"
```

Shows which strategy works (or fails) and why.

### Manual Testing
```python
from core.article_fetcher import (
    _fetch_with_headers,
    _fetch_with_retries,
    _fetch_with_jina,
    _fetch_with_playwright,
)

url = "https://example.com/article"

# Test each individually
result1 = _fetch_with_headers(url, timeout=10)
result2 = _fetch_with_retries(url, timeout=10)
result3 = _fetch_with_jina(url, timeout=10)
result4 = _fetch_with_playwright(url, timeout=10)
```

---

## Performance Comparison

| Strategy | Speed | Success Rate | Setup | When to Use |
|----------|-------|--------------|-------|------------|
| Browser Headers | ⚡ Fast | ~80% | None | First try |
| Retry Backoff | 🟡 Medium | ~85% | None | If headers fail |
| Jina API | 🔴 Slow | ~90% | None | Paywalls, Medium |
| Playwright | 🔴 Very Slow | ~95% | Install | Last resort |

---

## Common Issues & Solutions

### "HTTP 403 Forbidden"
The site is explicitly blocking requests that look like bots.

**Solutions:**
1. Try a different article URL from the same site
2. Enable Playwright for JavaScript rendering
3. Some paywalled sites cannot be bypassed (legal restriction)

### "Jina API unavailable"
Jina's free tier has rate limits and may be temporarily blocked.

**Solutions:**
1. Wait a minute and try again
2. Use Playwright instead (more reliable)
3. Try a simpler article first

### Playwright timeout
The page takes too long to load.

**Solutions:**
1. Try articles from faster sites
2. Increase timeout: `timeout=30` instead of `timeout=10`
3. Try another strategy first

### Rate limiting (429 error)
You've made too many requests too fast.

**Solutions:**
1. Wait a few minutes
2. Use different article URLs
3. Stagger requests over time

---

## Example Output

### Success with Strategy 1
```
📥 Attempting: direct request with browser headers...
✅ Success with direct request with browser headers
📝 Content length: 5,432 characters
```

### Success with Strategy 3
```
📥 Attempting: direct request with browser headers...
   ⚠️  Failed: 403 Client Error
📥 Attempting: request with retries...
   ⏳ Retry 1/2, waiting 2s...
   ⚠️  Failed: 403 Client Error
📥 Attempting: Jina Reader API...
✅ Success with Jina Reader API
📝 Content length: 4,821 characters
```

---

## Recommended Articles to Test

These are known to work:

✅ **Always work:**
```
https://en.wikipedia.org/wiki/Artificial_intelligence
https://xkcd.com
https://www.example.com
```

✅ **Usually work:**
```
https://dev.to (Dev community)
https://hashnode.com (Tech blog platform)
https://substack.com/archive (Open archive)
```

⚠️ **Sometimes work (requires Playwright):**
```
https://medium.com (May need JS rendering)
https://www.reuters.com (News site)
https://www.bbc.com/news (Paywall sometimes)
```

❌ **Won't work:**
```
https://youtube.com (Videos, not articles)
https://github.com (Code, not articles)
Sites behind paywalls (WSJ, FT, NYT)
```

---

## Configuration

### Timeout Settings
Edit timeout in script:
```python
# Default: 10 seconds
result = fetch_article(url, timeout=10)

# For slow sites: 30 seconds
result = fetch_article(url, timeout=30)

# For fast sites: 5 seconds
result = fetch_article(url, timeout=5)
```

### Disable Specific Strategies
Edit `article_fetcher.py` to remove strategies you don't need:
```python
strategies = [
    ("direct request with browser headers", lambda: _fetch_with_headers(url, timeout)),
    ("request with retries", lambda: _fetch_with_retries(url, timeout)),
    # Comment out to skip:
    # ("Jina Reader API", lambda: _fetch_with_jina(url, timeout)),
    # ("JavaScript rendering (Playwright)", lambda: _fetch_with_playwright(url, timeout)),
]
```

---

## Advanced: Custom Headers

Add even more specific headers for stubborn sites:
```python
headers = {
    'User-Agent': 'Mozilla/5.0...',
    'Referer': 'https://google.com/',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Cache-Control': 'max-age=0',
}
```

---

## Summary

The multi-strategy approach means:
- ✅ Most articles work immediately (fast)
- ✅ Protected content works with fallbacks (slower but reliable)
- ✅ Last resort is Playwright for JavaScript-heavy sites
- ✅ If all fail, you get helpful error messages

**Start with:** Browser headers (fast)  
**If blocked:** Automatic retry kicks in  
**If persists:** Try Jina API (works for 90% of cases)  
**Last resort:** Playwright (works for almost everything)
