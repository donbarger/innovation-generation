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

from core.generator import generate_for_video, generate_for_article, generate_for_source
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
    url: str
    source_type: str = "auto"  # "video", "article", or "auto"


# ── Background worker ────────────────────────────────────
def _run_generation(job_id: str, url: str, source_type: str, logger: ProgressLogger):
    jobs[job_id]["status"] = "running"
    logger.log(f"📋 Starting generation for: {url}")

    try:
        if source_type == "article":
            logger.log("📄 Processing article...")
            result = generate_for_article(
                url,
                output_dir=str(ARTICLES_DIR),
                logger=logger,
            )
        elif source_type == "video":
            logger.log("🎙️ Extracting video information...")
            result = generate_for_video(
                url,
                output_dir=str(ARTICLES_DIR),
                logger=logger,
            )
        else:
            # auto-detect
            logger.log("🔍 Detecting source type...")
            result = generate_for_source(
                url,
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
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "url is required")

    job_id = str(uuid.uuid4())
    logger = ProgressLogger(job_id)
    jobs[job_id] = {
        "status": "queued",
        "url": url,
        "source_type": req.source_type,
        "created": time.time(),
        "logger": logger,
    }

    thread = threading.Thread(
        target=_run_generation, args=(job_id, url, req.source_type, logger), daemon=True
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


# ── Sources (main listing) ───────────────────────────────
@app.get("/api/videos")
def list_videos():
    """Return every processed source with article counts."""

    sources: dict = {}

    # Scan both new and old CSV files
    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # Support both old (video_title, video_url) and new (source_title, source_url) formats
                title = row.get("source_title") or row.get("video_title", "Unknown")
                url = row.get("source_url") or row.get("video_url", "")
                source_type = row.get("source_type", "video")
                id_val = row.get("id") or ""

                if title not in sources:
                    safe = sanitize_filename(title)
                    has_transcript = (TRANSCRIPTS_DIR / f"{safe}.txt").exists()

                    sources[title] = {
                        "id": id_val,
                        "title": title,
                        "url": url,
                        "source_type": source_type,
                        "has_transcript": has_transcript,
                        "article_count": 0,
                    }

                sources[title]["article_count"] += 1

    # Pick up transcripts that have no CSV entry yet
    if TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            t = meta.get("title", tf.stem)
            if t not in sources:
                source_type = meta.get("source_type", "unknown")
                url = meta.get("source_id", "")
                sources[t] = {
                    "id": meta.get("source_id", ""),
                    "title": t,
                    "url": url,
                    "source_type": source_type,
                    "has_transcript": True,
                    "article_count": 0,
                }

    return sorted(sources.values(), key=lambda v: v["title"])


# ── Single source detail ──────────────────────────────
@app.get("/api/videos/{source_id}")
def get_video_detail(source_id: str):
    """Return full content for one source: transcript + articles."""

    source_title = None
    source_url = ""
    source_type = "unknown"
    rows: list[dict] = []

    # Decode source_id for robust matching
    from urllib.parse import unquote
    decoded_id = unquote(source_id).rstrip('/').lower()

    # Search both new and old CSVs
    for csv_path in [MASTER_CSV, OLD_CSV]:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row_id = (row.get("id") or "").lower()
                if decoded_id == row_id:
                    if not source_title:
                        source_title = row.get("source_title") or row.get("video_title", "Unknown")
                        source_url = row.get("source_url") or row.get("video_url", "")
                        source_type = row.get("source_type", "video")
                    rows.append(row)

    # Try transcript files
    if not source_title and TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            if source_id in str(meta.get("source_id", "")) or source_id in str(meta.get("video_id", "")):
                source_title = meta.get("title", tf.stem)
                source_type = meta.get("source_type", "unknown")
                source_url = meta.get("source_id", "")
                break

    if not source_title:
        raise HTTPException(404, "Source not found")

    safe = sanitize_filename(source_title)

    # ── Content ──────────────────────────────────────────
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
        "title": source_title,
        "url": source_url,
        "source_id": source_id,
        "source_type": source_type,
        "transcript": transcript_text,
        "articles_raw": articles_raw,
        "articles": articles,
    }


# ── Delete a whole source's content ──────────────────────
@app.delete("/api/videos/{source_id}")
def delete_video(source_id: str):
    deleted: list[str] = []
    source_title = None

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
                row_url = row.get("source_url") or row.get("video_url", "")
                if source_id in row_url:
                    source_title = row.get("source_title") or row.get("video_title")
                else:
                    remaining.append(row)

        if fieldnames and source_title:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(remaining)
            deleted.append(f"CSV rows removed from {csv_path.name}")

    # Try transcript files
    if not source_title and TRANSCRIPTS_DIR.exists():
        for tf in TRANSCRIPTS_DIR.glob("*.txt"):
            meta = _parse_transcript_header(tf)
            if source_id in str(meta.get("source_id", "")) or source_id in str(meta.get("video_id", "")):
                source_title = meta.get("title", tf.stem)
                break

    if not source_title:
        raise HTTPException(404, "Source not found")

    safe = sanitize_filename(source_title)

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

    return {"deleted": deleted, "source_title": source_title}


# ── Delete a single article ──────────────────────────────
@app.delete("/api/videos/{source_id}/articles/{article_title:path}")
def delete_article(source_id: str, article_title: str):
    source_title = None
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
                row_url = row.get("source_url") or row.get("video_url", "")
                match = source_id in row_url and title_col == article_title
                if match:
                    source_title = row.get("source_title") or row.get("video_title")
                else:
                    remaining.append(row)

        if source_title and fieldnames:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(remaining)
            deleted.append("CSV row removed")
            break

    if not source_title:
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
    for line in text.split("\n")[:10]:
        if line.startswith("Title:"):
            meta["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("Video ID:"):
            meta["video_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Source ID:"):
            meta["source_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Source Type:"):
            meta["source_type"] = line.split(":", 1)[1].strip()
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
