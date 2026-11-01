"""Deterministic skill normalisation and extraction — zero LLM tokens.

A taxonomy maps aliases to one canonical name ("ReactJS", "react.js" → "react"),
so matching is a set operation, and LLM output can be checked against the job text.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "data" / "skills_taxonomy.json"

# Composite skills imply their parts (a MERN developer knows MongoDB, Express, React, Node).
IMPLIES = {"mern": ["mongodb", "express", "react", "node.js", "javascript"], "next.js": ["react"]}


@lru_cache
def _taxonomy() -> dict[str, list[str]]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


@lru_cache
def _alias_map() -> dict[str, str]:
    mapping = {}
    for canonical, aliases in _taxonomy().items():
        mapping[canonical] = canonical
        for alias in aliases:
            mapping[alias.lower()] = canonical
    return mapping


def _alias_regex(alias: str) -> str:
    # Word boundaries that also respect symbols in names like c++, c#, node.js, ci/cd.
    return r"(?<![\w+#.])" + re.escape(alias) + r"(?![\w+#]|\.\w)"


@lru_cache
def _pattern() -> re.Pattern:
    # Longest aliases first so "react native" wins over "react".
    aliases = sorted(_alias_map(), key=len, reverse=True)
    return re.compile("|".join(_alias_regex(a) for a in aliases), re.IGNORECASE)


def known_skills() -> list[str]:
    return sorted(_taxonomy())


def canonical(skill: str) -> str:
    """Canonical name for a known skill, else the cleaned lower-case input."""
    cleaned = re.sub(r"\s+", " ", skill.strip().lower())
    return _alias_map().get(cleaned, cleaned)


def normalize_skills(skills: list[str]) -> list[str]:
    """Canonicalise, de-duplicate (order-preserving) and drop empties."""
    seen: dict[str, None] = {}
    for s in skills:
        c = canonical(s)
        if c and len(c) <= 40:
            seen.setdefault(c, None)
    return list(seen)


def expand_implied(skills: list[str] | set[str]) -> set[str]:
    out = set(skills)
    for s in list(out):
        out.update(IMPLIES.get(s, []))
    return out


def extract_skills(text: str) -> list[str]:
    """All known skills mentioned in free text, canonicalised, in first-seen order."""
    found: dict[str, None] = {}
    for m in _pattern().finditer(text or ""):
        found.setdefault(_alias_map()[m.group(0).lower()], None)
    return list(found)


NICE_RE = re.compile(r"nice[- ]to[- ]have|good[- ]to[- ]have|preferred|bonus|\bplus\b|desirable|optional", re.IGNORECASE)
HEADING_RE = re.compile(r"^[^.]{0,60}:\s*$")


def split_requirements(text: str) -> tuple[list[str], list[str]]:
    """(required, nice_to_have) skills, using 'nice to have / preferred / plus' cues per line or section."""
    required: dict[str, None] = {}
    nice: dict[str, None] = {}
    in_nice_section = False
    for line in (text or "").splitlines():
        if HEADING_RE.match(line.strip()):
            in_nice_section = bool(NICE_RE.search(line))
        target = nice if in_nice_section or NICE_RE.search(line) else required
        for s in extract_skills(line):
            target.setdefault(s, None)
    return list(required), [s for s in nice if s not in required]


def is_grounded(skill: str, text: str) -> bool:
    """True when the skill (or any alias of it) literally appears in the text.

    Used to drop skills an LLM invented that the job posting never mentions.
    """
    c = canonical(skill)
    if c in _taxonomy():
        return c in extract_skills(text)
    return re.search(_alias_regex(c), text or "", re.IGNORECASE) is not None
