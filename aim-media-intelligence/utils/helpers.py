import re
import json
import logging

logger = logging.getLogger(__name__)

# Common filler words / spoken-word noise
FILLERS = re.compile(
    r'\b(um+|uh+|hmm+|mhm|ah+|oh+|er+|you know|i mean|like|basically|actually|'
    r'literally|obviously|right\?|okay so|so basically|kind of|sort of)\b',
    re.IGNORECASE
)
TIMESTAMP_RE = re.compile(r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?')
BRACKET_NOISE = re.compile(r'\[.*?\]|\(.*?\)')
MULTI_SPACE = re.compile(r'  +')
MULTI_NEWLINE = re.compile(r'\n{3,}')


def clean_transcript(raw: str) -> str:
    if not raw:
        return ""
    text = TIMESTAMP_RE.sub(' ', raw)
    text = BRACKET_NOISE.sub(' ', text)
    text = FILLERS.sub(' ', text)
    text = MULTI_SPACE.sub(' ', text)
    text = MULTI_NEWLINE.sub('\n\n', text)
    return text.strip()


def truncate_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return ' '.join(words[:max_words]) + ' [truncated]'


def safe_json_parse(text: str) -> dict | list | None:
    """Extract and parse JSON from LLM response that may contain markdown fences."""
    # strip markdown code blocks
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```', '', text)
    text = text.strip()

    # find first { or [
    start = next((i for i, c in enumerate(text) if c in '{['), None)
    end_char = '}' if (start is not None and text[start] == '{') else ']'
    if start is None:
        return None

    # find matching closing bracket
    depth = 0
    for i, c in enumerate(text[start:], start):
        if c in '{[':
            depth += 1
        elif c in '}]':
            depth -= 1
        if depth == 0:
            try:
                return json.loads(text[start:i + 1])
            except json.JSONDecodeError:
                break
    # fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse JSON from LLM response")
        return None


def parse_iso_duration(duration: str) -> int:
    """Return seconds from ISO 8601 duration string like PT1H3M20S."""
    import isodate
    try:
        return int(isodate.parse_duration(duration).total_seconds())
    except Exception:
        return 0


def word_count(text: str) -> int:
    return len(text.split()) if text else 0
