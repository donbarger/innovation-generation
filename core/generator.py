from pathlib import Path
from typing import List, Dict
from .transcription import get_video_transcript, read_assemblyai_config
from .ai_models import initialize_predictionguard, generate_innovations_and_notes, parse_innovation_body
from .utils import sanitize_filename
import os


def save_innovations(innovations: List[Dict[str, str]], video_id: str, video_title: str, output_dir: Path, master_csv: Path):
    output_dir.mkdir(exist_ok=True, parents=True)

    safe_title = sanitize_filename(video_title)
    video_url = f"https://youtube.com/watch?v={video_id}"

    innovations_file = output_dir / f"{safe_title}.txt"
    with innovations_file.open("w", encoding="utf-8") as f:
        for i, dev in enumerate(innovations, 1):
            f.write(f"**{dev['title']}**\n\n")
            f.write(f"{dev['body']}\n\n")
            if i < len(innovations):
                f.write("---\n\n")

    notes_dir = output_dir / "substack_notes"
    notes_dir.mkdir(exist_ok=True)

    note_files = []
    for i, dev in enumerate(innovations, 1):
        note_filename = f"{safe_title} - {sanitize_filename(dev['title'])}.txt"
        note_file = notes_dir / note_filename
        with note_file.open("w", encoding="utf-8") as f:
            f.write(f"Title: {dev['title']}\n")
            f.write(f"Source Video: {video_url}\n\n")
            f.write("NOTE 1:\n")
            f.write(dev.get('substack_note_1', '').strip() + "\n\n")
            f.write("NOTE 2:\n")
            f.write(dev.get('substack_note_2', '').strip() + "\n")
        note_files.append(str(note_file))

    # Append to master CSV
    file_exists = master_csv.exists()
    import csv
    with master_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["video_title", "video_url", "innovation_title", "key_insight", "innovation", "reflection", "summary"])

        for dev in innovations:
            parsed = parse_innovation_body(dev['body'])
            writer.writerow([
                video_title,
                video_url,
                dev['title'],
                parsed.get('scripture', ''),
                parsed.get('main_text', ''),
                parsed.get('reflection', ''),
                parsed.get('prayer', ''),
            ])

    return {
        "innovations_file": str(innovations_file),
        "note_files": note_files,
        "count": len(innovations),
    }


def generate_for_video(video_url: str, output_dir: str = "innovations", style_ref: str = "presentation_transcript.txt", logger=None):
    """Generate innovations from a YouTube video with detailed logging.
    
    Args:
        video_url: YouTube URL
        output_dir: Directory to save innovations
        style_ref: Path to style reference file
        logger: Optional logger object with log() method for progress tracking
    """
    
    def log(msg):
        if logger:
            logger.log(msg)
        print(msg)
    
    output_dir = Path(output_dir)
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)

    log("🎬 Fetching video info and transcript...")
    res = get_video_transcript(video_url)
    if not res:
        log("❌ Could not retrieve transcript. Check YouTube URL and API keys (AssemblyAI).")
        raise RuntimeError("Could not retrieve transcript for video")

    video_id, video_title, transcript = res
    log(f"✅ Video fetched: {video_title}")
    log(f"📝 Transcript length: {len(transcript)} characters")

    safe_title = sanitize_filename(video_title)
    transcript_file = transcripts_dir / f"{safe_title}.txt"
    transcript_file.write_text(f"Title: {video_title}\nVideo ID: {video_id}\n\n{transcript}", encoding="utf-8")
    log(f"💾 Saved transcript to: {transcript_file}")

    # Read style reference and channel voice
    log("📖 Loading style reference and channel voice...")
    style_reference = Path(style_ref).read_text(encoding="utf-8") if Path(style_ref).exists() else ""
    if not style_reference:
        log("⚠️  Style reference file not found, using defaults")
    
    channel_voice = Path("channel_about.txt").read_text(encoding="utf-8").strip() if Path("channel_about.txt").exists() else ""
    if not channel_voice:
        log("⚠️  Channel about file not found")

    # Initialize client and generate
    log("🤖 Initializing PredictionGuard client...")
    try:
        client = initialize_predictionguard()
        log("✅ PredictionGuard initialized")
    except RuntimeError as e:
        log(f"❌ PredictionGuard error: {e}")
        raise
    
    log("🧠 Generating innovations (this may take 30-60 seconds)...")
    innovations = generate_innovations_and_notes(client, transcript, video_title, style_reference, channel_voice, logger=logger)

    if not innovations:
        log("❌ Failed to parse innovations from AI response")
        log("💡 This might be a PredictionGuard API issue or the response format changed")
        raise RuntimeError("No innovations generated. Check logs for details.")

    log(f"✨ Generated {len(innovations)} innovations")

    master_csv = output_dir / "all_innovations.csv"
    log("💾 Saving to disk...")
    result = save_innovations(innovations, video_id, video_title, output_dir, master_csv)
    log(f"✅ Saved: {result['innovations_file']}")
    log(f"📱 Saved {len(result['note_files'])} Substack note files")

    return {
        "video_id": video_id,
        "video_title": video_title,
        "transcript_file": str(transcript_file),
        **result,
    }
