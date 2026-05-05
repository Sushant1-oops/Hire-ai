"""
LLM service with dual-provider architecture: Groq (primary) + Ollama (fallback).
Groq provides blazing-fast inference with the 70B Llama 3.3 model via cloud API.
If Groq is unavailable (no API key, rate limit, network error), the system
automatically and instantly falls back to the local Ollama instance.

Handles model inference for various HR tasks like match analysis, email generation, etc.
"""

import os
import json
import requests
import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from utils import logger, error_response, success_response, SimpleCache


# ==================== CONFIGURATION ====================
# Groq Configuration (Primary - Cloud)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = 120  # 2 minutes - Groq is very fast

# Ollama Configuration (Fallback - Local)
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = 300  # 5 minutes - local model is slower

# Shared
llm_cache = SimpleCache(ttl_seconds=3600 * 24)  # 24 hour cache

# Track active provider for health checks
_active_provider = "groq" if GROQ_API_KEY else "ollama"


# ==================== REQUEST/RESPONSE MODELS ====================
class MatchAnalysisRequest(BaseModel):
    """Request for candidate-job match analysis."""
    candidate_resume: str
    job_description: str
    candidate_name: Optional[str] = None


class MatchAnalysisResponse(BaseModel):
    """Response for match analysis."""
    strengths: List[str]
    weaknesses: List[str]
    missing_skills: List[str]
    recommendation: str
    explanation: str
    match_score: float


class InterviewQuestionsRequest(BaseModel):
    """Request for generating interview questions."""
    candidate_resume: str
    job_title: str
    candidate_name: Optional[str] = None
    candidate_level: Optional[str] = None


class InterviewQuestionsResponse(BaseModel):
    """Response with generated interview questions."""
    technical_questions: List[str]
    behavioral_questions: List[str]
    practical_tasks: List[str]


class OutreachEmailRequest(BaseModel):
    """Request for generating outreach email."""
    candidate_name: str
    job_title: str
    email_type: str
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    interview_date: Optional[str] = None
    interview_time: Optional[str] = None
    interview_location: Optional[str] = None


class OutreachEmailResponse(BaseModel):
    """Response with generated email."""
    subject_line: str
    email_body: str


class JobDescriptionRequest(BaseModel):
    """Request for generating job description."""
    job_title: str
    job_shorthand: str
    company_name: Optional[str] = None
    required_skills: Optional[List[str]] = None


class JobDescriptionResponse(BaseModel):
    """Response with generated job description."""
    job_description: str
    required_skills: List[str]
    nice_to_have_skills: List[str]


# ==================== GROQ API (PRIMARY) ====================
def check_groq_health() -> bool:
    """Check if Groq API is reachable and the API key is valid."""
    if not GROQ_API_KEY:
        return False
    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=3
        )
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Groq health check failed: {str(e)}")
        return False


def _generate_with_groq(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Generate text using Groq's ultra-fast LPU inference.
    Uses the OpenAI-compatible chat completions API.
    """
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 4096,
            "top_p": 0.9,
            "response_format": {"type": "json_object"},
        }

        start_time = time.time()

        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=GROQ_TIMEOUT
        )

        elapsed = round(time.time() - start_time, 2)

        if response.status_code == 200:
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"].strip()
            usage = result.get("usage", {})
            logger.info(
                f"[GROQ] Generation successful in {elapsed}s | "
                f"Model: {GROQ_MODEL} | "
                f"Tokens: {usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out"
            )
            return generated_text
        elif response.status_code == 429:
            logger.warning(f"[GROQ] Rate limited (429). Falling back to Ollama.")
            return None
        else:
            error_detail = response.text[:200]
            logger.error(f"[GROQ] API error {response.status_code}: {error_detail}")
            return None

    except requests.Timeout:
        logger.error("[GROQ] Request timed out")
        return None
    except Exception as e:
        logger.error(f"[GROQ] Error: {str(e)}")
        return None


# ==================== OLLAMA API (FALLBACK) ====================
def check_ollama_health() -> bool:
    """Check if Ollama service is running."""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ollama service not available: {str(e)}")
        return False


def _generate_with_ollama(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Generate text using local Ollama instance.
    Used as fallback when Groq is unavailable.
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        }

        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.time()

        logger.info(f"[OLLAMA] Calling local model: {OLLAMA_MODEL}")
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        elapsed = round(time.time() - start_time, 2)

        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "").strip()
            logger.info(f"[OLLAMA] Generation successful in {elapsed}s")
            return generated_text
        else:
            logger.error(f"[OLLAMA] API error: {response.status_code}")
            return None

    except requests.Timeout:
        logger.error("[OLLAMA] Request timed out")
        return None
    except Exception as e:
        logger.error(f"[OLLAMA] Error: {str(e)}")
        return None


# ==================== UNIFIED GENERATE (WITH AUTO-FALLBACK) ====================
def generate_text(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Generate text using the best available LLM provider.
    Priority: Groq (cloud, fast, 70B) -> Ollama (local, slow, 3B).
    Results are cached for 24 hours to avoid redundant API calls.
    """
    global _active_provider

    # Check cache first
    cache_key = f"llm_{hash(prompt + (system_prompt or ''))}"
    cached_response = llm_cache.get(cache_key)
    if cached_response:
        logger.info("[CACHE] Using cached LLM response")
        return cached_response

    generated_text = None

    # Strategy 1: Try Groq (Primary)
    if GROQ_API_KEY:
        logger.debug(f"[LLM] Attempting Groq ({GROQ_MODEL})...")
        generated_text = _generate_with_groq(prompt, system_prompt)
        if generated_text:
            _active_provider = "groq"
            llm_cache.set(cache_key, generated_text)
            return generated_text
        else:
            logger.warning("[LLM] Groq failed. Falling back to Ollama...")

    # Strategy 2: Fallback to Ollama (Local)
    logger.debug(f"[LLM] Attempting Ollama ({OLLAMA_MODEL})...")
    generated_text = _generate_with_ollama(prompt, system_prompt)
    if generated_text:
        _active_provider = "ollama"
        llm_cache.set(cache_key, generated_text)
        return generated_text

    # Both providers failed
    logger.error("[LLM] All providers failed. No text generated.")
    _active_provider = "none"
    return None


def get_active_provider() -> str:
    """Return the name of the currently active LLM provider."""
    return _active_provider


def get_llm_status() -> Dict:
    """Get comprehensive status of all LLM providers."""
    groq_available = bool(GROQ_API_KEY)
    groq_healthy = check_groq_health() if groq_available else False
    ollama_healthy = check_ollama_health()

    return {
        "active_provider": _active_provider,
        "groq": {
            "configured": groq_available,
            "healthy": groq_healthy,
            "model": GROQ_MODEL,
        },
        "ollama": {
            "configured": True,
            "healthy": ollama_healthy,
            "model": OLLAMA_MODEL,
            "url": OLLAMA_API_URL,
        }
    }


# ==================== JSON PARSER ====================
def parse_json_from_text(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response text. Handles markdown code blocks."""
    if not text:
        return None

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
        # Remove closing fence
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ==================== MATCH ANALYSIS ====================
def analyze_candidate_match(request: MatchAnalysisRequest) -> Optional[MatchAnalysisResponse]:
    """Analyze how well a candidate matches a job position."""
    system_prompt = """You are an expert HR recruiter and talent advisor with deep expertise in technical hiring.
Analyze the resume against the job description and provide a thorough, insightful match analysis.
Be specific and actionable in your assessment — reference exact skills, experiences, and qualifications from the resume.

You MUST respond with ONLY valid JSON (no markdown, no extra text) in this EXACT format:
{
    "strengths": ["strength1", "strength2", "strength3"],
    "weaknesses": ["weakness1", "weakness2"],
    "missing_skills": ["skill1", "skill2"],
    "recommendation": "Strong Hire|Consider|Reject",
    "explanation": "A detailed 2-3 sentence explanation of your overall assessment",
    "match_score": 0.75
}

Rules:
- strengths: List 3-5 specific strengths drawn directly from the resume
- weaknesses: List 2-3 genuine concerns or gaps
- missing_skills: List skills required by the JD but absent from the resume
- recommendation: Must be exactly one of "Strong Hire", "Consider", or "Reject"
- match_score: A float between 0.0 and 1.0
- DO NOT add any extra fields. Return ONLY the JSON object above."""

    prompt = f"""
Analyze this candidate for the following role:

CANDIDATE RESUME:
{request.candidate_resume}

JOB DESCRIPTION:
{request.job_description}

Provide a detailed, data-driven analysis of how well this candidate matches the role.
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse match analysis response: {response_text[:300]}")
        return None

    try:
        return MatchAnalysisResponse(**json_data)
    except Exception as e:
        logger.error(f"Error creating MatchAnalysisResponse: {str(e)}")
        return None


# ==================== INTERVIEW QUESTIONS ====================
def generate_interview_questions(request: InterviewQuestionsRequest) -> Optional[InterviewQuestionsResponse]:
    """Generate interview questions tailored to candidate level."""
    level_context = {
        "fresher": "Entry-level candidate with minimal professional experience. Focus on learning ability, fundamentals, and potential.",
        "intermediate": "Mid-level professional with 2-5 years of experience. Balance theoretical knowledge with practical experience.",
        "experienced": "Senior professional with 5+ years of experience. Focus on architectural decisions, leadership, and complex problem-solving."
    }

    level_desc = level_context.get(request.candidate_level or "intermediate", level_context["intermediate"])

    system_prompt = f"""You are an expert technical interviewer who has conducted thousands of interviews at top-tier companies.
Generate highly targeted, insightful interview questions for a {request.job_title} position.
Candidate Level: {request.candidate_level or 'intermediate'}
{level_desc}

You MUST respond with ONLY valid JSON in this EXACT format:
{{
    "technical_questions": ["question1", "question2", "question3"],
    "behavioral_questions": ["question1", "question2", "question3"],
    "practical_tasks": ["task1", "task2"]
}}

Rules:
- technical_questions: 3 deep, role-specific technical questions. Reference technologies from the candidate's resume.
- behavioral_questions: 3 STAR-method behavioral questions targeting leadership, teamwork, and problem-solving.
- practical_tasks: 2 hands-on coding/design tasks or real-world scenarios relevant to the role.
- Each question must be a single string. Do NOT use nested objects.
- DO NOT add any extra fields. Return ONLY the JSON object above."""

    prompt = f"""
Generate {request.candidate_level or 'intermediate'}-level interview questions for a {request.job_title} position.

CANDIDATE RESUME:
{request.candidate_resume}

Create questions that are specifically tailored to this candidate's background and the role requirements.
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse interview questions response: {response_text[:300]}")
        return None

    try:
        technical = json_data.get("technical_questions", [])
        behavioral = json_data.get("behavioral_questions", [])
        practical = json_data.get("practical_tasks", [])

        # Handle object arrays with 'question' field (robustness for smaller models)
        if technical and isinstance(technical[0], dict) and "question" in technical[0]:
            technical = [q.get("question", "") for q in technical]
        if behavioral and isinstance(behavioral[0], dict) and "question" in behavioral[0]:
            behavioral = [q.get("question", "") for q in behavioral]
        if practical and isinstance(practical[0], dict):
            if "description" in practical[0]:
                practical = [t.get("description", "") for t in practical]
            elif "question" in practical[0]:
                practical = [t.get("question", "") for t in practical]

        return InterviewQuestionsResponse(
            technical_questions=technical,
            behavioral_questions=behavioral,
            practical_tasks=practical
        )
    except Exception as e:
        logger.error(f"Error creating InterviewQuestionsResponse: {str(e)}")
        return None


# ==================== EMAIL GENERATION ====================
def generate_outreach_email(request: OutreachEmailRequest) -> tuple[Optional[OutreachEmailResponse], Optional[str]]:
    """
    Generate professional outreach emails.
    Supports all email types: interview_invite, rejection, cold_outreach,
    offer, follow_up, thank_you.
    """
    email_instructions = {
        "interview_invite": "Write a professional, warm, and enthusiastic interview invitation email. Include the interview details if provided. Make the candidate feel valued and excited.",
        "rejection": "Write a respectful, empathetic, and constructive rejection email. Acknowledge the candidate's strengths, provide brief encouragement, and invite them to apply again in the future.",
        "cold_outreach": "Write an engaging, compelling cold outreach email that makes the candidate excited about the opportunity. Highlight what makes this role and company unique.",
        "offer": "Write a congratulatory, enthusiastic job offer email. Express genuine excitement about the candidate joining the team. Mention the role and invite them to discuss terms.",
        "follow_up": "Write a professional, friendly follow-up email to check on the candidate's status and maintain engagement. Show genuine interest in their decision.",
        "thank_you": "Write a warm, sincere thank-you email after an interview. Express appreciation for their time, reference something specific about the conversation, and reinforce enthusiasm.",
    }

    instruction = email_instructions.get(request.email_type, "Write a professional email.")

    system_prompt = f"""You are a world-class recruiter at a prestigious company, known for writing emails that candidates love to receive.
{instruction}

You MUST respond with ONLY valid JSON (no markdown, no extra text) in this EXACT format:
{{
    "subject_line": "A compelling, professional subject line",
    "email_body": "Greeting paragraph\\n\\nFirst body paragraph\\n\\nSecond body paragraph\\n\\nClosing paragraph\\n\\nSign-off,\\nName"
}}

CRITICAL FORMATTING RULES for email_body:
- You MUST use \\n\\n (two newline characters) to separate every paragraph inside the email_body string.
- The email MUST have at least 4-5 separate paragraphs, each separated by \\n\\n.
- Structure: Greeting -> Opening -> Body details -> Call to action -> Sign-off
- Use \\n (single newline) for line breaks within a section (e.g., between "Best regards," and the name).
- If listing details (date, time, location), put each on its own line using \\n with a dash prefix.
- The email must feel personal, warm, and human — never robotic or templated.
- Use the candidate's name naturally.
- Keep the email concise but impactful (150-250 words).
- Include a clear call-to-action.
- DO NOT add any extra fields. Return ONLY the JSON object above."""

    interview_details = ""
    if request.interview_date or request.interview_time or request.interview_location:
        interview_details = "\nInterview Details (if applicable):"
        if request.interview_date:
            interview_details += f"\n- Date: {request.interview_date}"
        if request.interview_time:
            interview_details += f"\n- Time: {request.interview_time}"
        if request.interview_location:
            interview_details += f"\n- Location: {request.interview_location}"

    prompt = f"""
Write an email for:
- Candidate Name: {request.candidate_name}
- Job Title: {request.job_title}
- Company: {request.company_name or 'Our Company'}
- Contact Person: {request.contact_person or 'Hiring Team'}{interview_details}

Make it personalized, professional, and compelling.
"""

    max_retries = 3
    last_text = None
    cache_key = f"llm_{hash(prompt + (system_prompt or ''))}"

    for attempt in range(1, max_retries + 1):
        response_text = generate_text(prompt, system_prompt)
        last_text = response_text
        if not response_text:
            logger.error("Failed to generate email (no response from LLM)")
            break

        json_data = parse_json_from_text(response_text)
        if not json_data:
            logger.error(f"Failed to parse email response (attempt {attempt}): {response_text[:300]}")
            llm_cache.delete(cache_key)
            continue

        try:
            return OutreachEmailResponse(**json_data), response_text
        except Exception as e:
            logger.error(f"Error creating OutreachEmailResponse on attempt {attempt}: {str(e)}")
            llm_cache.delete(cache_key)
            continue

    logger.error("Exceeded retries for email generation")
    return None, last_text


# ==================== JOB DESCRIPTION GENERATION ====================
def generate_job_description(request: JobDescriptionRequest) -> Optional[JobDescriptionResponse]:
    """Generate comprehensive job description."""
    system_prompt = """You are an expert HR manager and job description writer who creates compelling, inclusive, and professional job descriptions that attract top talent.

You MUST respond with ONLY valid JSON (no markdown, no extra text) in this EXACT format:
{
    "job_description": "Full JD text here...",
    "required_skills": ["skill1", "skill2", "skill3"],
    "nice_to_have_skills": ["skill1", "skill2"]
}

Rules:
- job_description: A comprehensive, well-structured job description (300-500 words) covering role overview, responsibilities, qualifications, and benefits.
- required_skills: 5-8 essential technical and professional skills as simple strings.
- nice_to_have_skills: 3-5 bonus skills that would strengthen a candidate's application.
- DO NOT add any other fields to the JSON object.
- All arrays must use JSON lists ([]), never sets ({}).
- Return ONLY the JSON object above."""

    prompt = f"""
Create a professional, compelling job description for:
- Position: {request.job_title}
- Company: {request.company_name or 'A growing tech company'}
- Summary: {request.job_shorthand}

Required skills: {', '.join(request.required_skills) if request.required_skills else 'Use industry standard'}

Include:
1. An engaging role overview that excites top candidates
2. Key responsibilities (5-7 bullet points)
3. Required qualifications
4. Nice-to-have qualifications
5. Benefits and culture fit
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse job description response: {response_text[:300]}")
        return None

    try:
        return JobDescriptionResponse(**json_data)
    except Exception as e:
        logger.error(f"Error creating JobDescriptionResponse: {str(e)}")
        return None


# ==================== STARTUP LOG ====================
def _log_provider_status():
    """Log the LLM provider configuration at startup."""
    if GROQ_API_KEY:
        logger.info(f"[LLM] Primary provider: Groq ({GROQ_MODEL})")
        logger.info(f"[LLM] Fallback provider: Ollama ({OLLAMA_MODEL})")
    else:
        logger.info(f"[LLM] Groq API key not configured. Using Ollama only ({OLLAMA_MODEL})")
        logger.info("[LLM] Set GROQ_API_KEY in .env to enable Groq (recommended)")

_log_provider_status()


# ==================== HEALTH CHECK ====================
if __name__ == "__main__":
    print("=" * 60)
    print("  LLM Provider Health Check")
    print("=" * 60)

    # Check Groq
    if GROQ_API_KEY:
        print(f"\n[Groq] API Key: {'*' * 8}...{GROQ_API_KEY[-4:]}")
        print(f"[Groq] Model: {GROQ_MODEL}")
        if check_groq_health():
            print("[Groq] Status: HEALTHY")
            result = generate_text("Respond with a short JSON: {\"status\": \"ok\"}", "You are a test bot. Respond with valid JSON only.")
            print(f"[Groq] Test response: {result}")
        else:
            print("[Groq] Status: UNHEALTHY")
    else:
        print("\n[Groq] Not configured (no GROQ_API_KEY in .env)")

    # Check Ollama
    print(f"\n[Ollama] URL: {OLLAMA_API_URL}")
    print(f"[Ollama] Model: {OLLAMA_MODEL}")
    if check_ollama_health():
        print("[Ollama] Status: HEALTHY")
    else:
        print("[Ollama] Status: UNHEALTHY")
        print(f"  Start Ollama with: ollama serve")
        print(f"  Pull model with: ollama pull {OLLAMA_MODEL}")

    print("\n" + "=" * 60)
