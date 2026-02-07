"""
Article Generator — orchestrates content → AI → save pipeline.
Generates Substack article drafts from YouTube videos or online articles.
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional

from .transcription import get_video_transcript, get_article_content, get_source_content
from .ai_models import initialize_predictionguard, generate_articles
from .utils import sanitize_filename


def save_articles(
    articles: List[Dict[str, str]],
    source_id: str,
    source_title: str,
    source_url: str,
    source_type: str,
    output_dir: Path,
    master_csv: Path,
):
    """Persist articles to text file and master CSV."""
    output_dir.mkdir(exist_ok=True, parents=True)

    safe_title = sanitize_filename(source_title)

    # ── Write pretty-printed text file ────────────────────
    articles_file = output_dir / f"{safe_title}.txt"
    with articles_file.open("w", encoding="utf-8") as f:
        for i, art in enumerate(articles, 1):
            f.write(f"**{art['title']}**\n\n")
            f.write(f"{art['body']}\n\n")
            if i < len(articles):
                f.write("---\n\n")

    import hashlib
    def make_id(url):
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    file_exists = master_csv.exists()
    with master_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "id",
                "source_title",
                "source_url",
                "video_url",
                "source_type",
                "article_title",
                "article_body",
            ])

        row_id = make_id(source_url)
        for art in articles:
            writer.writerow([
                row_id,
                source_title,
                source_url,
                source_url,  # Always write video_url for compatibility
                source_type,
                art["title"],
                art["body"],
            ])

    return {
        "articles_file": str(articles_file),
        "count": len(articles),
        "source_url": source_url,
        "source_title": source_title,
        "source_type": source_type,
    }


def generate_for_video(
    video_url: str,
    output_dir: str = "articles",
    style_ref: str = "presentation_transcript.txt",
    logger=None,
):
    """End-to-end: YouTube URL → transcript → articles → saved files."""
    return generate_for_source(video_url, output_dir, style_ref, logger, source_type="video")


def generate_for_article(
    article_url: str,
    output_dir: str = "articles",
    style_ref: str = "presentation_transcript.txt",
    logger=None,
):
    """End-to-end: Article URL → content → articles → saved files."""
    return generate_for_source(article_url, output_dir, style_ref, logger, source_type="article")


def generate_for_source(
    source_url: str,
    output_dir: str = "articles",
    style_ref: str = "presentation_transcript.txt",
    logger=None,
    source_type: Optional[str] = None,
):
    """End-to-end: Source URL → content → articles → saved files."""

    def log(msg):
        if logger:
            logger.log(msg)
        print(msg)

    output_dir = Path(output_dir)
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)

    # 1. Fetch content ──────────────────────────────────
    if source_type == "article":
        log("📄 Fetching article...")
        res = get_article_content(source_url)
    elif source_type == "video":
        log("🎬 Fetching video info and transcript...")
        res = get_video_transcript(source_url)
    else:
        # Auto-detect
        log("🔍 Detecting source type...")
        res = get_source_content(source_url)
        
        if res and ("youtube.com" in source_url or "youtu.be" in source_url):
            source_type = "video"
        else:
            source_type = "article"
    
    if not res:
        log("❌ Could not retrieve content. Check URL and API keys.")
        raise RuntimeError("Could not retrieve content from source")

    source_id, source_title, content = res
    log(f"✅ Source: {source_title}")
    log(f"📝 Content length: {len(content):,} characters")

    # Save content ──────────────────────────────────────
    safe_title = sanitize_filename(source_title)
    content_file = transcripts_dir / f"{safe_title}.txt"
    content_file.write_text(
        f"Title: {source_title}\nSource ID: {source_id}\nSource Type: {source_type}\n\n{content}",
        encoding="utf-8",
    )
    log(f"💾 Content saved: {content_file.name}")

    # 2. Load reference material ───────────────────────────
    log("📖 Loading your Substack style and channel voice...")
    style_reference = ""
    if Path(style_ref).exists():
        style_reference = Path(style_ref).read_text(encoding="utf-8")
    else:
        log("⚠️  Style reference file not found — articles may not match your voice")

    channel_voice = ""
    if Path("channel_about.txt").exists():
        channel_voice = Path("channel_about.txt").read_text(encoding="utf-8").strip()
    else:
        log("⚠️  channel_about.txt not found")

    # 3. Initialize AI client ──────────────────────────────
    log("🤖 Initializing PredictionGuard...")
    try:
        client = initialize_predictionguard()
        log("✅ PredictionGuard ready")
    except RuntimeError as e:
        log(f"❌ {e}")
        raise

    # 4. Generate articles ─────────────────────────────────
    log("✍️  Writing article drafts (this may take 30–60 seconds)...")
    articles = generate_articles(
        client, content, source_title, style_reference, channel_voice, logger=logger
    )

    if not articles:
        log("❌ No articles parsed from AI response")
        raise RuntimeError("No articles generated — check logs for details.")

    log(f"✨ Generated {len(articles)} article drafts")

    # 5. Save to disk ──────────────────────────────────────
    master_csv = output_dir / "all_articles.csv"
    log("💾 Saving articles...")
    result = save_articles(
        articles, 
        source_id, 
        source_title, 
        source_url, 
        source_type, 
        output_dir, 
        master_csv
    )
    log(f"✅ Done! Saved to {result['articles_file']}")

    return {
        "source_id": source_id,
        "source_title": source_title,
        "source_url": source_url,
        "source_type": source_type,
        "content_file": str(content_file),
        **result,
    }
