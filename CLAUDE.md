# Innovation Generation

Automated innovation content pipeline that converts YouTube video transcripts into innovation articles and Substack notes using PredictionGuard AI.

## Tech Stack

- Python 3.13 with virtual environment at `.venv/`
- PredictionGuard API (gpt-oss-120b model) for content generation
- FastAPI backend serving both API and frontend
- Vanilla HTML/CSS/JS frontend (no React/Node required)
- yt-dlp + youtube-transcript-api for transcript extraction
- AssemblyAI as fallback transcription service

## Quick Start

```bash
./run.sh
```

That's it. The script creates a virtual environment, installs dependencies, and launches the server at `http://localhost:8000`.

Required: A `.env` file with:
```
PREDICTIONGUARD_API_KEY=your_key
PREDICTIONGUARD_URL=https://globalpath.predictionguard.com
ASSEMBLYAI_API_KEY=your_key  (optional, for videos without captions)
```

## Project Structure

- `run.sh` — One-command launcher (creates venv, installs deps, starts server)
- `backend/app.py` — FastAPI server (API + static file serving)
- `frontend/` — Self-contained HTML/CSS/JS UI
- `core/` — Core Python modules:
  - `generator.py` — Main orchestration (transcript → innovations)
  - `transcription.py` — YouTube/AssemblyAI transcript extraction
  - `ai_models.py` — PredictionGuard API integration
  - `utils.py` — Shared utilities
- `scripts/` — Standalone pipeline scripts (batch/single video)
- `innovations/` — Generated innovation text files and CSV
- `innovations/substack_notes/` — Generated Substack note files
- `transcripts/` — Saved video transcripts

## API Endpoints

- `POST /api/generate` — Start a generation job from YouTube URL
- `GET /api/jobs/{job_id}` — Poll job status and progress
- `GET /api/videos` — List all processed videos with counts
- `GET /api/videos/{video_id}` — Full detail: transcript, innovations, notes
- `DELETE /api/videos/{video_id}` — Delete all content for a video
- `DELETE /api/videos/{video_id}/innovations/{title}` — Delete single innovation
- `GET /api/health` — Health check

## Content Guidelines

Innovations should be conversational, use simple language, address the reader as "you", and extract innovation insights from transcripts. See `innovation_generation_guidelines.txt` and `channel_about.txt` for voice/style rules.
