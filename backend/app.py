"""
Not So Quietly Disruptive — Article Studio
FastAPI backend serving the API and frontend.
"""

import csv
import re
import time
import uuid
import threading
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.generator import generate_for_video
from core.utils import sanitize_filename

# ── Paths ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
ARTICLES_DIR = ROOT / "articles"
TRANSCRIPTS_DIR = ROOT / "transcripts"
MASTER_CSV = ARTICLES_DIR / "all_articles.csv"

# Backward compat: also check old "innovations" directory
OLD_DIR = ROOT / "innovations"
OLD_CSV = OLD_DIR / "all_innovations.csv"

# ── App ──────────────────────────────────────────────────
app = FastAPI(title="Article Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ──────────────────────────────────
jobs: dict = {}


class ProgressLogger:
    def __init__(self, job_id: str, max_messages: int = 200):
        self.job_id = job_id
        self.messages: deque = deque(maxlen=max_messages)

    def log(self, msg: str):
        self.messages.append({"ts": time.time(), "msg": msg})

    def get_messages(self):
        return list(self.messages)


class GenerateRequest(BaseModel):
    video_url: str


# ── Background worker ────────────────────────────────────
def _run_generation(job_id: str, video_url: str, logger: ProgressLogger):
    jobs[job_id]["status"] = "running"
    logger.log(f"📋 Starting generation for: {video_url}")

    try:
        logger.log("🎙️ Extracting video information...")
        result = generate_for_video(
            video_url,
            output_dir=str(ARTICLES_DIR),
            logger=logger,
        )
        logger.log(f"✅ Generated {result['count']} articles!")
        logger.log("🎉 Done! Your article drafts are ready.")
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
    except Exception as exc:
        error_msg = str(exc)
        logger.log(f"❌ Error: {error_msg}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = error_msg


# ═══════════════════════════════════════════════════════════
#  API ROUTES
# ═══════════════════════════════════════════════════════════


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    video_url = req.video_url.strip()
    if not video_url:
        raise HTTPException(400, "video_url is required")

    job_id = str(uuid.uuid4())
    logger = ProgressLogger(job_id)
    jobs[job_id] = {
        "status": "queued",
        "video_url": video_url,
        "created": time.time(),
        "logger": logger,
    }

    thread = threading.Thread(
        target=_run_generation, args=(job_id, video_url, logger), daemon=True
    )
    thread.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    out = {k: v for k, v in job.items() if k != "logger"}
    logger: ProgressLogger | None = job.get("logger")
    if logger:
        out["progress"] = logger.get_messages()
    return out


# ── Videos (main listing) ───────────────────────────────
@app.get("/api/videos")
def list_videos():
    """Return every processed video with article counts."""
    videos: dict = {}

    # Scan both new and old CSV files
    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                title = row.get("video_title", "Unknown")
                url = row.get("video_url", "")

                if title not in videos:
                    video_id = _extract_video_id(url)
                    safe = sanitize_filename(title)
                    has_transcript = (TRANSCRIPTS_DIR / f"{safe}.txt").exists()

                    videos[title] = {
                        "title": title,
                        "url": url,
                        "video_id": video_id,
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                        if video_id
                        else None,
                        "has_transcript": has_transcript,
                        "article_count": 0,
                    }

                videos[title]["article_count"] += 1

    # Pick up transcripts that have no CSV entry yet
    if TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            t = meta.get("title", tf.stem)
            if t not in videos:
                vid = meta.get("video_id", "")
                videos[t] = {
                    "title": t,
                    "url": f"https://youtube.com/watch?v={vid}" if vid else "",
                    "video_id": vid,
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
                    if vid
                    else None,
                    "has_transcript": True,
                    "article_count": 0,
                }

    return sorted(videos.values(), key=lambda v: v["title"])


# ── Single video detail ──────────────────────────────────
@app.get("/api/videos/{video_id}")
def get_video_detail(video_id: str):
    """Return full content for one video: transcript + articles."""

    video_title = None
    video_url = ""
    rows: list[dict] = []

    # Search both new and old CSVs
    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if video_id in row.get("video_url", ""):
                    if not video_title:
                        video_title = row.get("video_title", "Unknown")
                        video_url = row.get("video_url", "")
                    rows.append(row)

    # Try transcript files
    if not video_title and TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            if meta.get("video_id") == video_id:
                video_title = meta.get("title", tf.stem)
                video_url = f"https://youtube.com/watch?v={video_id}"
                break

    if not video_title:
        raise HTTPException(404, "Video not found")

    safe = sanitize_filename(video_title)

    # ── Transcript ───────────────────────────────────────
    transcript_text = ""
    transcript_file = TRANSCRIPTS_DIR / f"{safe}.txt"
    if transcript_file.exists():
        transcript_text = transcript_file.read_text(encoding="utf-8")

    # ── Articles from file (full formatted text) ─────────
    articles_raw = ""
    for d in [ARTICLES_DIR, OLD_DIR]:
        f = d / f"{safe}.txt"
        if f.exists():
            articles_raw = f.read_text(encoding="utf-8")
            break

    # ── Structured articles from CSV ─────────────────────
    articles = []
    for row in rows:
        # Support both new and old column names
        art_title = row.get("article_title") or row.get("innovation_title", "Untitled")
        art_body = row.get("article_body") or row.get("innovation", "")

        articles.append({
            "title": art_title,
            "body": art_body,
        })

    # Fallback: parse from text file if no CSV rows
    if not articles and articles_raw:
        articles = _parse_articles_from_file(articles_raw)

    return {
        "title": video_title,
        "url": video_url,
        "video_id": video_id,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        "transcript": transcript_text,
        "articles_raw": articles_raw,
        "articles": articles,
    }


# ── Delete a whole video's content ───────────────────────
@app.delete("/api/videos/{video_id}")
def delete_video(video_id: str):
    deleted: list[str] = []
    video_title = None

    # Remove rows from both CSVs
    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue
        remaining: list[dict] = []
        fieldnames: list[str] = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                if video_id in row.get("video_url", ""):
                    video_title = row.get("video_title")
                else:
                    remaining.append(row)

        if fieldnames and video_title:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(remaining)
            deleted.append(f"CSV rows removed from {csv_path.name}")

    # Try transcript files
    if not video_title and TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            if meta.get("video_id") == video_id:
                video_title = meta.get("title", tf.stem)
                break

    if not video_title:
        raise HTTPException(404, "Video not found")

    safe = sanitize_filename(video_title)

    # Delete transcript
    tf = TRANSCRIPTS_DIR / f"{safe}.txt"
    if tf.exists():
        tf.unlink()
        deleted.append(tf.name)

    # Delete article files (check both dirs)
    for d in [ARTICLES_DIR, OLD_DIR]:
        af = d / f"{safe}.txt"
        if af.exists():
            af.unlink()
            deleted.append(af.name)

    return {"deleted": deleted, "video_title": video_title}


# ── Delete a single article ──────────────────────────────
@app.delete("/api/videos/{video_id}/articles/{article_title:path}")
def delete_article(video_id: str, article_title: str):
    video_title = None
    deleted: list[str] = []

    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue

        remaining: list[dict] = []
        fieldnames: list[str] = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                title_col = row.get("article_title") or row.get("innovation_title", "")
                match = video_id in row.get("video_url", "") and title_col == article_title
                if match:
                    video_title = row.get("video_title")
                else:
                    remaining.append(row)

        if video_title and fieldnames:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(remaining)
            deleted.append("CSV row removed")
            break

    if not video_title:
        raise HTTPException(404, "Article not found")

    return {"deleted": deleted}


# ── Health check ─────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "time": time.time()}


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════


def _extract_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return ""


def _parse_transcript_header(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    meta: dict = {}
    for line in text.split("\n")[:5]:
        if line.startswith("Title:"):
            meta["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("Video ID:"):
            meta["video_id"] = line.split(":", 1)[1].strip()
    return meta


def _parse_articles_from_file(raw: str) -> list[dict]:
    """Fallback: split a raw .txt file into article dicts."""
    articles = []
    sections = re.split(r"\n-{3,}\n", raw)
    for section in sections:
        section = section.strip()
        if not section or len(section) < 80:
            continue

        title_match = re.search(r"^\*\*(.+?)\*\*", section, re.MULTILINE)
        if not title_match:
            title_match = re.search(r"^#\s+(.+?)$", section, re.MULTILINE)

        title = title_match.group(1).strip() if title_match else "Untitled"
        body = section[title_match.end():].strip() if title_match else section

        if len(body) < 50:
            continue

        articles.append({"title": title, "body": body})
    return articles


# ═══════════════════════════════════════════════════════════
#  STATIC FILES — must be LAST so /api/* routes take priority
# ═══════════════════════════════════════════════════════════
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
