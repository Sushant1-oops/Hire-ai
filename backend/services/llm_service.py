import hashlib
import json
import re
import time
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from .cache_service import Cache
from core.config import (
    GROQ_TIMEOUT, LLM_MAX_INPUT_CHARS, LLM_MAX_RETRIES, LLM_REDACT_PII, OLLAMA_TIMEOUT,
)
import os
from ai.llm_safety import UNTRUSTED_DATA_NOTICE, redact_pii, wrap_untrusted
from core.observability import traceable
from core.utils import logger

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

llm_cache = Cache("llm", 3600 * 24)
_active_provider = "groq" if GROQ_API_KEY else "ollama"
_status_cache = {"at": 0.0, "value": None}

_PLACEHOLDER = re.compile(r"\[[A-Za-z][A-Za-z '\-]{1,30}\]")


# ------------------------------------------------------------------ schemas

def _clean_list(items, max_items: int, max_len: int) -> List[str]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            item = item.get("question") or item.get("description") or item.get("text") or ""
        text = " ".join(str(item).split())
        if text and text.lower() not in {"n/a", "none", "tbd"}:
            out.append(text[:max_len])
    return out[:max_items]


class MatchAnalysisRequest(BaseModel):
    candidate_resume: str
    job_description: str
    candidate_name: Optional[str] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    final_score: Optional[float] = None
    recommendation: Optional[str] = None


class MatchAnalysisResponse(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    explanation: str


class InterviewQuestionsRequest(BaseModel):
    candidate_resume: str
    candidate_skills: List[str]
    job_title: str
    job_description: str
    required_skills: List[str]
    missing_skills: List[str]
    candidate_name: Optional[str] = None
    candidate_level: Optional[str] = None


class InterviewQuestionsResponse(BaseModel):
    technical_questions: List[str]
    behavioral_questions: List[str]
    practical_tasks: List[str]


class OutreachEmailRequest(BaseModel):
    candidate_name: str
    job_title: str
    email_type: str
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    interview_date: Optional[str] = None
    interview_time: Optional[str] = None
    interview_location: Optional[str] = None


class OutreachEmailResponse(BaseModel):
    subject_line: str
    email_body: str


class JobDescriptionRequest(BaseModel):
    job_title: str = Field(min_length=2, max_length=255)
    job_shorthand: str = Field(min_length=2, max_length=2000)
    company_name: Optional[str] = Field(default=None, max_length=255)
    required_skills: Optional[List[str]] = Field(default=None, max_length=40)


class JobDescriptionResponse(BaseModel):
    job_description: str
    required_skills: List[str]
    nice_to_have_skills: List[str]


# ------------------------------------------------------------------ providers

def check_groq_health() -> bool:
    if not GROQ_API_KEY:
        return False
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def check_ollama_health() -> bool:
    try:
        return requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def _generate_with_groq(prompt: str, system_prompt: Optional[str], temperature: float) -> Optional[str]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": GROQ_MODEL, "messages": messages, "temperature": temperature,
        "max_tokens": 2048, "top_p": 0.9, "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    for attempt in range(LLM_MAX_RETRIES):
        delay = 2 ** attempt
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=GROQ_TIMEOUT)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.replace(".", "", 1).isdigit():
                    delay = min(float(retry_after), 10.0)
                logger.warning(f"Groq returned {response.status_code} (attempt {attempt + 1}/{LLM_MAX_RETRIES})")
            else:
                logger.error(f"Groq returned {response.status_code}; not retrying")
                return None
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"Groq request failed ({type(e).__name__}) (attempt {attempt + 1}/{LLM_MAX_RETRIES})")
        except (KeyError, ValueError) as e:
            logger.error(f"Groq returned an unreadable response: {e}")
            return None
        if attempt < LLM_MAX_RETRIES - 1:
            time.sleep(delay)
    return None


def _generate_with_ollama(prompt: str, system_prompt: Optional[str], temperature: float) -> Optional[str]:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": temperature}}
    if system_prompt:
        payload["system"] = system_prompt
    for attempt in range(2):
        try:
            response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
            if response.status_code == 200:
                return response.json().get("response", "").strip() or None
            return None
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 0:
                time.sleep(1)
    return None


@traceable(name="llm_generate_text", run_type="llm")
def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    pii_names: Optional[List[str]] = None,
    temperature: float = 0.3,
    use_cache: bool = True,
) -> Optional[str]:
    """Groq first (with retry/backoff), local Ollama as fallback. Text sent to
    Groq has contact details, and the candidate names in pii_names, masked; the
    local Ollama model gets the unredacted text because nothing leaves the machine."""
    global _active_provider
    key = hashlib.sha256(f"{system_prompt or ''}\x00{prompt}\x00{temperature}".encode("utf-8")).hexdigest()
    if use_cache:
        cached = llm_cache.get(key)
        if cached:
            return cached

    if GROQ_API_KEY:
        outgoing = redact_pii(prompt, pii_names) if LLM_REDACT_PII else prompt
        text = _generate_with_groq(outgoing, system_prompt, temperature)
        if text:
            _active_provider = "groq"
            llm_cache.set(key, text)
            return text
        logger.warning("Groq unavailable after retries; falling back to Ollama")

    text = _generate_with_ollama(prompt, system_prompt, temperature)
    if text:
        _active_provider = "ollama"
        llm_cache.set(key, text)
        return text
    return None


def get_active_provider() -> str:
    return _active_provider


def get_llm_status() -> Dict:
    """Provider health checks make network calls, so the result is reused for 60s."""
    now = time.time()
    if _status_cache["value"] is not None and now - _status_cache["at"] < 60:
        return _status_cache["value"]
    value = {
        "active_provider": _active_provider,
        "groq": {"configured": bool(GROQ_API_KEY), "healthy": check_groq_health() if GROQ_API_KEY else False, "model": GROQ_MODEL},
        "ollama": {"configured": True, "healthy": check_ollama_health(), "model": OLLAMA_MODEL, "url": OLLAMA_API_URL},
    }
    _status_cache.update(at=now, value=value)
    return value


def parse_json_from_text(text: str) -> Optional[Dict]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[cleaned.index("\n") + 1:] if "\n" in cleaned else cleaned
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


# ------------------------------------------------------------------ tasks

@traceable(name="analyze_candidate_match", run_type="chain")
def analyze_candidate_match(request: MatchAnalysisRequest) -> Optional[MatchAnalysisResponse]:
    """Explains a result the ranking engine already produced. The score and the
    recommendation come from ScoringService and are handed to the model as facts;
    the model is not asked to decide them and anything it says about them is discarded."""
    system_prompt = (
        "You are an experienced technical recruiter writing a short, factual assessment of one candidate "
        "for one role. The scoring has already been done by a deterministic engine; explain it, do not "
        "re-score it. Refer to the candidate as 'the candidate'. Only state things supported by the resume text. "
        f"{UNTRUSTED_DATA_NOTICE}\n"
        'Respond with ONLY valid JSON: {"strengths": ["..."], "weaknesses": ["..."], "explanation": "2-3 sentences"}. '
        "Give 2-5 strengths and 1-4 weaknesses, each one sentence."
    )
    engine_facts = []
    if request.final_score is not None:
        engine_facts.append(f"Engine score: {request.final_score:.2f} ({request.recommendation or 'n/a'})")
    engine_facts.append(f"Required skills the resume matches: {', '.join(request.matched_skills) or 'none'}")
    engine_facts.append(f"Required skills not found in the resume: {', '.join(request.missing_skills) or 'none'}")

    prompt = (
        "RANKING ENGINE RESULT (trusted):\n" + "\n".join(engine_facts) + "\n\n"
        "JOB DESCRIPTION:\n" + request.job_description[:LLM_MAX_INPUT_CHARS // 3] + "\n\n"
        "CANDIDATE RESUME:\n" + wrap_untrusted("resume", request.candidate_resume, LLM_MAX_INPUT_CHARS)
    )
    text = generate_text(prompt, system_prompt, pii_names=[request.candidate_name] if request.candidate_name else None, temperature=0.2)
    data = parse_json_from_text(text) if text else None
    if not data:
        return None
    strengths = _clean_list(data.get("strengths"), 5, 300)
    weaknesses = _clean_list(data.get("weaknesses"), 4, 300)
    explanation = " ".join(str(data.get("explanation", "")).split())[:800]
    if not (strengths or weaknesses) or not explanation:
        return None
    return MatchAnalysisResponse(strengths=strengths, weaknesses=weaknesses, explanation=explanation)


@traceable(name="generate_interview_questions", run_type="chain")
def generate_interview_questions(request: InterviewQuestionsRequest) -> Optional[InterviewQuestionsResponse]:
    level_context = {
        "fresher": "Entry-level. Focus on fundamentals.",
        "intermediate": "Mid-level. Balance theory and practice.",
        "experienced": "Senior. Focus on architecture and leadership.",
    }
    level = request.candidate_level if request.candidate_level in level_context else "intermediate"

    system_prompt = (
        f"You are an expert technical interviewer preparing questions for a {request.job_title[:120]} position. "
        f"Candidate level: {level}. {level_context[level]} {UNTRUSTED_DATA_NOTICE}\n"
        'Respond with ONLY valid JSON: {"technical_questions": ["q1","q2","q3","q4"], '
        '"behavioral_questions": ["q1","q2","q3"], "practical_tasks": ["t1","t2"]}\n'
        "- 4 technical questions: 2 test depth in skills the candidate already has, 2 probe the missing required skills.\n"
        "- 3 STAR-method behavioral questions.\n"
        "- 2 hands-on practical tasks relevant to the job description."
    )
    prompt = (
        f"Job description:\n{request.job_description[:LLM_MAX_INPUT_CHARS // 3] or 'N/A'}\n\n"
        f"Required skills: {', '.join(request.required_skills)}\n"
        f"Candidate skills: {', '.join(request.candidate_skills)}\n"
        f"Missing required skills (probe these): {', '.join(request.missing_skills) or 'none'}\n\n"
        f"Candidate resume:\n{wrap_untrusted('resume', request.candidate_resume, LLM_MAX_INPUT_CHARS)}"
    )
    text = generate_text(prompt, system_prompt, pii_names=[request.candidate_name] if request.candidate_name else None, temperature=0.5)
    data = parse_json_from_text(text) if text else None
    if not data:
        return None
    technical = _clean_list(data.get("technical_questions"), 6, 400)
    behavioral = _clean_list(data.get("behavioral_questions"), 5, 400)
    practical = _clean_list(data.get("practical_tasks"), 3, 500)
    if len(technical) < 2 or not behavioral or not practical:
        return None
    return InterviewQuestionsResponse(technical_questions=technical, behavioral_questions=behavioral, practical_tasks=practical)


@traceable(name="generate_outreach_email", run_type="chain")
def generate_outreach_email(request: OutreachEmailRequest) -> tuple[Optional[OutreachEmailResponse], Optional[str]]:
    email_instructions = {
        "interview_invite": "Write a warm interview invitation email.", "rejection": "Write a respectful rejection email.",
        "cold_outreach": "Write an engaging cold outreach email.", "offer": "Write an enthusiastic job offer email.",
        "follow_up": "Write a friendly follow-up email.", "thank_you": "Write a sincere thank-you email.",
    }
    instruction = email_instructions.get(request.email_type, "Write a professional email.")

    system_prompt = f"""You are a world-class recruiter. {instruction}
Respond with ONLY valid JSON in this format:
{{"subject_line": "Subject line", "email_body": "Greeting\\n\\nParagraph 1\\n\\nParagraph 2\\n\\nSign-off,\\nName"}}
Use \\n\\n to separate paragraphs. Keep it 150-250 words.

The email must be complete and ready to send exactly as written. Never use bracket placeholders like
[Company Name], [Your Name], [Date] or [Insert X], and never write "N/A" or "TBD". Only mention a detail
(company, contact name, interview date/time/location) if it is actually given below. If interview scheduling
details are not given, say the exact time will be shared separately instead of naming a placeholder."""

    details = [f"Candidate Name: {request.candidate_name}", f"Job Title: {request.job_title}"]
    if request.company_name:
        details.append(f"Company: {request.company_name}")
    if request.contact_person:
        details.append(f"Sign the email from: {request.contact_person}")
    if request.email_type == "interview_invite":
        if any([request.interview_date, request.interview_time, request.interview_location]):
            details.append(
                f"Interview Details - Date: {request.interview_date or 'not yet set'}, "
                f"Time: {request.interview_time or 'not yet set'}, "
                f"Location: {request.interview_location or 'not yet set'}"
            )
        else:
            details.append("Interview scheduling details are not decided yet. Say you'll follow up separately to find a time.")
    prompt = "\n".join(details) + "\nMake it personalized and professional."

    raw = None
    for attempt in range(2):
        # pii_names stays empty on purpose: the email is addressed to the candidate by name.
        raw = generate_text(prompt, system_prompt, temperature=0.6, use_cache=(attempt == 0))
        data = parse_json_from_text(raw) if raw else None
        if not data:
            continue
        try:
            parsed = OutreachEmailResponse(**data)
        except Exception:
            continue
        subject = " ".join(parsed.subject_line.split())[:150]
        body = parsed.email_body.strip()
        if not subject or not body or _PLACEHOLDER.search(subject + body):
            continue  # blank content or an unfilled [Placeholder]: regenerate once, bypassing the cache
        return OutreachEmailResponse(subject_line=subject, email_body=body), raw
    return None, raw


@traceable(name="generate_job_description", run_type="chain")
def generate_job_description(request: JobDescriptionRequest) -> Optional[JobDescriptionResponse]:
    system_prompt = (
        "You are an expert HR manager. Create a compelling job description. Respond with ONLY valid JSON: "
        '{"job_description": "Full JD text", "required_skills": ["skill1"], "nice_to_have_skills": ["skill1"]}'
    )
    prompt = (
        f"Position: {request.job_title[:150]}\n"
        f"Company: {request.company_name or 'A growing tech company'}\n"
        f"Summary: {request.job_shorthand[:1000]}\n"
        f"Required skills: {', '.join(request.required_skills) if request.required_skills else 'Use industry standard'}\n"
        "Include role overview, responsibilities, qualifications, and benefits."
    )
    text = generate_text(prompt, system_prompt, temperature=0.6)
    data = parse_json_from_text(text) if text else None
    if not data:
        return None
    description = str(data.get("job_description", "")).strip()
    required = _clean_list(data.get("required_skills"), 20, 60)
    nice = _clean_list(data.get("nice_to_have_skills"), 15, 60)
    if len(description) < 80 or not required:
        return None
    return JobDescriptionResponse(job_description=description[:8000], required_skills=required, nice_to_have_skills=nice)
