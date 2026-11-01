"""Prompts. Static instructions come first, variable data last (provider prompt-cache friendly).

Every prompt forbids inventing facts and asks for short, schema-bound JSON.
"""

ANALYZER_SYSTEM = """You extract hiring requirements from job postings.
Rules:
- Use ONLY skills explicitly written in each posting. Never infer or invent.
- Skills are short lowercase names (e.g. "react", "python", "mongodb", "rest api").
- required_skills = must-haves; nice_to_have = preferred/bonus.
- min_years = minimum years of experience stated, or null.
- seniority: one of intern, junior, mid, senior, lead, unknown.
- summary: max 20 words.
Return JSON: {"jobs":[{"id":str,"required_skills":[str],"nice_to_have":[str],"min_years":number|null,"seniority":str,"summary":str}]}
Return one entry per job id given, no other text."""


def analyzer_user(jobs: list[tuple[str, str, str]]) -> str:
    """jobs: [(id, title, trimmed_text)]"""
    parts = [f"### id: {jid}\ntitle: {title}\n{text}" for jid, title, text in jobs]
    return "Postings:\n\n" + "\n\n".join(parts)


MATCHER_SYSTEM = """You review how well a candidate fits jobs. Skill overlap is ALREADY computed by code and
is correct — do not recompute it or add skills. Judge only what code cannot: domain fit, seniority fit,
and whether the missing skills are critical.
For each job return:
- fit_adjustment: integer from -15 to 15 applied to the code score (0 if the code score is fair)
- seniority_fit: one of under, good, over
- reasoning: max 30 words, mention only facts from the input
Return JSON: {"jobs":[{"id":str,"fit_adjustment":int,"seniority_fit":str,"reasoning":str}]}"""


def matcher_user(profile: dict, items: list[dict]) -> str:
    lines = [
        f"Candidate role: {profile['target_role']}",
        f"Candidate years: {profile.get('years_experience') or 'not stated'}",
        f"Candidate summary: {(profile.get('description') or '')[:400]}",
        "",
    ]
    for it in items:
        lines.append(
            f"### id: {it['id']}\ntitle: {it['title']}\nseniority: {it['seniority']} (min years: {it['min_years']})\n"
            f"code_score: {it['base_score']}\nmatched: {', '.join(it['matched']) or 'none'}\n"
            f"missing_required: {', '.join(it['missing']) or 'none'}\nsummary: {it['summary']}"
        )
    return "\n".join(lines)


OUTREACH_SYSTEM = """You write outreach drafts a job seeker sends manually to a recruiter/HR.
Rules:
- Mention ONLY skills listed under "matched skills" and facts given in the input. Never invent
  experience, numbers, employers or achievements.
- No placeholders like [Name] except "Hi there" style greetings; keep it ready to send.
- Do not claim to have applied unless told so.
Return JSON: {"subject": str, "body": str}"""

TONE_GUIDE = {
    "short": "Short and direct: 50-70 words, 3-4 sentences, LinkedIn connection-note style.",
    "friendly": "Warm and conversational: 90-130 words.",
    "formal": "Professional and formal: 120-160 words, email style.",
}
KIND_GUIDE = {
    "message": "Write a recruiter outreach message.",
    "cover_letter": "Write a concise cover letter (180-250 words, 3 short paragraphs). Subject = 'Application for <title>'.",
    "bullets": "Write 4-6 resume bullet points tailored to this job, one per line starting with '• '. "
               "Base them only on the candidate's matched skills and summary. Subject = 'Resume bullets'.",
}


def outreach_user(*, kind: str, tone: str, job: dict, profile: dict, matched: list[str], missing: list[str]) -> str:
    return (
        f"Task: {KIND_GUIDE[kind]}\nTone: {TONE_GUIDE[tone]}\n\n"
        f"Job title: {job['title']}\nCompany: {job['company']}\nLocation: {job.get('location', '')}\n"
        f"Job summary: {job.get('summary', '')}\n\n"
        f"Candidate name: {profile.get('name', '')}\nTarget role: {profile['target_role']}\n"
        f"Candidate years: {profile.get('years_experience') or 'not stated'}\n"
        f"Candidate summary: {(profile.get('description') or '')[:500]}\n"
        f"Matched skills: {', '.join(matched) or 'none'}\n"
        f"Skills still learning (do not claim): {', '.join(missing) or 'none'}"
    )
