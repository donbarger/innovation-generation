#!/usr/bin/env python3
"""
Single video innovation generation pipeline using PredictionGuard:
1. Pull transcript from a single YouTube video
2. Generate innovations using PredictionGuard models
3. Generate 2 Substack notes per innovation
"""

import argparse
import json
import os
import re
import sys
import tempfile
import csv
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import assemblyai as aai
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from predictionguard import PredictionGuard

# Load environment variables from .env file
load_dotenv()

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
except:
    YouTubeTranscriptApi = None


def sanitize_filename(name: str) -> str:
    """Clean filename for safe filesystem use."""
    name = re.sub(r"[\\/:*?\"<>|]", "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180]


def read_assemblyai_config() -> Optional[str]:
    """Read AssemblyAI API key from assembly_ai.txt or environment."""
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if api_key and api_key != "ADD_YOUR_API_KEY":
        return api_key
    
    config_file = Path("assembly_ai.txt")
    if not config_file.exists():
        return None
    
    text = config_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    
    for line in lines:
        if line.startswith("API_KEY:"):
            api_key = line.split(":", 1)[1].strip().strip('"')
            return api_key
    
    return None


def try_youtube_transcript(video_id: str) -> Optional[str]:
    """Try to get transcript directly from YouTube."""
    if not YouTubeTranscriptApi:
        return None
    
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        lines = []
        for entry in transcript:
            text = entry.get("text", "").replace("\n", " ").strip()
            lines.append(text)
        return " ".join(lines).strip()
    except:
        return None


def transcribe_audio_with_assemblyai(audio_path: Path, api_key: str) -> Optional[str]:
    """Transcribe audio file using AssemblyAI."""
    try:
        aai.settings.api_key = api_key
        transcriber = aai.Transcriber()
        
        print(f"   🎙️  Transcribing with AssemblyAI...")
        transcript = transcriber.transcribe(
            str(audio_path),
            config=aai.TranscriptionConfig(speech_models=["universal"])
        )
        
        if transcript.status == aai.TranscriptStatus.error:
            print(f"   ❌ Transcription failed: {transcript.error}")
            return None
        
        print(f"   ✅ Transcription complete!")
        return transcript.text
        
    except Exception as e:
        print(f"   ❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_and_transcribe_audio(video_id: str, assemblyai_key: str) -> Optional[str]:
    """Download video audio and transcribe using AssemblyAI."""
    if not assemblyai_key:
        return None
    
    print(f"   📥 Downloading audio...")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        ydl_opts["outtmpl"] = str(tmpdir_path / "%(id)s.%(ext)s")
        
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=True)
                ext = info.get("ext", "m4a")
                audio_path = tmpdir_path / f"{video_id}.{ext}"
                
                if not audio_path.exists():
                    print(f"   ❌ Audio file not found")
                    return None
                
                # Transcribe with AssemblyAI
                text = transcribe_audio_with_assemblyai(audio_path, assemblyai_key)
                return text
                        
            except DownloadError as e:
                print(f"   ❌ Audio download failed: {e}")
                return None
            except Exception as e:
                print(f"   ❌ Unexpected error: {e}")
                import traceback
                traceback.print_exc()
                return None


def get_video_transcript(video_url: str) -> Optional[tuple]:
    """Get video ID and transcript from a YouTube video URL."""
    
    # Extract video ID from URL
    video_id = None
    if "youtube.com/watch?v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]
    
    if not video_id:
        print("❌ Invalid YouTube URL")
        return None
    
    # Get AssemblyAI API key
    assemblyai_key = read_assemblyai_config()
    
    # Get video info
    ydl_opts = {"quiet": True, "skip_download": True}
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title", f"Video_{video_id}")
            
            print(f"🎥 Video: {title}")
            
            # Try to get direct transcript
            text = try_youtube_transcript(video_id)
            if text:
                print(f"✅ Got transcript directly from YouTube!")
                return (video_id, title, text)
            
            # Try audio transcription with AssemblyAI
            if assemblyai_key:
                print(f"⚠️  No direct transcript, using AssemblyAI transcription...")
                text = download_and_transcribe_audio(video_id, assemblyai_key)
                if text:
                    return (video_id, title, text)
            else:
                print(f"❌ No AssemblyAI API key found")
            
            return None
            
    except Exception as e:
        print(f"❌ Error getting video: {e}")
        import traceback
        traceback.print_exc()
        return None


def initialize_predictionguard() -> PredictionGuard:
    """Initialize PredictionGuard client from environment variables."""
    api_key = os.environ.get("PREDICTIONGUARD_API_KEY")
    base_url = os.environ.get("PREDICTIONGUARD_URL")
    
    if not api_key or not base_url:
        print("\n❌ Missing PredictionGuard Configuration")
        print("=" * 60)
        print("Please set the following in your .env file:")
        print("  PREDICTIONGUARD_API_KEY=your_api_key")
        print("  PREDICTIONGUARD_URL=https://globalpath.predictionguard.com")
        print("\nOr export them as environment variables:")
        print("  export PREDICTIONGUARD_API_KEY=your_api_key")
        print("  export PREDICTIONGUARD_URL=https://globalpath.predictionguard.com")
        print("=" * 60)
        sys.exit(1)
    
    return PredictionGuard(url=base_url, api_key=api_key)


def generate_innovations_and_notes(
    transcript: str,
    video_title: str,
    style_reference: str,
    channel_voice: str,
) -> List[Dict[str, any]]:
    """Generate innovations and Substack notes using PredictionGuard."""
    
    print(f"\n📝 Generating innovations with PredictionGuard...")
    
    client = initialize_predictionguard()
    
    # Build system prompt
    system_prompt = f"""You are an expert innovation and technology writer focused on the intersection of faith and technology. Your task is to create simple, conversational pieces about innovation that help Christians understand how to embrace technology thoughtfully.

CHANNEL VOICE:
{channel_voice}

YOUR WRITING MISSION:
- Help readers understand innovation through a Christian lens
- Show how technology and faith can work together
- Make complex tech concepts accessible and relatable
- Challenge readers to think critically about innovation's impact

CRITICAL RULES:
1. Extract key insights about innovation, technology, or their intersection with faith from the transcript
2. DO NOT include the speaker's personal stories or biographical details
3. DO NOT use first-person narrative that sounds like personal testimony ("I realized", "changed my thinking", etc.)
4. Use conversational, simple language (avoid heavy jargon, but define technical terms when needed)
5. Short sentences and paragraphs for easy scanning
6. Direct address using "you" to engage the reader
7. Voice should be thought-leadership/teaching, NOT personal memoir
8. Use phrases like "Here's what matters...", "Consider this perspective...", "The real issue is..." NOT personal experience narratives
9. Make it practical - readers should understand why this innovation matters to them
10. Balance innovation insight with faith perspective when relevant to your channel

FORMAT for each innovation (follow this EXACTLY):

**The Real Reason Christians Should Care About AI**

Key Insight: Technology is a tool that reflects the values of those who create and use it

[3-5 conversational paragraphs of 2-4 sentences each - your main innovation content here]

**Think about it:** [One reflection question that challenges assumptions or deepens understanding]

**Summary:** [Simple, direct takeaway in 2-3 sentences]

---

SUBSTACK NOTE 1:
[3-6 short lines, punchy, memorable, uses line breaks for impact]

---

SUBSTACK NOTE 2:
[3-6 short lines, different angle/hook than note 1, engaging and shareable]

---

TITLE REQUIREMENTS:
- Must be specific and engaging (e.g., "The Real Reason Christians Should Care About AI", "Why Your Tech Stack Matters More Than You Think", "How Innovation Is Reshaping Discipleship")
- Must capture the core insight or debate of the piece
- Should be 4-10 words
- NEVER use "Key Insight:", "Innovation", or generic placeholders

STYLE REFERENCE (conversational examples):
{style_reference[:4000]}

SUBSTACK NOTE STYLE EXAMPLES:
1. Technology is never neutral.

Every tool we build carries the values of its creators.
Every platform we use shapes how we think.
Every innovation we adopt changes what we believe is possible.

The real question isn't "should Christians use this?"
It's "does this serve what we're called to become?"

2. Disruption looks different when you're the one being disrupted.

Innovation feels good when it's on your terms.
It feels threatening when it challenges your status quo.

Maybe that's the moment worth paying attention to.

3. The church has always been behind on technology adoption.

Not because we're anti-innovation.
But because we're still asking questions other industries already forgot to ask:

Who does this serve?
What does this cost us?
What are we trading away?

Remember: 
- Extract the actionable insight, not the speaker's personal journey
- Teach the principle, not the story
- NEVER use first-person that sounds like YOUR experience or perspective
- You're SHARING innovation perspective, not personal testimony
- This is for Christians thinking about technology and innovation - keep that lens in mind"""
    
    user_message = f"""Generate 3-4 innovations from this content transcript. For each innovation, also generate 2 Substack notes (short, punchy, social media style).

VIDEO TITLE: {video_title}

TRANSCRIPT:
{transcript[:15000]}

Generate innovations that extract key insights without copying the speaker's personal experiences. Make it conversational and practical. Follow the Substack note style examples closely."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            temperature=0.7,
            max_completion_tokens=8000,
        )
        
        content = response["choices"][0]["message"]["content"].strip()
        
        print(f"✅ Generation complete!")
        
        # Parse the response
        innovations = parse_innovations_and_notes(content)
        
        if not innovations:
            # Debug: save the raw output to see what the model generated
            debug_file = Path("debug_pg_output.txt")
            debug_file.write_text(content, encoding="utf-8")
            print(f"   ⚠️  Parsing failed. Raw output saved to: {debug_file}")
        
        return innovations
        
    except Exception as e:
        print(f"❌ Error generating innovations: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_innovations_and_notes(content: str) -> List[Dict[str, str]]:
    """Parse response into structured innovations with notes."""
    
    innovations = []
    
    # Split by multiple "---" separators
    sections = re.split(r'\n---+\n', content)
    
    i = 0
    while i < len(sections):
        section = sections[i].strip()
        
        # Skip empty or very short sections
        if not section or len(section) < 50:
            i += 1
            continue
        
        # Extract title - try markdown header first, then bold
        title_match = re.search(r'^#\s+(.+?)$', section, re.MULTILINE) or re.search(r'^\*\*(.+?)\*\*', section, re.MULTILINE)
        
        if not title_match:
            i += 1
            continue
        
        title = title_match.group(1).strip()
        
        # Skip if title is "Key Insight:" or similar formatting artifacts
        if title.lower() in ["key insight:", "key insight", "innovation", "think about it:", "summary:"]:
            # Try to extract a better title from the content
            body_preview = section[:500]
            theme_patterns = [
                r"Here's (?:something|a truth|what's)\s+(?:that\s+)?([^.!?]{20,80})[.!?]",
                r"(?:You know what|Think about)\s+([^.!?]{20,80})[.!?]",
                r"Jesus (?:said|told|taught)\s+([^.!?]{20,80})[.!?]",
            ]
            
            generated_title = None
            for pattern in theme_patterns:
                match = re.search(pattern, body_preview, re.IGNORECASE)
                if match:
                    generated_title = match.group(1).strip()
                    generated_title = generated_title[:60]
                    if not generated_title[0].isupper():
                        generated_title = generated_title.capitalize()
                    break
            
            if generated_title:
                title = generated_title
            else:
                first_line = re.search(r'\n\n([A-Z][^.!?]{10,80})[.!?]', section)
                if first_line:
                    title = first_line.group(1)[:60]
                else:
                    i += 1
                    continue
        
        # Get body (everything after title)
        body_start = section.find(title_match.group(0)) + len(title_match.group(0))
        body = section[body_start:].strip()
        
        # Look for next two sections as potential Substack notes
        note1 = ""
        note2 = ""
        
        if i + 1 < len(sections):
            next_section = sections[i + 1].strip()
            if len(next_section) < 400 and "Key Insight:" not in next_section and "Think about it:" not in next_section:
                note1 = next_section
                i += 1
                
                if i + 1 < len(sections):
                    next_next = sections[i + 1].strip()
                    if len(next_next) < 400 and "Key Insight:" not in next_next and "Think about it:" not in next_next:
                        note2 = next_next
                        i += 1
        
        innovations.append({
            "title": title,
            "body": body,
            "substack_note_1": note1,
            "substack_note_2": note2
        })
        
        i += 1
    
    return innovations


def parse_innovation_body(body: str) -> Dict[str, str]:
    """Parse innovation body into key_insight, main text, reflection, and summary."""
    
    scripture_match = re.search(r'Key Insight:\s*(.+?)(?=\n\n)', body, re.IGNORECASE)
    scripture = scripture_match.group(1).strip() if scripture_match else ""
    
    reflection_match = re.search(r'\*\*Think about it:\*\*\s*(.+?)(?=\n\n\*\*Summary)', body, re.DOTALL | re.IGNORECASE)
    reflection = reflection_match.group(1).strip() if reflection_match else ""
    
    prayer_match = re.search(r'\*\*Summary:\*\*\s*(.+?)$', body, re.DOTALL | re.IGNORECASE)
    prayer = prayer_match.group(1).strip() if prayer_match else ""
    
    if scripture_match and reflection_match:
        start = scripture_match.end()
        end = reflection_match.start()
        main_text = body[start:end].strip()
    else:
        main_text = body
    
    return {
        "scripture": scripture,
        "main_text": main_text,
        "reflection": reflection,
        "prayer": prayer
    }


def save_innovations(innovations: List[Dict[str, str]], video_id: str, video_title: str, output_dir: Path, master_csv: Path):
    """Save innovations, Substack notes, and append to master CSV."""
    
    output_dir.mkdir(exist_ok=True, parents=True)
    
    safe_title = sanitize_filename(video_title)
    video_url = f"https://youtube.com/watch?v={video_id}"
    
    # Save main innovations file
    innovations_file = output_dir / f"{safe_title}.txt"
    
    with innovations_file.open("w", encoding="utf-8") as f:
        for i, dev in enumerate(innovations, 1):
            f.write(f"**{dev['title']}**\n\n")
            f.write(f"{dev['body']}\n\n")
            if i < len(innovations):
                f.write("---\n\n")
    
    print(f"\n✅ Saved innovations: {innovations_file}")
    
    # Save Substack notes separately — one file per innovation, named after the article
    notes_dir = output_dir / "substack_notes"
    notes_dir.mkdir(exist_ok=True)

    for i, dev in enumerate(innovations, 1):
        # Create a safe filename per innovation
        note_filename = f"{safe_title} - {sanitize_filename(dev['title'])}.txt"
        note_file = notes_dir / note_filename

        with note_file.open("w", encoding="utf-8") as f:
            f.write(f"Title: {dev['title']}\n")
            f.write(f"Source Video: {video_url}\n\n")
            f.write("NOTE 1:\n")
            f.write(dev.get('substack_note_1', '').strip() + "\n\n")
            f.write("NOTE 2:\n")
            f.write(dev.get('substack_note_2', '').strip() + "\n")

        print(f"✅ Saved Substack notes: {note_file}")
    
    # Append to master CSV
    file_exists = master_csv.exists()
    
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
                parsed['scripture'],
                parsed['main_text'],
                parsed['reflection'],
                parsed['prayer']
            ])
    
    print(f"✅ Appended to master CSV: {master_csv}")
    
    return len(innovations)


def main():
    parser = argparse.ArgumentParser(description="Generate innovations from a single YouTube video")
    parser.add_argument("--video", required=True, help="YouTube video URL")
    parser.add_argument("--output", default="innovations", help="Output directory")
    parser.add_argument("--style-ref", default="presentation_transcript.txt", help="Style reference file")
    
    args = parser.parse_args()
    
    # Verify PredictionGuard configuration
    try:
        pg_client = initialize_predictionguard()
        print("✅ PredictionGuard configured successfully")
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    
    # Get AssemblyAI key
    assemblyai_key = read_assemblyai_config()
    if not assemblyai_key:
        print("❌ No AssemblyAI API key provided. Set ASSEMBLYAI_API_KEY or add to assembly_ai.txt")
        return 1
    
    # Read style reference
    style_ref_path = Path(args.style_ref)
    if not style_ref_path.exists():
        print(f"❌ Style reference not found: {style_ref_path}")
        return 1
    
    style_reference = style_ref_path.read_text(encoding="utf-8")
    
    # Channel voice
    channel_about_path = Path("channel_about.txt")
    if channel_about_path.exists():
        channel_voice = channel_about_path.read_text(encoding="utf-8").strip()
    else:
        channel_voice = "ADD_YOUR_CHANNEL_ABOUT"
    
    # Get video transcript
    print("📋 Fetching video...")
    result = get_video_transcript(args.video)
    
    if not result:
        print("❌ Could not get video or transcript")
        return 1
    
    video_id, video_title, transcript = result
    
    print(f"\n{'='*60}")
    print(f"🎥 Processing: {video_title}")
    print(f"{'='*60}")
    
    # Generate innovations
    innovations = generate_innovations_and_notes(
        transcript,
        video_title,
        style_reference,
        channel_voice
    )
    
    if not innovations:
        print("❌ No innovations generated")
        return 1
    
    # Save transcript
    transcript_dir = Path("transcripts")
    transcript_dir.mkdir(exist_ok=True)
    safe_title = sanitize_filename(video_title)
    transcript_file = transcript_dir / f"{safe_title}.txt"
    transcript_file.write_text(f"Title: {video_title}\nVideo ID: {video_id}\n\n{transcript}", encoding="utf-8")
    print(f"\n✅ Saved transcript: {transcript_file}")
    
    # Save innovations
    output_dir = Path(args.output)
    master_csv = output_dir / "all_innovations.csv"
    count = save_innovations(innovations, video_id, video_title, output_dir, master_csv)
    
    print(f"\n{'='*60}")
    print(f"🎉 COMPLETE!")
    print(f"📖 Generated {count} innovations with {count * 2} Substack notes")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
