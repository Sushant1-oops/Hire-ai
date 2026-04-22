"""
LLM service for interacting with Ollama.
Handles model inference for various HR tasks like match analysis, email generation, etc.
"""

import os
import json
import requests
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from utils import logger, error_response, success_response, SimpleCache


# Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
LLM_TIMEOUT = 300  # 5 minutes timeout
llm_cache = SimpleCache(ttl_seconds=3600 * 24)  # 24 hour cache


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


# ==================== OLLAMA API CALLS ====================
def check_ollama_health() -> bool:
    """Check if Ollama service is running."""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ollama service not available: {str(e)}")
        return False


def generate_text(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Generate text using Ollama.
    Uses caching to avoid repeated LLM calls for same prompts.
    """
    cache_key = f"ollama_{hash(prompt + (system_prompt or ''))}"
    cached_response = llm_cache.get(cache_key)
    if cached_response:
        logger.info("✓ Using cached LLM response")
        return cached_response

    try:
        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        }

        if system_prompt:
            payload["system"] = system_prompt

        logger.debug(f"Calling Ollama API with model: {LLM_MODEL}")

        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json=payload,
            timeout=LLM_TIMEOUT
        )

        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "").strip()
            llm_cache.set(cache_key, generated_text)
            logger.info("✓ LLM generation successful")
            return generated_text
        else:
            logger.error(f"Ollama API error: {response.status_code}")
            return None

    except requests.Timeout:
        logger.error("Ollama API timeout")
        return None
    except Exception as e:
        logger.error(f"Error calling Ollama: {str(e)}")
        return None


def parse_json_from_text(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ==================== MATCH ANALYSIS ====================
def analyze_candidate_match(request: MatchAnalysisRequest) -> Optional[MatchAnalysisResponse]:
    """Analyze how well a candidate matches a job position."""
    system_prompt = """You are an expert HR recruiter and talent advisor. 
Analyze the resume and job description to provide a comprehensive match analysis.
Respond with ONLY valid JSON (no markdown, no extra text) in this exact format:
{
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "missing_skills": ["skill1", "skill2"],
    "recommendation": "Strong Hire|Consider|Reject",
    "explanation": "Brief explanation",
    "match_score": 0.75
}"""

    prompt = f"""
Analyze this candidate for the following role:

CANDIDATE RESUME:
{request.candidate_resume}

JOB DESCRIPTION:
{request.job_description}

Provide detailed analysis of how well this candidate matches the role.
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse match analysis response: {response_text}")
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

    system_prompt = f"""You are an expert technical interviewer.
Generate interview questions for a {request.job_title} position.
Candidate Level: {request.candidate_level or 'intermediate'}
{level_desc}
Respond with ONLY valid JSON in this exact format:
{{
    "technical_questions": ["question1", "question2", "question3"],
    "behavioral_questions": ["question1", "question2", "question3"],
    "practical_tasks": ["task1", "task2"]
}}"""

    prompt = f"""
Generate {request.candidate_level or 'intermediate'}-level interview questions for a {request.job_title} position.

CANDIDATE RESUME:
{request.candidate_resume}

Create:
1. 3 technical questions appropriate for the role
2. 3 behavioral questions to assess soft skills
3. 2 practical tasks or real-world scenarios
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse interview questions response: {response_text}")
        return None

    try:
        technical = json_data.get("technical_questions", [])
        behavioral = json_data.get("behavioral_questions", [])
        practical = json_data.get("practical_tasks", [])

        # Handle object arrays with 'question' field
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
        "interview_invite": "Write a professional and friendly interview invitation email. Include the interview details if provided.",
        "rejection": "Write a respectful and constructive rejection email. Be empathetic and encourage the candidate to apply again in the future.",
        "cold_outreach": "Write an engaging cold outreach email to attract the candidate to apply for the position.",
        "offer": "Write a congratulatory job offer email. Be enthusiastic and professional. Mention the role and invite them to discuss terms.",
        "follow_up": "Write a professional follow-up email to check on the candidate's status and maintain engagement.",
        "thank_you": "Write a warm thank-you email after an interview. Express appreciation for their time and interest.",
    }

    instruction = email_instructions.get(request.email_type, "Write a professional email.")

    system_prompt = f"""You are an expert recruiter writing professional emails.
{instruction}
Respond with ONLY valid JSON (no markdown, no extra text) in this exact format:
{{
    "subject_line": "Subject Line Here",
    "email_body": "Email body text here"
}}"""

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
    cache_key = f"ollama_{hash(prompt + (system_prompt or ''))}"

    for attempt in range(1, max_retries + 1):
        response_text = generate_text(prompt, system_prompt)
        last_text = response_text
        if not response_text:
            logger.error("Failed to generate email (no response from LLM)")
            break

        json_data = parse_json_from_text(response_text)
        if not json_data:
            logger.error(f"Failed to parse email response (attempt {attempt}): {response_text}")
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
    system_prompt = """You are an expert HR manager and job description writer.
Create a comprehensive, professional job description.
Respond with ONLY valid JSON (no markdown, no extra text) in this exact format:
{
    "job_description": "Full JD text here...",
    "required_skills": ["skill1", "skill2", "skill3"],
    "nice_to_have_skills": ["skill1", "skill2"]
}"""

    prompt = f"""
Create a professional job description for:
- Position: {request.job_title}
- Company: {request.company_name or 'A growing tech company'}
- Summary: {request.job_shorthand}

Required skills: {', '.join(request.required_skills) if request.required_skills else 'Use industry standard'}

Include:
1. Role overview
2. Key responsibilities (5-7)
3. Required qualifications
4. Nice-to-have qualifications
5. Benefits and culture fit
"""

    response_text = generate_text(prompt, system_prompt)
    if not response_text:
        return None

    json_data = parse_json_from_text(response_text)
    if not json_data:
        logger.error(f"Failed to parse job description response: {response_text}")
        return None

    try:
        return JobDescriptionResponse(**json_data)
    except Exception as e:
        logger.error(f"Error creating JobDescriptionResponse: {str(e)}")
        return None


# ==================== HEALTH CHECK ====================
if __name__ == "__main__":
    print(f"Checking Ollama service at {OLLAMA_API_URL}...")
    if check_ollama_health():
        print("✓ Ollama is running")
        result = generate_text("Say hello")
        print(f"Test response: {result}")
    else:
        print("✗ Ollama is not running")
        print(f"Start Ollama with: ollama serve")
        print(f"Pull model with: ollama pull {LLM_MODEL}")
