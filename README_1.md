# Innovation Generation

Automated innovation generation pipeline that converts YouTube video transcripts
into conversational innovation pieces using Claude AI.

## Quick Start

1. Create a `.env` file (or export env vars) with your API keys:

```
ANTHROPIC_API_KEY=ADD_YOUR_API_KEY
ASSEMBLYAI_API_KEY=ADD_YOUR_API_KEY
```

2. Add your content and voice files:

- `channel_about.txt` — your channel voice/about text
- `presentation_transcript.txt` — style reference transcript
- `transcripts/` — source transcript files (one per video)

3. Run the pipeline:

```
python scripts/generate_innovations_pipeline.py \
  --playlist "https://youtube.com/playlist?list=PLAYLIST_ID" \
  --api-key $ANTHROPIC_API_KEY \
  --output innovations \
  --style-ref presentation_transcript.txt
```

## Notes

- Placeholder content in this repo is intentional. Replace any `REDACTED`
  files with your own transcripts/innovations/notes.
- API keys are **not** stored in this repo. Use environment variables or a
  local `.env` file and keep it out of version control.

