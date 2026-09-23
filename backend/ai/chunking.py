from typing import List, Optional

MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP = 100
MAX_CHUNKS = 10
PROFILE_HEAD_CHARS = 600
JOB_TEXT_CHARS = 1000


def build_profile_text(skills: Optional[List[str]], experience_years: Optional[float], text: Optional[str]) -> str:
    """First chunk of every resume. all-MiniLM-L6-v2 silently truncates past
    ~256 tokens, so the highest-signal facts (skills, experience) go first and
    the rest of the budget is the top of the resume."""
    parts = []
    if skills:
        parts.append(f"Skills: {', '.join(skills)}.")
    if experience_years is not None:
        parts.append(f"{experience_years} years of experience.")
    if text:
        parts.append(" ".join(text.split())[:PROFILE_HEAD_CHARS])
    return " ".join(parts)


def build_job_text(description: Optional[str], required_skills: Optional[List[str]]) -> str:
    parts = []
    if required_skills:
        parts.append(f"Required skills: {', '.join(required_skills)}.")
    if description:
        parts.append(" ".join(description.split())[:JOB_TEXT_CHARS])
    return " ".join(parts)


def _split_long(line: str) -> List[str]:
    if len(line) <= MAX_CHUNK_CHARS:
        return [line]
    pieces, current = [], ""
    for sentence in line.replace("; ", ". ").split(". "):
        if len(current) + len(sentence) + 2 > MAX_CHUNK_CHARS and current:
            pieces.append(current)
            current = ""
        while len(sentence) > MAX_CHUNK_CHARS:
            pieces.append(sentence[:MAX_CHUNK_CHARS])
            sentence = sentence[MAX_CHUNK_CHARS:]
        current = f"{current}. {sentence}" if current else sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_resume(skills: Optional[List[str]], experience_years: Optional[float], text: Optional[str]) -> List[str]:
    """Chunk 0 is the profile summary. The rest is the resume body packed into
    ~800 character windows (about 200 tokens, inside the model's limit) with a
    small overlap so a sentence cut at a boundary still appears whole once."""
    chunks = [build_profile_text(skills, experience_years, text)]
    body = (text or "").strip()
    if body:
        units: List[str] = []
        for line in body.split("\n"):
            line = line.strip()
            if line:
                units.extend(_split_long(line))
        current = ""
        for unit in units:
            if current and len(current) + len(unit) + 1 > MAX_CHUNK_CHARS:
                chunks.append(current)
                tail = current[-CHUNK_OVERLAP:] if CHUNK_OVERLAP else ""
                if " " in tail:
                    tail = tail[tail.index(" ") + 1:]
                current = f"{tail} {unit}".strip() if tail else unit
            else:
                current = f"{current}\n{unit}" if current else unit
            if len(chunks) >= MAX_CHUNKS:
                break
        if current and len(chunks) < MAX_CHUNKS:
            chunks.append(current)
    return [c for c in chunks if c and c.strip()][:MAX_CHUNKS]
