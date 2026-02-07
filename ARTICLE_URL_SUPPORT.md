# Article URL Support — Migration Guide

Your innovation-articles repository has been successfully updated to support both **YouTube videos** and **online articles**. You can now paste article URLs directly and generate Substack posts from them!

## What's New

### New Features
- ✅ **Article fetching** — Paste any article URL and the system extracts the title and content
- ✅ **Auto-detection** — The system automatically detects whether you've provided a YouTube URL or article link
- ✅ **Unified pipeline** — Same AI generation workflow works for both sources
- ✅ **Backward compatible** — All existing YouTube video functionality still works

### Updated Files

#### Core Modules (Backend)
1. **`core/article_fetcher.py`** (NEW)
   - Fetches articles from URLs using `requests` and `BeautifulSoup4`
   - Intelligently extracts article title and content from HTML
   - Validates URLs and handles various article formats
   - Functions:
     - `fetch_article(url)` — Fetch and extract article content
     - `extract_article_title_and_text(html, url)` — Parse HTML into structured content
     - `validate_article_url(url)` — Validate URL format

2. **`core/transcription.py`** (UPDATED)
   - Added `get_article_content(article_url)` — Fetch article-specific content
   - Added `get_source_content(source_url)` — Auto-detect YouTube vs article
   - `get_video_transcript()` still available for YouTube-only workflows
   - Imports new `article_fetcher` module

3. **`core/generator.py`** (UPDATED)
   - Added `generate_for_article(article_url, ...)` — Generate from articles
   - Added `generate_for_source(source_url, ...)` — Handle both types automatically
   - `generate_for_video()` still works for backward compatibility
   - Updated CSV structure to track `source_type` (video/article)
   - Updated `save_articles()` to store both video and article metadata

#### Backend API (`backend/app.py`) (UPDATED)
- Updated request model: `GenerateRequest` now accepts `url` and optional `source_type`
- Updated `/api/generate` endpoint to handle both sources
- Updated `/api/videos` endpoint (now works for all sources)
- Updated job processing to auto-detect source type or use explicit type
- All delete/read endpoints updated to work with generic "source" concept
- CSV parsing supports both old (video_title/video_url) and new (source_title/source_url/source_type) column names

#### Frontend Updates
- **`frontend/index.html`** (UPDATED)
  - Updated placeholder: "Paste a YouTube video URL or article link..."
  - Updated hero subtitle to mention both sources
  - Stats labels changed from "Videos" to "Sources" and "Articles" to "Generated"

- **`frontend/script.js`** (UPDATED)
  - Updated `startGeneration()` function to auto-detect source type
  - Relaxed URL validation (accepts any URL starting with http/https or containing a dot)
  - Sends `source_type: auto` to backend for intelligent detection
  - API request now sends `{ url, source_type }` instead of `{ video_url }`

#### New CLI Script
- **`scripts/generate_articles_from_url.py`** (NEW)
  - Command-line interface for generating articles from any URL
  - Usage: `python generate_articles_from_url.py "https://example.com/article"`
  - Options:
    - `--output` — Specify output directory
    - `--style` — Custom style reference file
    - `--type` — Explicitly set source type (article/video/auto)

#### Dependencies (`requirements.txt`, `backend/requirements.txt`)
- Added `beautifulsoup4` — For intelligent HTML parsing and article extraction

## How to Use

### Web Interface
1. Open the frontend at `http://localhost:5000` (or your deployment URL)
2. Paste either a YouTube URL or an article link in the input field
3. Click "Write Articles"
4. The system auto-detects the source type and generates Substack posts

### Command Line (YouTube Videos)
```bash
python scripts/generate_innovations_single_video.py "https://youtube.com/watch?v=VIDEO_ID"
```

### Command Line (Articles)
```bash
python scripts/generate_articles_from_url.py "https://example.com/article"
```

### Programmatic Usage
```python
from core.generator import generate_for_source

# Auto-detect source type
result = generate_for_source("https://example.com/my-article")

# Explicit article
result = generate_for_article("https://example.com/my-article")

# Explicit video
result = generate_for_video("https://youtube.com/watch?v=...")
```

## Technical Details

### Article Content Extraction
The article fetcher uses intelligent content selection:
- Tries multiple CSS selectors (article, main, .post-content, etc.)
- Removes navigation, ads, and footer elements
- Extracts and cleans text intelligently
- Falls back to full page text if dedicated selectors fail
- Cleans up whitespace and removes short lines

### Source Detection
- **YouTube**: Detected if URL contains "youtube.com" or "youtu.be"
- **Article**: Anything else that passes URL validation (must have http/https)
- **Auto**: Backend intelligently routes to correct handler

### Data Storage
CSV files now include a `source_type` column:
- `video` — YouTube videos
- `article` — Online articles
- Backward compatible with old column names (video_title → source_title, etc.)

## Migration Notes

✅ **Fully backward compatible**
- Old video_title/video_url columns still work
- YouTube functionality unchanged
- All existing articles/transcripts preserved

⚠️ **New installations**
- Must install `beautifulsoup4`: `pip install beautifulsoup4`
- Run `pip install -r requirements.txt` to update dependencies

## API Changes

### Request Format (Updated)
```json
// New (supports both)
POST /api/generate
{
  "url": "https://example.com/article",
  "source_type": "auto"  // "video", "article", or "auto"
}

// Still works (for backward compatibility)
POST /api/generate
{
  "video_url": "https://youtube.com/watch?v=..."
}
```

### Response Format (Unchanged)
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

## Troubleshooting

### Article Extraction Failures & Bot Detection

**Problem:** Getting HTTP 403 (Forbidden) or access denied errors when fetching articles from Medium, Paywalled sites, or other protected content?

The system includes **multiple strategies to bypass bot detection**:

#### Strategy 1: Browser Headers (Default)
- Uses realistic User-Agent and headers that mimic a modern browser
- Works for most sites that just check user-agent
- Fast and lightweight

#### Strategy 2: Retries with Exponential Backoff
- Automatically retries failed requests with delays (1s, 2s, 4s)
- Helps bypass rate limiting and temporary blocks
- Waits between attempts to appear more human-like

#### Strategy 3: Jina Reader API (Free)
- Uses Jina.ai's free Reader API to convert any URL to clean markdown
- **Works with Medium and most paywall-protected articles**
- No JavaScript rendering needed
- Reliable and fast

#### Strategy 4: JavaScript Rendering (Playwright)
- Renders pages with a real Chromium browser
- Loads and executes JavaScript like a real user
- Bypasses most bot detection
- Slower but most reliable
- **Requires installation:** `pip install playwright && playwright install`

### How the Fallback Works

The system automatically tries strategies in order:
```
Browser Headers → Retries → Jina API → Playwright
```

If one fails, it automatically tries the next. If all fail, you'll see helpful suggestions.

### Installation for Full Support

To enable all features including JavaScript rendering:

```bash
# Install Playwright (optional but recommended)
pip install playwright
python -m playwright install chromium
```

Then try your article URL again - the system will use JavaScript rendering if needed.

### Examples

**Free, public content (Works with Strategy 1-2):**
```bash
python scripts/generate_articles_from_url.py "https://en.wikipedia.org/wiki/AI"
python scripts/generate_articles_from_url.py "https://example.com/blog/article"
```

**Paywalled or Protected Content (Works with Strategy 3-4):**
```bash
# These now work thanks to Jina API fallback:
python scripts/generate_articles_from_url.py "https://medium.com/@author/article"
python scripts/generate_articles_from_url.py "https://dev.to/author/article"
```

### Still Having Issues?

1. **Check the error message** - it will tell you which strategy failed and why
2. **Try a different URL** - some sites have stronger protection
3. **Test a known working site first** - like Wikipedia or your own blog
4. **Ensure you have the latest version** - run `pip install -r requirements.txt`

### How to Debug

Use the test script to see which strategy works:
```bash
python scripts/test_fetch_strategies.py "https://your-article-url"
```

This shows exactly which strategy succeeds or fails.

## Next Steps

1. **Update dependencies**: `pip install -r requirements.txt`
2. **Test with an article**: Try pasting a Medium, Dev.to, or other article URL
3. **Check results**: Articles are saved to the same `articles/` directory with the same format

Enjoy generating Substack posts from any content! 🎉
