#!/usr/bin/env python3
"""
Generate Substack article drafts from an online article URL.

Usage:
    python generate_articles_from_url.py "https://example.com/article"
    python generate_articles_from_url.py "https://example.com/article" --output articles
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generator import generate_for_article, generate_for_source

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Generate Substack article drafts from an online article URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_articles_from_url.py "https://example.com/my-article"
  python generate_articles_from_url.py "https://medium.com/@author/article" --output my_articles
        """
    )
    
    parser.add_argument(
        "url",
        help="URL of the article to process"
    )
    
    parser.add_argument(
        "--output",
        default="articles",
        help="Output directory for generated articles (default: articles)"
    )
    
    parser.add_argument(
        "--style",
        default="presentation_transcript.txt",
        help="Path to style reference file (default: presentation_transcript.txt)"
    )
    
    parser.add_argument(
        "--type",
        choices=["article", "video", "auto"],
        default="auto",
        help="Source type: 'article' or 'video' (default: auto-detect)"
    )
    
    args = parser.parse_args()
    
    article_url = args.url.strip()
    if not article_url:
        print("❌ Article URL is required")
        return False
    
    try:
        print("\n" + "=" * 60)
        print("📰 Article to Substack Generator")
        print("=" * 60 + "\n")
        
        if args.type == "auto":
            result = generate_for_source(article_url, args.output, args.style)
        elif args.type == "article":
            result = generate_for_article(article_url, args.output, args.style)
        else:
            # video
            from core.generator import generate_for_video
            result = generate_for_video(article_url, args.output, args.style)
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS")
        print("=" * 60)
        print(f"Source: {result['source_title']}")
        print(f"Type: {result['source_type']}")
        print(f"Articles: {result['count']} generated")
        print(f"Output: {result['articles_file']}")
        print()
        
        return True
        
    except RuntimeError as e:
        print(f"\n❌ Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
