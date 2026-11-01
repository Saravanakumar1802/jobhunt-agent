"""Hard guarantee that only free-tier models are ever called.

Rules (verified Oct 2026, no card on any of these):
- groq/*        — the whole Groq free plan is free; non-chat models excluded
- gemini/*      — Flash / Flash-Lite / Gemma only (Pro is billing-only)
- openrouter/*  — only ids ending in ":free"
Everything else is rejected, so a typo or a paid model id can never slip in.
"""

NON_CHAT = ("whisper", "tts", "guard", "playai", "orpheus", "embedding", "image", "audio", "live", "veo", "imagen")
PROVIDERS = ("groq", "gemini", "openrouter")


def provider_of(model: str) -> str:
    return model.split("/", 1)[0] if "/" in model else ""


def check_free(model: str) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    provider, _, name = model.partition("/")
    lname = name.lower()
    if provider not in PROVIDERS or not name:
        return False, f"Provider must be one of {', '.join(PROVIDERS)} (prefix like 'groq/…')"
    if any(k in lname for k in NON_CHAT):
        return False, "Not a chat/text model"
    if provider == "gemini":
        if "pro" in lname.split("-") or "-pro" in lname:
            return False, "Gemini Pro models require billing — use Flash or Flash-Lite"
        if "flash" not in lname and "gemma" not in lname:
            return False, "Only Gemini Flash / Flash-Lite / Gemma are on the free tier"
    if provider == "openrouter" and not lname.endswith(":free"):
        return False, "OpenRouter models must end in ':free'"
    return True, "free tier"


def is_free(model: str) -> bool:
    return check_free(model)[0]
