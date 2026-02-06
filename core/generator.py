"""
Article Generator — orchestrates transcript → AI → save pipeline.
Generates Substack article drafts from YouTube video transcripts.
"""

import csv
from pathlib import Path
from typing import List, Dict

from .transcription import get_video_transcript
from .ai_models import initialize_predictionguard, generate_articles
from .utils import sanitize_filename


def save_articles(
    articles: List[Dict[str, str]],
    video_id: str,
    video_title: str,
    output_dir: Path,
    master_csv: Path,
):
    """Persist articles to text file and master CSV."""
    output_dir.mkdir(exist_ok=True, parents=True)

    safe_title = sanitize_filename(video_title)
    video_url = f"https://youtube.com/watch?v={video_id}"

    # ── Write pretty-printed text file ────────────────────
    articles_file = output_dir / f"{safe_title}.txt"
    with articles_file.open("w", encoding="utf-8") as f:
        for i, art in enumerate(articles, 1):
            f.write(f"**{art['title']}**\n\n")
            f.write(f"{art['body']}\n\n")
            if i < len(articles):
                f.write("---\n\n")

    # ── Append structured rows to master CSV ──────────────
    file_exists = master_csv.exists()
    with master_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "video_title",
                "video_url",
                "article_title",
                "article_body",
            ])

        for art in articles:
            writer.writerow([
                video_title,
                video_url,
                art["title"],
                art["body"],
            ])

    return {
        "articles_file": str(articles_file),
        "count": len(articles),
    }


def generate_for_video(
    video_url: str,
    output_dir: str = "articles",
    style_ref: str = "presentation_transcript.txt",
    logger=None,
):
    """End-to-end: YouTube URL → transcript → articles → saved files."""

    def log(msg):
        if logger:
            logger.log(msg)
        print(msg)

    output_dir = Path(output_dir)
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)

    # 1. Fetch transcript ──────────────────────────────────
    log("🎬 Fetching video info and transcript...")
    res = get_video_transcript(video_url)
    if not res:
        log("❌ Could not retrieve transcript. Check YouTube URL and API keys.")
        raise RuntimeError("Could not retrieve transcript for video")

    video_id, video_title, transcript = res
    log(f"✅ Video: {video_title}")
    log(f"📝 Transcript length: {len(transcript):,} characters")

    # Save transcript ──────────────────────────────────────
    safe_title = sanitize_filename(video_title)
    transcript_file = transcripts_dir / f"{safe_title}.txt"
    transcript_file.write_text(
        f"Title: {video_title}\nVideo ID: {video_id}\n\n{transcript}",
        encoding="utf-8",
    )
    log(f"💾 Transcript saved: {transcript_file.name}")

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
        client, transcript, video_title, style_reference, channel_voice, logger=logger
    )

    if not articles:
        log("❌ No articles parsed from AI response")
        raise RuntimeError("No articles generated — check logs for details.")

    log(f"✨ Generated {len(articles)} article drafts")

    # 5. Save to disk ──────────────────────────────────────
    master_csv = output_dir / "all_articles.csv"
    log("💾 Saving articles...")
    result = save_articles(articles, video_id, video_title, output_dir, master_csv)
    log(f"✅ Done! Saved to {result['articles_file']}")

    return {
        "video_id": video_id,
        "video_title": video_title,
        "transcript_file": str(transcript_file),
        **result,
    }
