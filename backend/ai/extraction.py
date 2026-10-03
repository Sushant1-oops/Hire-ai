import re
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from core.config import MAX_PDF_PAGES, NAME_CONFIDENCE_THRESHOLD, NER_ENABLED, OCR_ENABLED
from ai.skills_extractor import SkillsExtractor

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# Matches "2022", "'22" or "22" right after a month token — the short forms are
# only accepted immediately after a month name so a bare "22" elsewhere in the
# text (an age, a percentage) is never mistaken for a year.
_YEAR_RE = r"(?:(?:19|20)\d{2}|'\d{2})"

_NAME_STOP_WORDS = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary", "objective", "experience",
    "education", "skills", "contact", "phone", "email", "address", "linkedin", "github",
    "portfolio", "page", "professional", "personal", "details", "information", "references",
    "available", "upon", "request", "mobile", "dob", "gender", "nationality", "location",
}
_ROLE_WORDS = {
    "engineer", "developer", "manager", "student", "intern", "analyst", "designer",
    "consultant", "scientist", "architect", "specialist", "fresher", "graduate", "lead",
    "programmer", "administrator", "founder", "freelancer", "trainee",
}
_CONTACT_TOKEN = re.compile(
    r"@|https?://|www\.|linkedin\.com|github\.com|\+?\d[\d\-\s()]{6,}\d|"
    r"\b(?:faridabad|delhi|gurugram|gurgaon|noida|mumbai|bangalore|bengaluru|pune|hyderabad|chennai|kolkata|india)\b",
    re.IGNORECASE,
)

_EDU_LINE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|bachelor|master|b\.?sc|m\.?sc|b\.?e\b|mba|bca|mca|university|college|school|"
    r"institute|cgpa|gpa|degree|diploma|percentage|class\s+x|12th|10th|senior secondary|higher secondary)",
    re.IGNORECASE,
)
_FRESHER_RE = re.compile(
    r"\b(?:fresher|no\s+(?:prior\s+)?(?:work\s+)?experience|recent\s+graduate|entry[\s-]level)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ section segmentation
#
# Resumes mix dates and keywords across very different sections (a degree's
# "2023-2027", a project's tech list, an "eager to learn Go" aside). Instead of
# guessing line-by-line which of those belong to "experience" or "skills",
# split the whole resume into labelled sections once and read each field only
# from the sections where it actually belongs. This is what fixes a student's
# degree years ("Delhi Technical Campus ... (2023-2027)") from being counted
# as 3+ years of work experience: it lives in the education section, which
# experience computation never looks at unless there is no experience section
# at all (see extract_experience).

_SECTION_HEADERS = {
    "experience": r"work\s+experience|professional\s+experience|employment(?:\s+history)?|experience|"
                  r"work\s+history|internships?|career\s+(?:history|summary)|relevant\s+experience",
    "education": r"education|academic(?:s|\s+background)?|academic\s+qualifications?",
    "skills": r"skills(?:\s*(?:&|and)\s*(?:tools|interests))?|technical\s+skills|key\s+skills|core\s+skills|"
              r"core\s+competencies|technologies|tools?(?:\s*(?:&|and)\s*technologies)?|skill\s*set|"
              r"areas\s+of\s+expertise",
    "projects": r"projects?|academic\s+projects?|personal\s+projects?|key\s+projects?|open[\s-]source(?:\s+projects?)?",
    "objective": r"objective|summary|professional\s+summary|profile|profile\s+summary|about\s+me|career\s+objective",
    "certifications": r"certifications?|certificates?|licenses?",
    "achievements": r"achievements?|awards?|honou?rs?|accomplishments?",
    "publications": r"publications?",
    "other": r"extracurriculars?|interests|hobbies|languages|references|declaration|volunteer(?:ing)?|activities|"
             r"additional\s+information|other\s+information",
}
_SECTION_HEADER_RE = {
    label: re.compile(rf"^\s*(?:{pattern})\s*:?\s*$", re.IGNORECASE)
    for label, pattern in _SECTION_HEADERS.items()
}


def _segment_text(text: str) -> Dict[str, str]:
    """Splits a resume into {section_label: joined_line_text}, keyed by the
    canonical labels in _SECTION_HEADERS plus "preamble" for everything before
    the first recognised header (name, contact line, headline)."""
    buckets: Dict[str, List[str]] = {"preamble": []}
    current = "preamble"
    for line in text.split("\n"):
        matched = None
        for label, pattern in _SECTION_HEADER_RE.items():
            if pattern.match(line):
                matched = label
                break
        if matched:
            current = matched
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)
    return {label: "\n".join(lines) for label, lines in buckets.items()}


_ASPIRATIONAL_RE = re.compile(
    r"\((?:comfortable\s+)?pick(?:ing)?\s+up\s+(?:new\s+)?(?:languages?|skills?|technologies?|frameworks?)"
    r"\s+such\s+as\s+[^)]*\)"
    r"|\b(?:eager|willing|happy|hoping|planning|interested)\s+to\s+learn\s+[^.;\n)]*"
    r"|\bwant(?:s|ing)?\s+to\s+learn\s+[^.;\n)]*"
    r"|\b(?:looking\s+forward\s+to|plan\s+to)\s+(?:learn(?:ing)?|pick(?:ing)?\s+up)\s+[^.;\n)]*",
    re.IGNORECASE,
)


def _strip_aspirational(text: str) -> str:
    """Drops clauses that name a technology the candidate does NOT yet have —
    "comfortable picking up new languages such as Go or Scala", "eager to learn
    Kubernetes" — so they are not extracted as if they were current skills."""
    return _ASPIRATIONAL_RE.sub(" ", text)



# ------------------------------------------------------------------ text

def extract_text_from_pdf(file_path: str) -> Tuple[Optional[str], bool]:
    """Returns (text, used_ocr). Text PDFs go through pdfplumber; if that yields
    almost nothing the file is probably scanned, so try OCR when it is installed."""
    import pdfplumber

    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:MAX_PDF_PAGES]:
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
    # Resumes that use icon fonts for contact-detail bullets (a phone/email/
    # LinkedIn glyph) sometimes hit a font pdfplumber can't map to a real
    # character; it falls back to emitting the raw glyph id as literal text
    # like "(cid:239)". These carry no information and would otherwise sit
    # right in the middle of the contact line, so drop them before anything
    # else runs.
    text = re.sub(r"\(cid:\d+\)", " ", text)
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

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+")
_COMMON_TLDS = ("com", "org", "net", "edu", "gov", "io", "co", "in", "ai", "dev", "me", "uk", "us", "info", "biz", "tech", "app")
# PDF text extraction often glues the next word onto an address when the two sit
# in different columns: "jane@mail.comLinkedIn". If a known TLD is directly
# followed by a capital letter, the capital starts the next word.
_GLUED_TLD = re.compile(r"^(.+?\.(?:" + "|".join(_COMMON_TLDS) + r"))(?=[A-Z])")


def extract_email(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text or "")
    if not match:
        return None
    address = match.group(0).rstrip(".-")
    glued = _GLUED_TLD.match(address)
    if glued:
        address = glued.group(1)
    return address.lower()


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


def _name_candidates_from_line(line: str) -> List[str]:
    """A line that mixes the name with contact details ("Sushant Thakur |
    Faridabad | +91-9310738102 | mail@x.com", "Jane Doe - Backend Engineer")
    is common, so the name is usually only the first segment. Try the whole
    line first, then each segment split on a separator, longest first."""
    candidates = [line]
    segments = re.split(r"\s*[|•·│]\s*|\s{2,}|\t+|\s+-\s+|\s*,\s*", line)
    candidates.extend(s for s in segments if s and s != line)
    seen, out = set(), []
    for c in candidates:
        c = c.strip(" .")
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


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


@lru_cache(maxsize=1)
def _load_ner():
    """The spaCy model takes ~1s to load, so it is loaded once per process (a
    failed load is cached as None too, instead of retrying for every resume)."""
    try:
        import spacy
        return spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except Exception:
        return None


def _ner_person(text: str) -> Optional[str]:
    if not NER_ENABLED:
        return None
    nlp = _load_ner()
    if nlp is None:
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
        if _CONTACT_TOKEN.search(line) and "|" not in line and "  " not in line and "\t" not in line:
            # A line that's *entirely* a contact detail (just an email, a phone,
            # an address) is never a name. A line where the name shares space
            # with contact details (has a separator) still gets segmented below.
            continue
        for candidate in _name_candidates_from_line(line):
            if _CONTACT_TOKEN.search(candidate) or re.search(r"\d{3,}", candidate):
                continue
            score = _score_name_line(candidate, i, tokens)
            if score > best_score:
                best_name, best_score = candidate, score

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
    """All experience-type sections joined. Resumes often split work history
    across "Work Experience" and a later "Internships" block; reading only the
    first one silently drops the rest."""
    section = _segment_text(text).get("experience", "")
    return section if section.strip() else None


def _norm_year(raw: str) -> int:
    """'22 -> 2022. Two-digit years only ever show up in recent resumes, so
    treat every one of them as 2000 + YY rather than guessing 19xx vs 20xx."""
    raw = raw.lstrip("'")
    return int(raw) if len(raw) == 4 else 2000 + int(raw)


_RANGE = re.compile(
    rf"(?:{_MONTH_RE}[\s,]*)?({_YEAR_RE})\s*(?:-|–|—|to)\s*"
    rf"(?:(?:{_MONTH_RE}[\s,]*)?({_YEAR_RE})|(present|current|now|ongoing|till\s+date|to\s+date))",
    re.IGNORECASE,
)
_NUMERIC_RANGE = re.compile(
    r"(\d{1,2})[/.](\d{2}|\d{4})\s*(?:-|–|—|to)\s*(?:(\d{1,2})[/.](\d{2}|\d{4})|(present|current|now|ongoing))",
    re.IGNORECASE,
)
# A role line with only a single year and no range at all — "AI Engineer Intern |
# Acme   2026" — is common for short internships and still carries real signal.
# Only ever consulted for a year that isn't already part of a matched range.
_LONE_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


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

    consumed: List[Tuple[int, int]] = []  # character spans already explained by a real range

    for m in _RANGE.finditer(text):
        consumed.append(m.span())
        start_month_name, start_year, end_month_name, end_year, present = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        start_month = _MONTHS[start_month_name[:3].lower()] if start_month_name else 1
        start_idx = _month_index(_norm_year(start_year), start_month)
        if present:
            end_idx = now_idx
            year_only = start_month_name is None
        else:
            end_month = _MONTHS[end_month_name[:3].lower()] if end_month_name else 1
            end_idx = _month_index(_norm_year(end_year), end_month)
            year_only = start_month_name is None or end_month_name is None
        add(start_idx, end_idx, year_only)

    for m in _NUMERIC_RANGE.finditer(text):
        consumed.append(m.span())
        sm, sy, em, ey, present = m.groups()
        if not 1 <= int(sm) <= 12:
            continue
        start_idx = _month_index(_norm_year(sy), int(sm))
        if present:
            end_idx = now_idx
        else:
            if not 1 <= int(em) <= 12:
                continue
            end_idx = _month_index(_norm_year(ey), int(em))
        add(start_idx, end_idx, False)

    for m in _LONE_YEAR.finditer(text):
        if any(s <= m.start() and m.end() <= e for s, e in consumed):
            continue
        year = int(m.group(1))
        if year > now.year:
            continue
        # Treated as a ~6-month engagement, via the same year-only floor `add`
        # already applies above — conservative rather than assuming a full year.
        start_idx = _month_index(year, 1)
        add(start_idx, start_idx, True)

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
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s*(?:and)?\s*,?\s*(\d+)\s*\+?\s*months?\s+(?:of\s+)?(?:total\s+)?(?:work\s+)?experience",
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?(?:work\s+)?experience",
    r"(\d+(?:\.\d+)?)\s*\+?\s*yrs?\s+(?:of\s+)?(?:professional\s+)?experience",
    r"total\s+(?:work\s+)?experience\s*:?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?",
    r"experience\s*:?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?",
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:in\s+)?(?:software|development|engineering|it|programming)\b",
    r"over\s+(\d+)\s+years?",
    r"more\s+than\s+(\d+)\s+years?",
]
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def extract_experience(text: str, now: Optional[datetime] = None) -> Tuple[Optional[float], str]:
    """Returns (years, source) where source is 'stated', 'computed' or 'none'.
    A number the candidate states outright wins; otherwise years are computed
    from the date ranges in the experience section (overlaps merged, education
    dates excluded). A resume that identifies itself as a fresher and states no
    other experience is treated as 0 years rather than "unknown"."""
    if not text:
        return None, "none"
    lower = text.lower()

    # "3 years 6 months" / "3 years, 6 months" of experience, checked first since
    # it is more specific than the plain "N years" patterns below.
    combo = re.search(_STATED_PATTERNS[0], lower)
    if combo:
        years, months = float(combo.group(1)), float(combo.group(2))
        if 0 <= years <= 50 and 0 <= months < 12:
            return round(years + months / 12, 1), "stated"

    for pattern in _STATED_PATTERNS[1:]:
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

    # Date-range computation only ever looks at text that is actually about work:
    # the Experience section if the resume has one, or — if it doesn't — only the
    # preamble above the first recognised header, never Education/Projects/Skills/
    # Certifications/etc. This is what keeps a degree's "(2023-2027)" or a
    # certification's issue date from being counted as years of work experience.
    section = _experience_section(text)
    if section is not None:
        scope = section
    else:
        preamble = _segment_text(text).get("preamble", "")
        scope = "\n".join(l for l in preamble.split("\n") if not _EDU_LINE.search(l))
    months = merged_months(_date_intervals(scope, now))
    if months > 0:
        return round(months / 12, 1), "computed"

    if _FRESHER_RE.search(lower):
        return 0.0, "stated"
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
    # A degree is only claimed in the education section ("Master Data Management"
    # in a job description, "BE" in prose, must not become a qualification).
    # Resumes with no recognisable heading fall back to the whole text.
    scope = _segment_text(text).get("education", "")
    if not scope.strip():
        scope = text
    found = []
    for pattern, label, flags in _DEGREE_PATTERNS:
        if re.search(pattern, scope, flags):
            found.append({"degree": label})
    return found


# ------------------------------------------------------------------ orchestration

def parse_resume(text: str, used_ocr: bool = False) -> Dict:
    email = extract_email(text)
    name, name_conf, name_method = extract_name(text, email)
    years, years_source = extract_experience(text)

    # Skills are read from everything except the Education section (a degree
    # title like "AI & Machine Learning" is not a claimed skill), with clauses
    # that name a technology the candidate doesn't have yet ("eager to learn
    # Go") stripped first so only technologies actually in use are counted.
    segments = _segment_text(text)
    skills_text = _strip_aspirational("\n".join(v for k, v in segments.items() if k != "education"))
    extractor = SkillsExtractor()
    skills = extractor.extract(skills_text)
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
