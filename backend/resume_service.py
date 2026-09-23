
import os
import re
import shutil
from typing import Optional, Dict, Tuple
from datetime import datetime
import pdfplumber
from sqlalchemy.orm import Session
from models import Resume
from utils import logger, ensure_directory, extract_skills_from_text, extract_experience_years, extract_education, safe_json_dumps, safe_json_loads

_NAME_STOP_WORDS = {"resume", "curriculum", "vitae", "cv", "profile", "summary", "objective", "experience", "education", "skills", "contact", "phone", "email", "address", "linkedin", "github", "portfolio", "page", "professional", "personal", "details", "information", "references", "available", "upon", "request"}

class ResumeService:
    RESUME_STORAGE_DIR = "data/resumes"
    ALLOWED_EXTENSIONS = {".pdf"}
    MAX_FILE_SIZE_MB = 20

    def __init__(self):
        ensure_directory(self.RESUME_STORAGE_DIR)

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Optional[str]:
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if page_text: text += f"\n{page_text}"
            if not text.strip(): return None
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[•●◆▪►]', '-', text)
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF: {str(e)}")
            return None

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        lines = text.strip().split('\n')
        clean_lines = [l.strip() for l in lines if l.strip()]
        if not clean_lines: return None
        for line in clean_lines[:8]:
            if not line or len(line) > 60 or len(line) < 3 or '@' in line or 'http' in line.lower() or re.search(r'\d{5,}', line): continue
            if any(stop in line.lower() for stop in _NAME_STOP_WORDS): continue
            words = line.split()
            if 1 <= len(words) <= 5 and sum(1 for w in words if w[0].isupper()) >= len(words) * 0.5:
                return line
        email_match = re.search(r'([a-zA-Z0-9_.+-]+)@', text)
        if email_match:
            name = re.sub(r'[._]', ' ', email_match.group(1)).title()
            name = re.sub(r'\d+', '', name).strip()
            if len(name) > 2: return name
        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        return match.group(0).lower().rstrip('.') if match else None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        phone_patterns = [r'(?:\+91[\s\-.]?)?\d{5}[\s\-.]?\d{5}', r'(?:\+91[\s\-.]?)?\d{4}[\s\-.]?\d{6}', r'(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}']
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                digits = re.sub(r'\D', '', match.group(0))
                if 10 <= len(digits) <= 15: return match.group(0).strip()
        return None

    @classmethod
    def parse_resume_metadata(cls, text: str) -> Dict:
        name = cls._extract_name(text)
        return {
            "name": name, "candidate_name": name,
            "email": cls._extract_email(text), "phone": cls._extract_phone(text),
            "skills": extract_skills_from_text(text),
            "experience_years": extract_experience_years(text),
            "education": extract_education(text)
        }

    def save_resume_file(self, file_path: str, storage_filename: str) -> Tuple[bool, str]:
        try:
            if not os.path.exists(file_path): return False, ""
            if os.path.getsize(file_path) / (1024 * 1024) > self.MAX_FILE_SIZE_MB: return False, ""
            timestamp = datetime.now().isoformat().replace(':', '-')
            storage_path = os.path.join(self.RESUME_STORAGE_DIR, f"{timestamp}_{storage_filename}")
            shutil.copy2(file_path, storage_path)
            return True, storage_path
        except Exception: return False, ""

    @classmethod
    def process_resume(cls, file_path: str) -> Optional[Dict]:
        service = cls()
        extracted_text = service.extract_text_from_pdf(file_path)
        if not extracted_text: return None
        cleaned_text = ' '.join(extracted_text.split())
        metadata = service.parse_resume_metadata(extracted_text)
        return {"extracted_text": extracted_text, "metadata": metadata, "text_length": len(extracted_text), "cleaned_text": cleaned_text}

    def create_resume_record(self, db: Session, user_id: int, file_path: str, storage_path: str, processed_data: Dict) -> Optional[Resume]:
        try:
            metadata = processed_data.get("metadata", {})
            resume = Resume(
                user_id=user_id, file_name=os.path.basename(file_path), file_path=storage_path,
                candidate_name=metadata.get("candidate_name"), candidate_email=metadata.get("email"),
                candidate_phone=metadata.get("phone"), extracted_text=processed_data.get("extracted_text"),
                experience_years=metadata.get("experience_years"), skills=safe_json_dumps(metadata.get("skills", [])),
                education=safe_json_dumps(metadata.get("education", [])), is_processed=True
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            return resume
        except Exception as e:
            db.rollback()
            return None

    def create_pending_resume_record(self, db: Session, user_id: int, filename: str, storage_path: str,
                                      candidate_name: str, candidate_email: str, candidate_phone: Optional[str]) -> Optional[Resume]:
        
        try:
            resume = Resume(
                user_id=user_id, file_name=filename, file_path=storage_path,
                candidate_name=candidate_name, candidate_email=candidate_email, candidate_phone=candidate_phone,
                is_processed=False,
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            return resume
        except Exception:
            db.rollback()
            return None

    @staticmethod
    def get_resume_by_id(db: Session, resume_id: int, user_id: int) -> Optional[Resume]:
        return db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()

    @staticmethod
    def get_user_resumes(db: Session, user_id: int, limit: int = 500) -> list:
        return db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_resume_statistics(db: Session, user_id: int) -> Dict:
        
        resumes = db.query(Resume).filter(Resume.user_id == user_id).all()
        total_resumes = len(resumes)

        experiences = [r.experience_years for r in resumes if r.experience_years is not None]
        avg_experience = round(sum(experiences) / len(experiences), 1) if experiences else 0.0

        skill_counts: Dict[str, int] = {}
        for r in resumes:
            for skill in safe_json_loads(r.skills, []) or []:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        top_skills = [
            {"skill": skill, "count": count}
            for skill, count in sorted(skill_counts.items(), key=lambda kv: kv[1], reverse=True)
        ][:10]

        bands = [("0-2 yrs", 0, 2), ("2-5 yrs", 2, 5), ("5-8 yrs", 5, 8), ("8+ yrs", 8, float("inf"))]
        distribution = []
        for label, low, high in bands:
            count = sum(1 for e in experiences if low <= e < high)
            if count:
                distribution.append({"range": label, "count": count})

        return {
            "total_resumes": total_resumes,
            "avg_experience": avg_experience,
            "top_skills": top_skills,
            "experience_distribution": distribution,
        }

    @staticmethod
    def delete_resume(db: Session, resume_id: int, user_id: int) -> bool:
        try:
            resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()
            if not resume: return False
            from models import SearchResult, AICandidateMatch, InterviewQuestions, OutreachEmail
            db.query(SearchResult).filter(SearchResult.resume_id == resume_id).delete()
            db.query(AICandidateMatch).filter(AICandidateMatch.resume_id == resume_id).delete()
            db.query(InterviewQuestions).filter(InterviewQuestions.resume_id == resume_id).delete()
            db.query(OutreachEmail).filter(OutreachEmail.resume_id == resume_id).delete()
            if os.path.exists(resume.file_path): os.remove(resume.file_path)
            db.delete(resume)
            db.commit()
            try:
                from search_service import get_search_service
                search_service = get_search_service()
                search_service.remove_resume(resume_id)
                search_service.save_index()
            except: pass
            return True
        except Exception:
            db.rollback()
            return False