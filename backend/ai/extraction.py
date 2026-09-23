import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.config import NAME_CONFIDENCE_THRESHOLD, NER_ENABLED, OCR_ENABLED
from .skills_extractor import SkillsExtractor

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"

_NAME_STOP_WORDS = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary", "objective", "experience",
    "education", "skills", "contact", "phone", "email", "address", "linkedin", "github",
    "portfolio", "page", "professional", "personal", "details", "information", "references",
    "available", "upon", "request",
}
_ROLE_WORDS = {
    "engineer", "developer", "manager", "student", "intern", "analyst", "designer",
    "consultant", "scientist", "architect", "specialist", "fresher", "graduate", "lead",
    "programmer", "administrator",
}

_EDU_LINE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|bachelor|master|b\.?sc|m\.?sc|b\.?e\b|mba|bca|mca|university|college|school|"
    r"institute|cgpa|gpa|degree|diploma|percentage|class\s+x|12th|10th|senior secondary|higher secondary)",
    re.IGNORECASE,
)
_SECTION_START = re.compile(
    r"^\s*(work\s+experience|professional\s+experience|employment(?:\s+history)?|experience|work\s+history|internships?)\s*:?\s*$",
    re.IGNORECASE,
)
_SECTION_END = re.compile(
    r"^\s*(education|academic(?:s|\s+background)?|projects?|skills|technical\s+skills|certifications?|achievements?|"
    r"awards?|publications?|extracurriculars?|interests|languages|references)\s*:?\s*$",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ text

def extract_text_from_pdf(file_path: str) -> Tuple[Optional[str], bool]:
    """Returns (text, used_ocr). Text PDFs go through pdfplumber; if that yields
    almost nothing the file is probably scanned, so try OCR when it is installed."""
    import pdfplumber

    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if page_text:
                    text += f"\n{page_text}"
    except Exception:
        text = ""

    used_ocr = False
    if len(text.strip()) < 80 and OCR_ENABLED:
        ocr_text = _ocr_pdf(file_path)
        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
            text, used_ocr = ocr_text, True

    if not text.strip():
        return None, used_ocr
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[•●◆▪►]", "-", text)
    return text.strip(), used_ocr


def _ocr_pdf(file_path: str, max_pages: int = 4) -> Optional[str]:
    try:
        import pdfplumber
        import pytesseract
    except Exception:
        return None
    try:
        parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:max_pages]:
                image = page.to_image(resolution=200).original
                parts.append(pytesseract.image_to_string(image))
        return "\n".join(parts)
    except Exception:
        return None


# ------------------------------------------------------------------ contact details

def extract_email(text: str) -> Optional[str]:
    match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return match.group(0).lower().rstrip(".") if match else None


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Digits only, keeping a leading +. Returns None if it doesn't look like a phone number."""
    if not raw:
        return None
    raw = raw.strip()
    digits = re.sub(r"\D", "", raw)
    if not 10 <= len(digits) <= 15:
        return None
    return ("+" if raw.startswith("+") else "") + digits


_PHONE_PATTERNS = [
    r"(?<!\d)(?:\+91[\s\-.]?|0)?[6-9]\d{4}[\s\-.]?\d{5}(?!\d)",
    r"(?<!\d)(?:\+91[\s\-.]?)?\d{4}[\s\-.]\d{6}(?!\d)",
    r"(?<!\d)(?:\+?1[\s\-.]?)?\(?[2-9]\d{2}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}(?!\d)",
]


def extract_phone(text: str) -> Optional[str]:
    for pattern in _PHONE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            normalized = normalize_phone(match.group(0))
            if normalized:
                return normalized
    return None


# ------------------------------------------------------------------ name

def _tidy_case(name: str) -> str:
    return name.title() if name.isupper() else name


def _email_tokens(email: Optional[str]) -> set:
    if not email:
        return set()
    local = email.split("@")[0]
    return {t for t in re.split(r"[^a-z]+", local.lower()) if len(t) >= 3}


def _score_name_line(line: str, position: int, email_tokens: set) -> float:
    words = line.split()
    if not 1 < len(words) <= 4:
        return 0.0
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words):
        return 0.0
    lowered = {w.lower().strip(".") for w in words}
    if lowered & _NAME_STOP_WORDS or lowered & _ROLE_WORDS:
        return 0.0
    if not all(w[0].isupper() for w in words):
        return 0.0
    score = 0.55
    if position == 0:
        score += 0.15
    if len(words) in (2, 3):
        score += 0.1
    if email_tokens and any(tok in line.lower().replace(" ", "") for tok in email_tokens):
        score += 0.2
    return min(score, 0.98)


def _ner_person(text: str) -> Optional[str]:
    if not NER_ENABLED:
        return None
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except Exception:
        return None
    try:
        doc = nlp(text[:600])
        for ent in doc.ents:
            if ent.label_ == "PERSON" and 2 <= len(ent.text.split()) <= 4 and "@" not in ent.text:
                return ent.text.strip()
    except Exception:
        return None
    return None


def extract_name(text: str, email: Optional[str] = None) -> Tuple[Optional[str], float, str]:
    """Returns (name, confidence 0-1, method). Heuristics first; the NER model is
    only consulted when the heuristic result is weak."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    tokens = _email_tokens(email)

    best_name, best_score = None, 0.0
    for i, line in enumerate(lines[:8]):
        if "@" in line or "http" in line.lower() or re.search(r"\d{4,}", line):
            continue
        score = _score_name_line(line, i, tokens)
        if score > best_score:
            best_name, best_score = line, score

    method = "heuristic"
    if best_score < NAME_CONFIDENCE_THRESHOLD:
        ner_name = _ner_person(text)
        if ner_name:
            best_name, best_score, method = ner_name, max(best_score, 0.7), "ner"

    if best_name is None and email:
        local = re.sub(r"\d+", "", re.sub(r"[._]", " ", email.split("@")[0])).strip().title()
        if len(local) > 2:
            return local, 0.35, "email"
    if best_name is None:
        return None, 0.0, "none"
    return _tidy_case(best_name), round(best_score, 2), method


# ------------------------------------------------------------------ experience

def _experience_section(text: str) -> Optional[str]:
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if _SECTION_START.match(line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if _SECTION_END.match(lines[j]):
            end = j
            break
    section = "\n".join(lines[start:end])
    return section if section.strip() else None


_RANGE = re.compile(
    rf"(?:{_MONTH_RE}[\s,]*)?((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*"
    rf"(?:(?:{_MONTH_RE}[\s,]*)?((?:19|20)\d{{2}})|(present|current|now|ongoing|till\s+date|to\s+date))",
    re.IGNORECASE,
)
_NUMERIC_RANGE = re.compile(
    r"(\d{1,2})[/.]((?:19|20)\d{2})\s*(?:-|–|—|to)\s*(?:(\d{1,2})[/.]((?:19|20)\d{2})|(present|current|now|ongoing))",
    re.IGNORECASE,
)


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _date_intervals(text: str, now: Optional[datetime] = None) -> List[Tuple[int, int]]:
    now = now or datetime.now()
    now_idx = _month_index(now.year, now.month)
    intervals: List[Tuple[int, int]] = []

    def add(start_idx: int, end_idx: int, year_only: bool):
        end_idx = min(end_idx, now_idx)
        if year_only and end_idx - start_idx < 6:
            end_idx = start_idx + 6
        if end_idx < start_idx or start_idx > now_idx:
            return
        if (end_idx - start_idx) / 12 > 45:
            return
        intervals.append((start_idx, end_idx))

    for m in _RANGE.finditer(text):
        start_month_name, start_year, end_month_name, end_year, present = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        start_month = _MONTHS[start_month_name[:3].lower()] if start_month_name else 1
        start_idx = _month_index(int(start_year), start_month)
        if present:
            end_idx = now_idx
            year_only = start_month_name is None
        else:
            end_month = _MONTHS[end_month_name[:3].lower()] if end_month_name else 1
            end_idx = _month_index(int(end_year), end_month)
            year_only = start_month_name is None or end_month_name is None
        add(start_idx, end_idx, year_only)

    for m in _NUMERIC_RANGE.finditer(text):
        sm, sy, em, ey, present = m.groups()
        if not 1 <= int(sm) <= 12:
            continue
        start_idx = _month_index(int(sy), int(sm))
        if present:
            end_idx = now_idx
        else:
            if not 1 <= int(em) <= 12:
                continue
            end_idx = _month_index(int(ey), int(em))
        add(start_idx, end_idx, False)
    return intervals


def merged_months(intervals: List[Tuple[int, int]]) -> int:
    """Union of the date ranges, so overlapping jobs are only counted once."""
    if not intervals:
        return 0
    ordered = sorted(intervals)
    total = 0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return total


_STATED_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?(?:work\s+)?experience",
    r"(\d+(?:\.\d+)?)\s*\+?\s*yrs?\s+(?:of\s+)?(?:professional\s+)?experience",
    r"total\s+(?:work\s+)?experience\s*:?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?",
    r"experience\s*:?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?",
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:in\s+)?(?:software|development|engineering|it|programming)",
    r"over\s+(\d+)\s+years?",
    r"more\s+than\s+(\d+)\s+years?",
]
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def extract_experience(text: str, now: Optional[datetime] = None) -> Tuple[Optional[float], str]:
    """Returns (years, source) where source is 'stated', 'computed' or 'none'.
    A number the candidate states outright wins; otherwise years are computed
    from the date ranges in the experience section (overlaps merged, education
    dates excluded)."""
    if not text:
        return None, "none"
    lower = text.lower()

    for pattern in _STATED_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            try:
                years = float(match.group(1))
            except ValueError:
                continue
            if 0 < years <= 50:
                return years, "stated"
    for word, num in _WORD_NUMBERS.items():
        if re.search(rf"{word}\s+years?\s+(?:of\s+)?experience", lower):
            return float(num), "stated"

    section = _experience_section(text)
    if section is not None:
        scope = section
    else:
        scope = "\n".join(l for l in text.split("\n") if not _EDU_LINE.search(l))
    months = merged_months(_date_intervals(scope, now))
    if months > 0:
        return round(months / 12, 1), "computed"
    return None, "none"


# ------------------------------------------------------------------ education

_DEGREE_PATTERNS = [
    (r"\bPh\.?\s?D\b|\bDoctorate\b", "PhD", re.IGNORECASE),
    (r"\bMBA\b", "MBA", 0),
    (r"\bM\.?\s?Tech\b", "M.Tech", re.IGNORECASE),
    (r"\bM\.?Sc\.?\b|\bM\.S\.|\bMaster(?:'?s)?\s+(?:of|in|degree)\b", "Master's", re.IGNORECASE),
    (r"\bMCA\b", "MCA", 0),
    (r"\bB\.?\s?Tech\b", "B.Tech", re.IGNORECASE),
    (r"\bB\.E\.?(?=[\s,.(]|$)|\bBE\s+(?:in|\()", "B.E.", 0),
    (r"\bB\.?Sc\.?\b|\bBachelor(?:'?s)?\b", "Bachelor's", re.IGNORECASE),
    (r"\bBCA\b", "BCA", 0),
    (r"\bBBA\b", "BBA", 0),
    (r"\bB\.?\s?Com\b", "B.Com", re.IGNORECASE),
    (r"\bAssociate(?:'?s)?\s+degree\b", "Associate's", re.IGNORECASE),
    (r"\bDiploma\b", "Diploma", re.IGNORECASE),
    (r"\bHigh\s+School\b|\b12th\b", "High School", re.IGNORECASE),
]


def extract_education(text: str) -> List[Dict]:
    if not text:
        return []
    found = []
    for pattern, label, flags in _DEGREE_PATTERNS:
        if re.search(pattern, text, flags):
            found.append({"degree": label})
    return found


# ------------------------------------------------------------------ orchestration

def parse_resume(text: str, used_ocr: bool = False) -> Dict:
    email = extract_email(text)
    name, name_conf, name_method = extract_name(text, email)
    years, years_source = extract_experience(text)
    extractor = SkillsExtractor()
    skills = extractor.extract(text)
    meta = {
        "name_method": name_method,
        "email_confidence": 0.99 if email else 0.0,
        "experience_source": years_source,
        "used_ocr": used_ocr,
        "unrecognised_skills": extractor.unrecognised_from_skills_section(text),
    }
    needs_review = name_conf < NAME_CONFIDENCE_THRESHOLD or email is None
    meta["needs_review"] = needs_review
    return {
        "name": name,
        "candidate_name": name,
        "name_confidence": name_conf,
        "email": email,
        "phone": extract_phone(text),
        "skills": skills,
        "experience_years": years,
        "education": extract_education(text),
        "extraction_meta": meta,
    }
