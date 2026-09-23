
import os
import json
import requests
import time
from typing import Optional, List, Dict
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel
from utils import logger, SimpleCache
from observability import traceable

load_dotenv(find_dotenv())

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b") 
GROQ_TIMEOUT = 120

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = 300

llm_cache = SimpleCache(ttl_seconds=3600 * 24)
_active_provider = "groq" if GROQ_API_KEY else "ollama"

class MatchAnalysisRequest(BaseModel):
    candidate_resume: str
    job_description: str
    candidate_name: Optional[str] = None

class MatchAnalysisResponse(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    missing_skills: List[str]
    recommendation: str
    explanation: str
    match_score: float

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
    job_title: str
    job_shorthand: str
    company_name: Optional[str] = None
    required_skills: Optional[List[str]] = None

class JobDescriptionResponse(BaseModel):
    job_description: str
    required_skills: List[str]
    nice_to_have_skills: List[str]

def check_groq_health() -> bool:
    if not GROQ_API_KEY: return False
    try:
        response = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, timeout=3)
        return response.status_code == 200
    except: return False

def _generate_with_groq(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    try:
        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.6, "max_tokens": 4096, "top_p": 0.9, "response_format": {"type": "json_object"}}
        
        response = requests.post(GROQ_API_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=GROQ_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        elif response.status_code == 429: return None
        else: return None
    except: return None

def check_ollama_health() -> bool:
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except: return False

def _generate_with_ollama(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    try:
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "temperature": 0.7}
        if system_prompt: payload["system"] = system_prompt
        response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
        if response.status_code == 200: return response.json().get("response", "").strip()
        return None
    except: return None

@traceable(name="llm_generate_text", run_type="llm")
def generate_text(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    global _active_provider
    cache_key = f"llm_{hash(prompt + (system_prompt or ''))}"
    cached_response = llm_cache.get(cache_key)
    if cached_response: return cached_response

    generated_text = None
    if GROQ_API_KEY:
        generated_text = _generate_with_groq(prompt, system_prompt)
        if generated_text:
            _active_provider = "groq"
            llm_cache.set(cache_key, generated_text)
            return generated_text

    generated_text = _generate_with_ollama(prompt, system_prompt)
    if generated_text:
        _active_provider = "ollama"
        llm_cache.set(cache_key, generated_text)
        return generated_text
    return None

def get_active_provider() -> str: return _active_provider

def get_llm_status() -> Dict:
    groq_available = bool(GROQ_API_KEY)
    return {
        "active_provider": _active_provider,
        "groq": {"configured": groq_available, "healthy": check_groq_health() if groq_available else False, "model": GROQ_MODEL},
        "ollama": {"configured": True, "healthy": check_ollama_health(), "model": OLLAMA_MODEL, "url": OLLAMA_API_URL}
    }

def parse_json_from_text(text: str) -> Optional[Dict]:
    if not text: return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[cleaned.index("\n") + 1:] if "\n" in cleaned else cleaned
        if cleaned.rstrip().endswith("```"): cleaned = cleaned.rstrip()[:-3].rstrip()
    try: return json.loads(cleaned)
    except:
        import re
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group(0))
            except: return None
    return None

@traceable(name="analyze_candidate_match", run_type="chain")
def analyze_candidate_match(request: MatchAnalysisRequest) -> Optional[MatchAnalysisResponse]:
    system_prompt = """You are an expert HR recruiter. Analyze the resume against the job description.
    Respond with ONLY valid JSON in this format:
    {"strengths": ["s1", "s2"], "weaknesses": ["w1"], "missing_skills": ["m1"], "recommendation": "Strong Hire|Consider|Reject", "explanation": "1-2 sentences", "match_score": 0.75}"""
    
    prompt = f"CANDIDATE RESUME:\n{request.candidate_resume}\n\nJOB DESCRIPTION:\n{request.job_description}\n\nProvide analysis."
    response_text = generate_text(prompt, system_prompt)
    if not response_text: return None
    json_data = parse_json_from_text(response_text)
    if not json_data: return None
    try: return MatchAnalysisResponse(**json_data)
    except Exception as e: return None

@traceable(name="generate_interview_questions", run_type="chain")
def generate_interview_questions(request: InterviewQuestionsRequest) -> Optional[InterviewQuestionsResponse]:
    level_context = {"fresher": "Entry-level. Focus on fundamentals.", "intermediate": "Mid-level. Balance theory and practice.", "experienced": "Senior. Focus on architecture and leadership."}
    level_desc = level_context.get(request.candidate_level or "intermediate", level_context["intermediate"])

    system_prompt = f"""You are an expert technical interviewer. Generate targeted interview questions for a {request.job_title} position.
    Candidate Level: {request.candidate_level or 'intermediate'}. {level_desc}
    
    Respond with ONLY valid JSON in this format:
    { 
        "technical_questions": ["q1", "q2", "q3", "q4"],
        "behavioral_questions": ["q1", "q2", "q3"],
        "practical_tasks": ["t1", "t2"]
    } 
    
    Instructions:
    - Technical Questions: Create 4 deep technical questions. 2 questions should test the depth of skills the candidate ALREADY has. 2 questions MUST probe the MISSING REQUIRED SKILLS to assess their ability to adapt.
    - Behavioral Questions: 3 STAR-method questions.
    - Practical Tasks: 2 hands-on tasks relevant to the Job Description.
    Return ONLY the JSON object."""

    prompt = f"""
    Job Description:
    {request.job_description or 'N/A'}
    
    Required Skills for the Role:
    {', '.join(request.required_skills)}
    
    Candidate's Current Skills (from Resume):
    {', '.join(request.candidate_skills)}
    
    Missing Required Skills (Candidate lacks these, probe them):
    {', '.join(request.missing_skills)}
    
    Candidate Resume:
    {request.candidate_resume}
    
    Generate the interview questions based on the instructions.
    """

    response_text = generate_text(prompt, system_prompt)
    if not response_text: return None
    json_data = parse_json_from_text(response_text)
    if not json_data: return None

    try:
        technical = json_data.get("technical_questions", [])
        behavioral = json_data.get("behavioral_questions", [])
        practical = json_data.get("practical_tasks", [])

        if technical and isinstance(technical[0], dict): technical = [q.get("question", str(q)) for q in technical]
        if behavioral and isinstance(behavioral[0], dict): behavioral = [q.get("question", str(q)) for q in behavioral]
        if practical and isinstance(practical[0], dict): practical = [t.get("description", t.get("question", str(t))) for t in practical]

        return InterviewQuestionsResponse(technical_questions=technical, behavioral_questions=behavioral, practical_tasks=practical)
    except Exception: return None

@traceable(name="generate_outreach_email", run_type="chain")
def generate_outreach_email(request: OutreachEmailRequest) -> tuple[Optional[OutreachEmailResponse], Optional[str]]:
    email_instructions = {
        "interview_invite": "Write a warm interview invitation email.", "rejection": "Write a respectful rejection email.",
        "cold_outreach": "Write an engaging cold outreach email.", "offer": "Write an enthusiastic job offer email.",
        "follow_up": "Write a friendly follow-up email.", "thank_you": "Write a sincere thank-you email."
    }
    instruction = email_instructions.get(request.email_type, "Write a professional email.")

    system_prompt = f"""You are a world-class recruiter. {instruction}
    Respond with ONLY valid JSON in this format:
    { "subject_line": "Subject line", "email_body": "Greeting\\n\\nParagraph 1\\n\\nParagraph 2\\n\\nSign-off,\\nName"} 
    Use \\n\\n to separate paragraphs. Keep it 150-250 words.

    The email must be complete and ready to send exactly as written — never use
    bracket placeholders like [Company Name], [Your Name], [Date], or [Insert X],
    and never write "N/A" or "TBD". Only mention a detail (company, contact
    name, interview date/time/location) if it is actually given to you below.
    If interview scheduling details are not given, say the exact time will be
    shared separately instead of naming a placeholder date or time."""

    details = [f"Candidate Name: {request.candidate_name}", f"Job Title: {request.job_title}"]
    if request.company_name:
        details.append(f"Company: {request.company_name}")
    if request.contact_person:
        details.append(f"Sign the email from: {request.contact_person}")
    if request.email_type == "interview_invite":
        schedule = [p for p in [request.interview_date, request.interview_time, request.interview_location] if p]
        if schedule:
            details.append(
                f"Interview Details — Date: {request.interview_date or 'not yet set'}, "
                f"Time: {request.interview_time or 'not yet set'}, "
                f"Location: {request.interview_location or 'not yet set'}"
            )
        else:
            details.append("Interview scheduling details are not decided yet — say you'll follow up separately to find a time.")

    prompt = "\n    ".join(details) + "\n    Make it personalized and professional."

    response_text = generate_text(prompt, system_prompt)
    if not response_text: return None, None
    json_data = parse_json_from_text(response_text)
    if not json_data: return None, response_text
    try:
        parsed = OutreachEmailResponse(**json_data)
    except Exception:
        return None, response_text
    
    
    
    
    
    
    
    if not parsed.subject_line.strip() or not parsed.email_body.strip():
        return None, response_text
    return parsed, response_text

@traceable(name="generate_job_description", run_type="chain")
def generate_job_description(request: JobDescriptionRequest) -> Optional[JobDescriptionResponse]:
    system_prompt = """You are an expert HR manager. Create a compelling job description.
    Respond with ONLY valid JSON in this format:
    {"job_description": "Full JD text here...", "required_skills": ["skill1", "skill2"], "nice_to_have_skills": ["skill1", "skill2"]}"""
    
    prompt = f"""
    Position: {request.job_title}
    Company: {request.company_name or 'A growing tech company'}
    Summary: {request.job_shorthand}
    Required skills: {', '.join(request.required_skills) if request.required_skills else 'Use industry standard'}
    Include role overview, responsibilities, qualifications, and benefits.
    """
    
    response_text = generate_text(prompt, system_prompt)
    if not response_text: return None
    json_data = parse_json_from_text(response_text)
    if not json_data: return None
    try: return JobDescriptionResponse(**json_data)
    except Exception: return None