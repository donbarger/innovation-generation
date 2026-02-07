import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import re
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from dotenv import load_dotenv

from .article_fetcher import fetch_article, validate_article_url

load_dotenv()


def read_assemblyai_config() -> Optional[str]:
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
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return None

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        lines = []
        for entry in transcript:
            text = entry.get("text", "").replace("\n", " ").strip()
            lines.append(text)
        return " ".join(lines).strip()
    except Exception:
        return None


def transcribe_audio_with_assemblyai(audio_path: Path, api_key: str) -> Optional[str]:
    try:
        import assemblyai as aai
        aai.settings.api_key = api_key
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(
            str(audio_path),
            config=aai.TranscriptionConfig(speech_models=["universal"])
        )

        if transcript.status == aai.TranscriptStatus.error:
            return None

        return transcript.text
    except Exception:
        return None


def download_and_transcribe_audio(video_id: str, assemblyai_key: str) -> Optional[str]:
    if not assemblyai_key:
        return None

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
                    return None

                text = transcribe_audio_with_assemblyai(audio_path, assemblyai_key)
                return text

            except DownloadError:
                return None
            except Exception:
                return None


def get_video_transcript(video_url: str) -> Optional[Tuple[str, str, str]]:
    video_id = None
    if "youtube.com/watch?v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]

    if not video_id:
        return None

    assemblyai_key = read_assemblyai_config()

    ydl_opts = {"quiet": True, "skip_download": True}

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title", f"Video_{video_id}")

            text = try_youtube_transcript(video_id)
            if text:
                return (video_id, title, text)

            if assemblyai_key:
                text = download_and_transcribe_audio(video_id, assemblyai_key)
                if text:
                    return (video_id, title, text)

            return None
    except Exception:
        return None


def get_article_content(article_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Fetch an article from a URL and extract its content.
    
    Returns:
        Tuple of (article_id, title, content) where article_id is based on the URL
    """
    if not validate_article_url(article_url):
        return None
    
    result = fetch_article(article_url)
    if not result:
        return None
    
    url, title, content = result
    
    # Generate article_id from URL (remove protocol and special chars)
    article_id = re.sub(r'[^a-zA-Z0-9-]', '-', url.replace('https://', '').replace('http://', ''))
    article_id = re.sub(r'-+', '-', article_id)[:50]
    
    return (article_id, title, content)


def get_source_content(source_url: str) -> Optional[Tuple[str, str, str]]:
    """
    Automatically detect if source is a YouTube video or article URL and fetch content.
    
    Returns:
        Tuple of (source_id, title, content)
    """
    if not source_url or not isinstance(source_url, str):
        return None
    
    source_url = source_url.strip()
    
    # Check if it's a YouTube URL
    if "youtube.com" in source_url or "youtu.be" in source_url:
        return get_video_transcript(source_url)
    
    # Otherwise treat as article URL
    return get_article_content(source_url)
