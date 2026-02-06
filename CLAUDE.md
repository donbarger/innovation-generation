# learn-bible

Automated devotion generation pipeline that converts YouTube sermon transcripts (Zac Poonen's "All That Jesus Taught" series) into conversational daily devotions using Claude AI.

## Tech Stack

- Python 3.13 with virtual environment at `.venv/`
- Anthropic Claude API (Haiku 4.5 with prompt caching)
- yt-dlp + youtube-transcript-api for transcript extraction
- AssemblyAI as fallback transcription service

## Setup

```bash
source .venv/bin/activate
```

Required env vars: `ANTHROPIC_API_KEY` (or `CLAUDE_API_KEY`), `ASSEMBLYAI_API_KEY` (optional, also reads from `assembly_ai.txt`).

## Key Commands

### Generate devotions from a YouTube playlist

```bash
python scripts/generate_devotions_pipeline.py \
  --playlist "https://youtube.com/playlist?list=PLAYLIST_ID" \
  --api-key $ANTHROPIC_API_KEY \
  --output devotions \
  --style-ref presentation_transcript.txt
```

Pulls transcripts, generates 3-4 devotions + 2 Substack notes per video, saves to text files and CSV. Skips already-processed videos.

### Download audio from a single YouTube video

```bash
python scripts/download_youtube_audio.py "https://youtube.com/watch?v=VIDEO_ID"
python scripts/download_youtube_audio.py "https://youtube.com/watch?v=VIDEO_ID" --output my_audio.m4a
```

## Project Structure

- `scripts/` - Pipeline and utility scripts
- `devotions/` - Generated devotion text files (~155 files)
- `transcripts/` - YouTube sermon transcripts (~77 files)
- `presentation_transcript.txt` - Style reference for conversational tone
- `channel_about.txt` - Channel voice/brand guidelines
- `devotion_generation_guidelines.txt` - Generation rules and quality checklist
- `devotions_project_process.txt` - Full project documentation

## Content Guidelines

Devotions must be conversational (like talking to a friend), use simple language, address the reader as "you", and extract biblical principles without copying the speaker's personal stories or biographical details. No theological jargon. See `devotion_generation_guidelines.txt` for full rules.
