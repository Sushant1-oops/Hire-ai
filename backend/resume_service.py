"""
Resume service for handling resume uploads, PDF parsing, and text extraction.
Robust name/email/phone/skills extraction for production use.
"""

import os
import re
import shutil
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from datetime import datetime
import pdfplumber
from sqlalchemy.orm import Session
from models import Resume
from utils import (
    logger,
    ensure_directory,
    extract_skills_from_text,
    extract_experience_years,
    extract_education,
    clean_text,
    safe_json_dumps,
    validate_email,
    validate_phone,
)
from search_service import SemanticSearchService


# ==================== STOP WORDS for name detection ====================
_NAME_STOP_WORDS = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary",
    "objective", "experience", "education", "skills", "contact",
    "phone", "email", "address", "linkedin", "github", "portfolio",
    "page", "professional", "personal", "details", "information",
    "references", "available", "upon", "request",
}


class ResumeService:
    """Service for handling resume uploads and processing."""

    # Configuration
    RESUME_STORAGE_DIR = "data/resumes"
    ALLOWED_EXTENSIONS = {".pdf"}
    MAX_FILE_SIZE_MB = 20

    def __init__(self):
        """Initialize resume service."""
        ensure_directory(self.RESUME_STORAGE_DIR)
        logger.info(f"✓ Resume service initialized. Storage: {self.RESUME_STORAGE_DIR}")

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Optional[str]:
        """
        Extract text from PDF file using pdfplumber.
        Does NOT add page markers to avoid interfering with name detection.
        """
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n{page_text}"

            if not text.strip():
                logger.warning(f"No text extracted from {file_path}")
                return None

            logger.info(f"✓ Extracted {len(text)} characters from PDF")
            return text.strip()

        except Exception as e:
            logger.error(f"✗ Error extracting PDF: {str(e)}")
            return None

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        """
        Robustly extract candidate name from resume text.
        Uses multiple heuristics in priority order.
        """
        lines = text.strip().split('\n')
        clean_lines = [l.strip() for l in lines if l.strip()]

        if not clean_lines:
            return None

        # Strategy 1: Look for explicit "Name:" labels in first 15 lines
        for line in clean_lines[:15]:
            name_label_match = re.match(
                r'^(?:name|full\s*name|candidate\s*name)\s*[:|\-]\s*(.+)',
                line, re.IGNORECASE
            )
            if name_label_match:
                name = name_label_match.group(1).strip()
                if 2 < len(name) < 60:
                    return name

        # Strategy 2: First line that looks like a person name
        for line in clean_lines[:8]:
            line_clean = line.strip()

            # Skip empty or too-long lines
            if not line_clean or len(line_clean) > 60 or len(line_clean) < 3:
                continue

            # Skip lines with emails, URLs, phone numbers
            if '@' in line_clean or 'http' in line_clean.lower():
                continue
            if re.search(r'\d{5,}', line_clean):  # phone-like numbers
                continue

            # Skip lines that are clearly section headers or keywords
            line_lower = line_clean.lower()
            if any(stop in line_lower for stop in _NAME_STOP_WORDS):
                continue

            # Skip lines with too many special characters
            alpha_chars = sum(c.isalpha() or c.isspace() or c == '.' for c in line_clean)
            if len(line_clean) > 0 and alpha_chars / len(line_clean) < 0.85:
                continue

            # A name should be 1-4 words
            words = line_clean.split()
            if 1 <= len(words) <= 5:
                # Check that most words start with uppercase (typical for names)
                upper_starts = sum(1 for w in words if w[0].isupper() or w[0] == '.')
                if upper_starts >= len(words) * 0.5:
                    # Remove common prefixes
                    name = line_clean
                    for prefix in ['Mr.', 'Ms.', 'Mrs.', 'Dr.', 'Prof.', 'Rev.']:
                        if name.startswith(prefix):
                            name = name[len(prefix):].strip()
                            break
                    if len(name) > 2:
                        return name

        # Strategy 3: Extract from email prefix
        email_match = re.search(r'([a-zA-Z0-9_.+-]+)@', text)
        if email_match:
            prefix = email_match.group(1)
            # Convert dots/underscores to spaces and title-case
            name = re.sub(r'[._]', ' ', prefix).title()
            # Remove numbers
            name = re.sub(r'\d+', '', name).strip()
            if len(name) > 2:
                return name

        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Extract email address from text."""
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        match = re.search(email_pattern, text)
        if match:
            email = match.group(0).lower().rstrip('.')
            return email
        return None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        """
        Extract phone number from text.
        Supports US, Indian (+91), and international formats.
        """
        phone_patterns = [
            # Indian: +91-XXXXX-XXXXX or +91 XXXXX XXXXX
            r'(?:\+91[\s\-.]?)?\d{5}[\s\-.]?\d{5}',
            # Indian: +91-XXXX-XXXXXX
            r'(?:\+91[\s\-.]?)?\d{4}[\s\-.]?\d{6}',
            # US: (XXX) XXX-XXXX or XXX-XXX-XXXX
            r'(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}',
            # International: +XX XXXX XXXX
            r'\+\d{1,4}[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}[\s\-.]?\d{0,5}',
            # Simple 10-digit number
            r'\b\d{10}\b',
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0).strip()
                # Validate: must have at least 10 digits
                digits = re.sub(r'\D', '', phone)
                if 10 <= len(digits) <= 15:
                    return phone
        return None

    @classmethod
    def parse_resume_metadata(cls, text: str) -> Dict:
        """
        Parse resume text to extract structured metadata.
        Returns dict with name, email, phone, skills, experience_years, education.
        """
        metadata = {
            "name": None,
            "candidate_name": None,
            "email": None,
            "phone": None,
            "skills": [],
            "experience_years": None,
            "education": [],
        }

        # Extract name
        name = cls._extract_name(text)
        if name:
            metadata["name"] = name
            metadata["candidate_name"] = name

        # Extract email
        metadata["email"] = cls._extract_email(text)

        # Extract phone
        metadata["phone"] = cls._extract_phone(text)

        # Extract skills
        metadata["skills"] = extract_skills_from_text(text)

        # Extract experience
        metadata["experience_years"] = extract_experience_years(text)

        # Extract education
        metadata["education"] = extract_education(text)

        return metadata

    def save_resume_file(
        self,
        file_path: str,
        storage_filename: str
    ) -> Tuple[bool, str]:
        """
        Save uploaded resume file to storage.
        Returns: (success: bool, storage_path: str)
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Source file not found: {file_path}")
                return False, ""

            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                logger.error(f"File too large: {file_size_mb}MB")
                return False, ""

            # Generate storage path with safe timestamp
            timestamp = datetime.now().isoformat().replace(':', '-')
            storage_path = os.path.join(
                self.RESUME_STORAGE_DIR,
                f"{timestamp}_{storage_filename}"
            )

            shutil.copy2(file_path, storage_path)
            logger.info(f"✓ Resume saved to {storage_path}")
            return True, storage_path

        except Exception as e:
            logger.error(f"✗ Error saving resume: {str(e)}")
            return False, ""

    @classmethod
    def process_resume(cls, file_path: str) -> Optional[Dict]:
        """
        Process resume file: extract text and parse metadata.
        Returns dict with extracted_text and metadata.
        """
        service = cls()

        # Extract text from PDF
        extracted_text = service.extract_text_from_pdf(file_path)
        if not extracted_text:
            logger.error("Failed to extract text from resume")
            return None

        # Parse metadata
        metadata = service.parse_resume_metadata(extracted_text)

        return {
            "extracted_text": extracted_text,
            "metadata": metadata,
            "text_length": len(extracted_text),
            "cleaned_text": clean_text(extracted_text),
        }

    def create_resume_record(
        self,
        db: Session,
        user_id: int,
        file_path: str,
        storage_path: str,
        processed_data: Dict
    ) -> Optional[Resume]:
        """
        Create resume database record.
        """
        try:
            metadata = processed_data.get("metadata", {})

            resume = Resume(
                user_id=user_id,
                file_name=os.path.basename(file_path),
                file_path=storage_path,
                candidate_name=metadata.get("candidate_name"),
                candidate_email=metadata.get("email"),
                candidate_phone=metadata.get("phone"),
                extracted_text=processed_data.get("extracted_text"),
                experience_years=metadata.get("experience_years"),
                skills=safe_json_dumps(metadata.get("skills", [])),
                education=safe_json_dumps(metadata.get("education", [])),
                is_processed=True,
            )

            db.add(resume)
            db.commit()
            db.refresh(resume)

            logger.info(f"✓ Resume record created: ID={resume.id}, Name={resume.candidate_name}")
            return resume

        except Exception as e:
            logger.error(f"✗ Error creating resume record: {str(e)}")
            db.rollback()
            return None

    @staticmethod
    def get_resume_by_id(db: Session, resume_id: int, user_id: int) -> Optional[Resume]:
        """Get resume by ID for a specific user."""
        return db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

    @staticmethod
    def get_user_resumes(db: Session, user_id: int, limit: int = 500) -> list:
        """Get all resumes for a user."""
        return db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(Resume.created_at.desc()).limit(limit).all()

    @staticmethod
    def delete_resume(db: Session, resume_id: int, user_id: int) -> bool:
        """Delete a resume, all related records, and rebuild search index."""
        try:
            resume = db.query(Resume).filter(
                Resume.id == resume_id,
                Resume.user_id == user_id
            ).first()

            if not resume:
                return False

            from models import SearchResult, AICandidateMatch, InterviewQuestions, OutreachEmail

            # Delete all related records
            db.query(SearchResult).filter(SearchResult.resume_id == resume_id).delete()
            db.query(AICandidateMatch).filter(AICandidateMatch.resume_id == resume_id).delete()
            db.query(InterviewQuestions).filter(InterviewQuestions.resume_id == resume_id).delete()
            db.query(OutreachEmail).filter(OutreachEmail.resume_id == resume_id).delete()

            # Delete file
            if os.path.exists(resume.file_path):
                os.remove(resume.file_path)
                logger.info(f"✓ Deleted resume file: {resume.file_path}")

            # Delete record
            db.delete(resume)
            db.commit()
            logger.info(f"✓ Deleted resume record: ID={resume_id}")

            # Clear cache and rebuild index
            for cache_file in ["data/resume_embeddings.pkl", "data/faiss_index.bin"]:
                if os.path.exists(cache_file):
                    os.remove(cache_file)

            try:
                search_service = SemanticSearchService()
                search_service.rebuild_index(db, user_id)
                logger.info(f"✓ Rebuilt search index after deleting resume {resume_id}")
            except Exception as e:
                logger.warning(f"⚠ Failed to rebuild search index: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"✗ Error deleting resume: {str(e)}")
            db.rollback()
            return False

    @staticmethod
    def get_resume_statistics(db: Session, user_id: int) -> Dict:
        """Get statistics for user's resumes."""
        import json

        resumes = db.query(Resume).filter(Resume.user_id == user_id).all()

        if not resumes:
            return {
                "total_resumes": 0,
                "total_skills": 0,
                "avg_experience": 0,
                "top_skills": [],
                "experience_distribution": {}
            }

        total_resumes = len(resumes)
        all_skills = []
        total_experience = 0
        experience_count = 0
        experience_buckets = {}

        for resume in resumes:
            skills = json.loads(resume.skills) if resume.skills else []
            all_skills.extend(skills)

            if resume.experience_years is not None:
                total_experience += resume.experience_years
                experience_count += 1
                # Bucket into ranges
                yrs = resume.experience_years
                if yrs < 2:
                    bucket = "0-2 yrs"
                elif yrs < 5:
                    bucket = "2-5 yrs"
                elif yrs < 10:
                    bucket = "5-10 yrs"
                else:
                    bucket = "10+ yrs"
                experience_buckets[bucket] = experience_buckets.get(bucket, 0) + 1

        # Count skill frequencies
        skill_counts = {}
        for skill in all_skills:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

        top_skills = sorted(
            skill_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:15]

        return {
            "total_resumes": total_resumes,
            "total_skills": len(skill_counts),
            "avg_experience": round(total_experience / experience_count, 1) if experience_count > 0 else 0,
            "top_skills": [{"skill": skill, "count": count} for skill, count in top_skills],
            "experience_distribution": experience_buckets
        }


if __name__ == "__main__":
    logger.info("Resume service test")
    service = ResumeService()
    print(f"Storage directory: {service.RESUME_STORAGE_DIR}")
