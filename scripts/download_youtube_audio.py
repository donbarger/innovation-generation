#!/usr/bin/env python3
"""
Simple script to download audio from a YouTube video.

Usage:
    python download_youtube_audio.py "https://youtube.com/watch?v=VIDEO_ID"
    python download_youtube_audio.py "https://youtube.com/watch?v=VIDEO_ID" --output my_audio.m4a
"""

import argparse
import sys
from pathlib import Path
from yt_dlp import YoutubeDL


def sanitize_filename(filename: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()


def download_audio(video_url: str, output_path: str = None) -> bool:
    """
    Download audio from a YouTube video.
    
    Args:
        video_url: YouTube video URL
        output_path: Optional output filename. If not provided, uses video title.
    
    Returns:
        True if successful, False otherwise
    """
    
    try:
        # First, get video info to get the title
        print("📋 Fetching video info...")
        info_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        
        with YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_title = info.get("title", "audio")
            video_id = info.get("id", "unknown")
        
        print(f"🎥 Video: {video_title}")
        print(f"🆔 ID: {video_id}")
        
        # Determine output filename
        if output_path:
            output_file = Path(output_path)
        else:
            safe_title = sanitize_filename(video_title)
            output_file = Path(f"{safe_title}.m4a")
        
        # Download audio
        print(f"📥 Downloading audio...")
        
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }],
            "outtmpl": str(output_file.with_suffix("")),  # yt-dlp will add extension
            "quiet": False,
            "no_warnings": False,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        print(f"\n✅ Audio downloaded successfully!")
        print(f"📁 Saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error downloading audio: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download audio from a YouTube video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_youtube_audio.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
  python download_youtube_audio.py "https://youtube.com/watch?v=dQw4w9WgXcQ" --output my_song.m4a
        """
    )
    
    parser.add_argument(
        "url",
        help="YouTube video URL"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output filename (default: uses video title)"
    )
    
    args = parser.parse_args()
    
    # Validate URL
    if "youtube.com" not in args.url and "youtu.be" not in args.url:
        print("❌ Invalid YouTube URL")
        return 1
    
    # Download
    success = download_audio(args.url, args.output)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

