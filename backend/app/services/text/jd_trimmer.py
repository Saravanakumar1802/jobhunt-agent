"""Shrink job descriptions to the parts the LLM actually needs.

Keeps requirements / responsibilities / qualifications, drops benefits, EEO and
"about us" boilerplate. Typical JDs shrink 50-70%, which directly cuts tokens.
"""

import html
import re

KEEP = re.compile(
    r"requirement|qualification|responsibilit|skill|must have|nice to have|good to have|"
    r"what you('ll| will)|you (will|have|bring)|experience|about the role|role overview|tech stack|"
    r"key result|preferred|duties|job description|who you are",
    re.IGNORECASE,
)
DROP = re.compile(
    r"benefit|perk|equal opportunit|eeo|about (us|the company)|who we are|why (join|work)|"
    r"salary|compensation|what we offer|our (culture|values)|diversity|privacy|apply now|how to apply",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_BLOCK_TAG = re.compile(r"</?(p|div|li|ul|ol|br|h\d)[^>]*>", re.IGNORECASE)


def strip_html(text: str) -> str:
    text = _BLOCK_TAG.sub("\n", text or "")
    text = html.unescape(_TAG.sub(" ", text))
    lines = (re.sub(r"[ \t ]+", " ", ln).strip(" -•*\t") for ln in text.splitlines())
    return "\n".join(ln for ln in lines if ln)


def _is_heading(line: str) -> bool:
    return len(line) <= 70 and (line.endswith(":") or line.isupper() or len(line.split()) <= 6)


def trim_description(description: str, highlights: list[str] | None = None, max_chars: int = 4500) -> str:
    """Return the requirement-focused text, hard-capped at max_chars."""
    if highlights:
        # Providers like JSearch already split out qualifications/responsibilities.
        return "\n".join(f"- {h}" for h in highlights)[:max_chars]

    text = strip_html(description)
    lines = text.splitlines()
    kept: list[str] = []
    mode: bool | None = None  # None = no heading seen yet
    for line in lines:
        if _is_heading(line):
            if DROP.search(line):
                mode = False
                continue
            if KEEP.search(line):
                mode = True
                kept.append(line)
                continue
        if mode is not False:
            kept.append(line)

    result = "\n".join(kept) if kept else text
    return result[:max_chars]


YEARS_RE = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)


def extract_min_years(text: str) -> float | None:
    """Smallest 'N years' requirement mentioned, ignoring absurd values."""
    values = [int(m.group(1)) for m in YEARS_RE.finditer(text or "") if int(m.group(1)) <= 20]
    return float(min(values)) if values else None
