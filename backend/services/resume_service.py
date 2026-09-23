from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ai.extraction import extract_text_from_pdf, parse_resume
from models import Resume
from .storage_service import StoredFile, get_storage
from core.utils import logger, safe_json_dumps, safe_json_loads


class ResumeService:
    @staticmethod
    def parse_pdf(file_path: str) -> Optional[Dict]:
        """Text extraction (with OCR fallback for scans) and field parsing.
        Returns None when no text could be recovered at all."""
        text, used_ocr = extract_text_from_pdf(file_path)
        if not text:
            return None
        return {"extracted_text": text, "metadata": parse_resume(text, used_ocr=used_ocr)}

    @staticmethod
    def create_pending(
        db: Session,
        user_id: int,
        filename: str,
        stored: StoredFile,
        content_hash: str,
        candidate_name: Optional[str] = None,
        candidate_email: Optional[str] = None,
        candidate_phone: Optional[str] = None,
    ) -> Resume:
        """Records the upload right away (is_processed stays False). Parsing and
        embedding happen in the worker, see tasks.process_resume_job."""
        resume = Resume(
            user_id=user_id,
            file_name=filename,
            file_path=stored.key,
            storage_backend=stored.backend,
            mime_type="application/pdf",
            size_bytes=stored.size,
            content_hash=content_hash,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            is_processed=False,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume

    @staticmethod
    def apply_parsed(resume: Resume, processed: Dict, overwrite_contact: bool) -> None:
        """overwrite_contact=True for HR uploads (details come from the PDF).
        False for public applications, where the candidate typed their own name,
        email and phone into the form and those win over anything we parse."""
        meta = processed["metadata"]
        if overwrite_contact:
            resume.candidate_name = meta.get("candidate_name") or resume.candidate_name
            resume.candidate_email = meta.get("email") or resume.candidate_email
            resume.candidate_phone = meta.get("phone") or resume.candidate_phone
            resume.name_confidence = meta.get("name_confidence")
        else:
            resume.name_confidence = 1.0
        resume.extracted_text = processed["extracted_text"]
        resume.experience_years = meta.get("experience_years")
        resume.skills = safe_json_dumps(meta.get("skills", []))
        resume.education = safe_json_dumps(meta.get("education", []))
        resume.extraction_meta = safe_json_dumps(meta.get("extraction_meta", {}))
        resume.processing_error = None
        resume.processed_at = datetime.utcnow()

    @staticmethod
    def find_by_hash(db: Session, user_id: int, content_hash: str) -> Optional[Resume]:
        return db.query(Resume).filter(Resume.user_id == user_id, Resume.content_hash == content_hash).first()

    @staticmethod
    def get_resume_by_id(db: Session, resume_id: int, user_id: int) -> Optional[Resume]:
        return db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()

    @staticmethod
    def get_user_resumes(db: Session, user_id: int, limit: int = 500) -> List[Resume]:
        return db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_resume_statistics(db: Session, user_id: int) -> Dict:
        rows = db.query(Resume.skills, Resume.experience_years).filter(Resume.user_id == user_id).all()
        total_resumes = len(rows)

        experiences = [r.experience_years for r in rows if r.experience_years is not None]
        avg_experience = round(sum(experiences) / len(experiences), 1) if experiences else 0.0

        skill_counts: Dict[str, int] = {}
        for r in rows:
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
        resume = ResumeService.get_resume_by_id(db, resume_id, user_id)
        if not resume:
            return False
        storage_key, backend = resume.file_path, resume.storage_backend or "local"
        try:
            db.delete(resume)  # cascades to chunks, applications, search results, AI outputs
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"delete_resume failed for {resume_id}: {e}")
            return False
        try:
            get_storage(backend).delete(storage_key)
        except Exception as e:
            logger.warning(f"Stored file {storage_key} could not be deleted: {e}")
        return True
