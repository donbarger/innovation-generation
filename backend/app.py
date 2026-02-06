from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uuid
import sys
import os
from pathlib import Path
import time
import json
from collections import deque
from core.generator import generate_for_video

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
INNOVATIONS_DIR = ROOT / "innovations"
TRANSCRIPTS_DIR = ROOT / "transcripts"

app = FastAPI(title="Innovation Generation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}
progress_queues = {}


class ProgressLogger:
    def __init__(self, job_id: str, max_messages: int = 100):
        self.job_id = job_id
        self.messages = deque(maxlen=max_messages)
    
    def log(self, msg: str):
        self.messages.append({"timestamp": time.time(), "message": msg})
    
    def get_messages(self):
        return list(self.messages)


class GenerateRequest(BaseModel):
    video_url: str


def run_generation(job_id: str, video_url: str, progress_logger: ProgressLogger):
    jobs[job_id]["status"] = "running"
    log_dir = ROOT / "backend_logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{job_id}.log"

    progress_logger.log(f"📋 Starting generation for: {video_url}")
    
    with log_file.open("w", encoding="utf-8") as lf:
        try:
            progress_logger.log("🎙️ Extracting video information...")
            lf.write(f"Starting generation for: {video_url}\n")
            
            # Pass progress logger to generator for detailed logging
            result = generate_for_video(video_url, output_dir=str(INNOVATIONS_DIR), logger=progress_logger)
            
            progress_logger.log(f"✅ Generated {result['count']} innovations!")
            progress_logger.log(f"📁 Saved to: {result['innovations_file']}")
            progress_logger.log("🎉 Generation complete!")
            lf.write(f"\nResult: {result}\n")
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result
        except Exception as e:
            error_msg = str(e)
            progress_logger.log(f"❌ Error: {error_msg}")
            lf.write(f"ERROR: {e}\n")
            import traceback
            traceback.print_exc(file=lf)
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = error_msg


@app.post("/api/generate")
def api_generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    video_url = req.video_url.strip()
    if not video_url:
        raise HTTPException(status_code=400, detail="video_url is required")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "video_url": video_url, "created": time.time()}
    progress_logger = ProgressLogger(job_id)
    progress_queues[job_id] = progress_logger

    thread = threading.Thread(target=run_generation, args=(job_id, video_url, progress_logger), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = progress_queues.get(job_id, {})
    if isinstance(progress, ProgressLogger):
        job["progress"] = progress.get_messages()
    
    return job


@app.get("/api/jobs")
def list_jobs():
    return jobs


@app.get("/api/transcripts")
def list_transcripts():
    transcripts = []
    if TRANSCRIPTS_DIR.exists():
        for f in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            transcripts.append({"file": f.name, "preview": text[:400]})
    return transcripts


@app.get("/api/innovations")
def list_innovations():
    items = []
    if INNOVATIONS_DIR.exists():
        for f in sorted(INNOVATIONS_DIR.glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            items.append({"file": f.name, "preview": text[:600]})
    return items


@app.get("/api/substack_notes")
def list_substack_notes():
    notes = []
    notes_dir = INNOVATIONS_DIR / "substack_notes"
    if notes_dir.exists():
        for f in sorted(notes_dir.glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            notes.append({"file": f.name, "content": text})
    return notes


@app.get("/api/all_transcripts")
def list_all_transcripts():
    """Get all transcripts as a simple list."""
    transcripts = []
    if TRANSCRIPTS_DIR.exists():
        for f in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            lines = text.split('\n')
            title = "Unknown"
            video_id = "unknown"
            
            # Parse title and video ID from file
            for line in lines[:5]:
                if line.startswith("Title:"):
                    title = line.replace("Title:", "").strip()
                if line.startswith("Video ID:"):
                    video_id = line.replace("Video ID:", "").strip()
            
            # Get preview (first 500 chars of actual content, skip header lines)
            content_start = text.find("\n\n")
            if content_start > 0:
                preview = text[content_start:].strip()[:400]
            else:
                preview = text[:400]
            
            transcripts.append({
                "file": f.name,
                "title": title,
                "video_id": video_id,
                "preview": preview,
                "full_content": text
            })
    return transcripts


@app.get("/api/videos")
def list_videos():
    """Get all videos with their innovations grouped together."""
    import re
    
    videos = {}
    master_csv = INNOVATIONS_DIR / "all_innovations.csv"
    
    # Read CSV to group by video
    if master_csv.exists():
        import csv
        with master_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                video_title = row.get("video_title", "Unknown")
                video_url = row.get("video_url", "")
                
                if video_title not in videos:
                    # Extract video ID from URL
                    video_id = None
                    if "v=" in video_url:
                        video_id = video_url.split("v=")[1].split("&")[0]
                    
                    videos[video_title] = {
                        "title": video_title,
                        "url": video_url,
                        "video_id": video_id or "unknown",
                        "transcript": None,
                        "innovations": []
                    }
                
                # Find corresponding transcript
                from core.utils import sanitize_filename
                safe_title = sanitize_filename(video_title)
                transcript_file = TRANSCRIPTS_DIR / f"{safe_title}.txt"
                if transcript_file.exists():
                    videos[video_title]["transcript"] = {
                        "file": transcript_file.name,
                        "path": str(transcript_file)
                    }
                
                # Find corresponding innovation file
                innovations_file = INNOVATIONS_DIR / f"{safe_title}.txt"
                if innovations_file.exists():
                    content = innovations_file.read_text(encoding="utf-8")
                    preview = content[:300] + "..." if len(content) > 300 else content
                    
                    videos[video_title]["innovations"].append({
                        "title": row.get("innovation_title", "Unknown"),
                        "file": innovations_file.name,
                        "preview": preview,
                        "key_insight": row.get("scripture", ""),
                        "reflection": row.get("reflection", ""),
                        "summary": row.get("prayer", "")
                    })
    
    return list(videos.values())


@app.get("/api/videos/{video_id}/innovations")
def get_video_innovations(video_id: str):
    """Get all innovations for a specific video."""
    from core.utils import sanitize_filename
    
    # Find video by ID or title
    master_csv = INNOVATIONS_DIR / "all_innovations.csv"
    innovations = []
    
    if master_csv.exists():
        import csv
        with master_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if video_id.lower() in row.get("video_url", "").lower():
                    safe_title = sanitize_filename(row.get("video_title", ""))
                    
                    # Get full innovation content
                    innovations_file = INNOVATIONS_DIR / f"{safe_title}.txt"
                    notes_dir = INNOVATIONS_DIR / "substack_notes"
                    
                    innovation = {
                        "title": row.get("innovation_title", ""),
                        "key_insight": row.get("scripture", ""),
                        "main_text": row.get("devotion", ""),
                        "reflection": row.get("reflection", ""),
                        "summary": row.get("prayer", ""),
                        "notes": []
                    }
                    
                    # Find corresponding note files
                    note_pattern = f"{safe_title} - {sanitize_filename(row.get('innovation_title', ''))}*.txt"
                    for note_file in notes_dir.glob(note_pattern):
                        notes_content = note_file.read_text(encoding="utf-8")
                        innovation["notes"].append({
                            "file": note_file.name,
                            "content": notes_content
                        })
                    
                    innovations.append(innovation)
    
    return innovations


@app.delete("/api/innovations/{innovation_id}")
def delete_innovation(innovation_id: str):
    """Delete an innovation and its associated notes from disk."""
    from pathlib import Path
    
    # innovation_id is filename without extension
    innovations_dir = INNOVATIONS_DIR
    notes_dir = innovations_dir / "substack_notes"
    
    deleted_files = []
    
    # Delete innovation file if it matches pattern
    for f in innovations_dir.glob("*.txt"):
        if f.name != "all_innovations.csv" and innovation_id.lower() in f.name.lower():
            try:
                f.unlink()
                deleted_files.append(f.name)
            except Exception as e:
                return {"error": f"Could not delete {f.name}: {e}"}
    
    # Delete associated note files
    for f in notes_dir.glob("*.txt"):
        if innovation_id.lower() in f.name.lower():
            try:
                f.unlink()
                deleted_files.append(f.name)
            except Exception as e:
                return {"error": f"Could not delete {f.name}: {e}"}
    
    return {"deleted": deleted_files}
