import os
import sys
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
        raise RuntimeError("Missing PredictionGuard configuration")

    if not PredictionGuard:
        raise RuntimeError("predictionguard SDK not installed")

    return PredictionGuard(url=base_url, api_key=api_key)


def generate_innovations_and_notes(client, transcript: str, video_title: str, style_reference: str, channel_voice: str, logger=None) -> List[Dict[str, str]]:
    """Call PredictionGuard client to generate innovations with detailed logging."""
    
    def log(msg):
        if logger:
            logger.log(msg)
        print(msg)
    
    system_prompt = f"""You are an expert innovation and technology writer focused on the intersection of faith and technology.

CHANNEL VOICE:
{channel_voice}

STYLE REFERENCE:
{style_reference[:4000]}
"""

    user_message = f"""Generate 3-4 innovations from this content transcript. For each innovation, also generate 2 Substack notes.

VIDEO TITLE: {video_title}

TRANSCRIPT:
{transcript[:15000]}
"""

    try:
        log("📡 Calling PredictionGuard API (gpt-oss-120b)...")
        response = client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_message}],
            temperature=0.7,
            max_completion_tokens=8000,
        )
        
        log("✅ API response received")
        
        if not response:
            log("❌ Empty response from API")
            return []
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        if not content:
            log("❌ No content in API response. Check API status.")
            return []
        
        log(f"📝 Response length: {len(content)} characters")
        log(f"🔍 Parsing innovations from response...")
        
        # Parse the response
        innovations = parse_innovations_and_notes(content)
        
        log(f"✨ Successfully parsed {len(innovations)} innovations")
        
        if not innovations:
            log("⚠️  Parsing returned 0 innovations. Response may not match expected format.")
            log("💾 Saving raw response to debug_pg_output.txt for inspection")
            debug_file = Path("debug_pg_output.txt")
            debug_file.write_text(content, encoding="utf-8")
        
        return innovations
        
    except Exception as e:
        log(f"❌ Error calling PredictionGuard: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def parse_innovations_and_notes(content: str):
    import re
    innovations = []
    sections = re.split(r'\n---+\n', content)

    i = 0
    while i < len(sections):
        section = sections[i].strip()
        if not section or len(section) < 50:
            i += 1
            continue

        title_match = re.search(r'^#\s+(.+?)$', section, re.MULTILINE) or re.search(r'^\*\*(.+?)\*\*', section, re.MULTILINE)
        if not title_match:
            i += 1
            continue

        title = title_match.group(1).strip()
        body_start = section.find(title_match.group(0)) + len(title_match.group(0))
        body = section[body_start:].strip()

        note1 = ""
        note2 = ""
        if i + 1 < len(sections):
            next_section = sections[i + 1].strip()
            if len(next_section) < 400 and "Key Insight:" not in next_section and "Think about it:" not in next_section:
                note1 = next_section
                i += 1
                if i + 1 < len(sections):
                    next_next = sections[i + 1].strip()
                    if len(next_next) < 400 and "Key Insight:" not in next_next and "Think about it:" not in next_next:
                        note2 = next_next
                        i += 1

        innovations.append({
            "title": title,
            "body": body,
            "substack_note_1": note1,
            "substack_note_2": note2,
        })

        i += 1

    return innovations


def parse_innovation_body(body: str):
    import re
    scripture_match = re.search(r'Key Insight:\s*(.+?)(?=\n\n)', body, re.IGNORECASE)
    scripture = scripture_match.group(1).strip() if scripture_match else ""

    reflection_match = re.search(r'\*\*Think about it:\*\*\s*(.+?)(?=\n\n\*\*Summary)', body, re.DOTALL | re.IGNORECASE)
    reflection = reflection_match.group(1).strip() if reflection_match else ""

    prayer_match = re.search(r'\*\*Summary:\*\*\s*(.+?)$', body, re.DOTALL | re.IGNORECASE)
    prayer = prayer_match.group(1).strip() if prayer_match else ""

    if scripture_match and reflection_match:
        start = scripture_match.end()
        end = reflection_match.start()
        main_text = body[start:end].strip()
    else:
        main_text = body

    return {
        "scripture": scripture,
        "main_text": main_text,
        "reflection": reflection,
        "prayer": prayer,
    }
