"""
AI Models — Calls PredictionGuard to generate Substack article drafts.
"""

import os
import re
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from predictionguard import PredictionGuard
except Exception:
    PredictionGuard = None


def initialize_predictionguard():
    api_key = os.environ.get("PREDICTIONGUARD_API_KEY")
    base_url = os.environ.get("PREDICTIONGUARD_URL")

    if not api_key or not base_url:
        raise RuntimeError(
            "Missing PredictionGuard config. Set PREDICTIONGUARD_API_KEY and PREDICTIONGUARD_URL in .env"
        )

    if not PredictionGuard:
        raise RuntimeError("predictionguard SDK not installed — run: pip install predictionguard")

    return PredictionGuard(url=base_url, api_key=api_key)


# ═══════════════════════════════════════════════════════════════
#  PROMPT — Generates Substack articles in the author's voice
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """You are a ghostwriter for a Substack newsletter called "Not So Quietly Disruptive."

ABOUT THE AUTHOR AND NEWSLETTER:
{channel_voice}

WRITING STYLE — Study these previous articles carefully and match the tone, rhythm, sentence length, and voice EXACTLY:
{style_reference}

YOUR TASK:
Watch/read the provided YouTube video transcript and write 2-3 complete Substack article drafts inspired by the ideas in the video. Each article should be something the author could publish directly on their Substack.

CRITICAL RULES:
1. Write in FIRST PERSON — as the author. Use "I", "me", "my" naturally.
2. Match the author's conversational, reflective, story-driven style. NOT corporate. NOT listicle. NOT generic AI writing.
3. Each article MUST have a UNIQUE, COMPELLING HEADLINE — the kind that makes someone stop scrolling and click.
   - GOOD: "Somewhere Over Kentucky I Learned You Can Vibe Code on a Plane"
   - GOOD: "The Internet Is Listening — And It's Not Forgetting"
   - BAD: "Article 1", "Innovation Ideas", "Key Takeaways"
4. Articles should be 400-700 words each.
5. Include personal reflection, insight, and a clear point that resonates with Christian leaders navigating technology.
6. End each article with a thought-provoking takeaway or call to reflection.

FORMAT — Use this EXACT structure (separate articles with ---):

**<Compelling Headline>**

<Full article body written in the author's voice. Multiple paragraphs. Personal, reflective, insightful.>

---

**<Next Compelling Headline>**

<Full article body...>

---

IMPORTANT: Do NOT include section headers like "Key Insight" or "Why it matters" — write naturally flowing articles like the style reference shows. These are essays, not structured reports.
"""

USER_PROMPT_TEMPLATE = """Write 2-3 Substack article drafts inspired by this video.

VIDEO TITLE: {video_title}

TRANSCRIPT:
{transcript}
"""


def generate_articles(
    client,
    transcript: str,
    video_title: str,
    style_reference: str,
    channel_voice: str,
    logger=None,
) -> List[Dict[str, str]]:
    """Call PredictionGuard to generate Substack article drafts."""

    def log(msg):
        if logger:
            logger.log(msg)
        print(msg)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        channel_voice=channel_voice,
        style_reference=style_reference[:6000],
    )

    user_message = USER_PROMPT_TEMPLATE.format(
        video_title=video_title,
        transcript=transcript[:15000],
    )

    try:
        log("📡 Calling PredictionGuard API...")
        response = client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_completion_tokens=8000,
        )

        log("✅ API response received")

        if not response:
            log("❌ Empty response from API")
            return []

        content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not content:
            log("❌ No content in API response")
            return []

        log(f"📝 Response length: {len(content):,} characters")
        log("🔍 Parsing articles from response...")

        articles = parse_articles(content)

        log(f"✨ Parsed {len(articles)} articles")

        if not articles:
            log("⚠️  Parsing returned 0 articles — saving raw response for debugging")
            Path("debug_pg_output.txt").write_text(content, encoding="utf-8")

        return articles

    except Exception as e:
        log(f"❌ Error calling PredictionGuard: {e}")
        import traceback
        traceback.print_exc()
        return []


# ═══════════════════════════════════════════════════════════════
#  PARSING — Splits raw AI response into article dicts
# ═══════════════════════════════════════════════════════════════

def parse_articles(content: str) -> List[Dict[str, str]]:
    """Parse AI response into a list of article dicts with title + body."""
    articles = []

    # Split on --- separator lines
    sections = re.split(r"\n-{3,}\n", content)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 80:
            continue

        # Extract title: **Title** or # Title
        title_match = re.search(r"^\*\*(.+?)\*\*", section, re.MULTILINE)
        if not title_match:
            title_match = re.search(r"^#\s+(.+?)$", section, re.MULTILINE)

        if not title_match:
            continue

        title = title_match.group(1).strip()
        body = section[title_match.end():].strip()

        # Skip if body is too short (probably not a real article)
        if len(body) < 100:
            continue

        articles.append({
            "title": title,
            "body": body,
        })

    return articles
