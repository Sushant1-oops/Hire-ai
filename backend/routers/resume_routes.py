from typing import List

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

import core.audit as audit
from core.config import MAX_BATCH_FILES
from core.database import get_db
from auth.deps import get_current_user, user_limit
from models import User
from services.queue_service import enqueue_resume_processing
from services.resume_service import ResumeService
from services.search_service import reindex_user_resumes
from core.security import UploadRejected, ValidatedUpload, read_pdf_upload
from services.storage_service import StorageError, get_storage
from core.utils import fail, safe_json_loads, success_response

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _ingest(db: Session, user: User, upload: ValidatedUpload, request: Request) -> dict:
    """Dedup by file hash inside the tenant, store the PDF, create the pending
    record, queue the processing job."""
    existing = ResumeService.find_by_hash(db, user.id, upload.sha256)
    if existing:
        return {"resume_id": existing.id, "candidate_name": existing.candidate_name,
                "processing_status": existing.processing_status, "duplicate": True, "file": upload.filename}
    stored = get_storage().save_bytes(upload.data, user.id)
    resume = ResumeService.create_pending(db, user.id, upload.filename, stored, upload.sha256)
    enqueue_resume_processing(resume.id)
    audit.record(db, "resume_uploaded", user_id=user.id, resource_type="resume", resource_id=resume.id,
                 request=request, size=upload.size, backend=stored.backend)
    return {"resume_id": resume.id, "candidate_name": None, "processing_status": "pending", "duplicate": False, "file": upload.filename}


@router.post("/upload")
async def upload_resume(request: Request, file: UploadFile = File(...),
                        current_user: User = Depends(user_limit("resume_upload", 60, 3600)), db: Session = Depends(get_db)):
    try:
        upload = await read_pdf_upload(file)
    except UploadRejected as e:
        return fail(400, str(e))
    try:
        data = await run_in_threadpool(_ingest, db, current_user, upload, request)
    except StorageError as e:
        return fail(502, "Could not store the resume file", str(e))
    message = "This resume was already uploaded" if data["duplicate"] else "Resume uploaded. Parsing continues in the background."
    return success_response(data=data, message=message)


@router.post("/upload-batch")
async def upload_resumes_batch(request: Request, files: List[UploadFile] = File(...),
                               current_user: User = Depends(user_limit("resume_upload", 60, 3600)), db: Session = Depends(get_db)):
    if len(files) > MAX_BATCH_FILES:
        return fail(400, f"Upload at most {MAX_BATCH_FILES} files at a time")
    results = {"successful": [], "failed": []}
    for file in files:
        try:
            upload = await read_pdf_upload(file)
        except UploadRejected as e:
            results["failed"].append({"file": file.filename, "error": str(e)})
            continue
        try:
            item = await run_in_threadpool(_ingest, db, current_user, upload, request)
            results["successful"].append(item)
        except Exception as e:
            db.rollback()
            results["failed"].append({"file": upload.filename, "error": "Could not store or queue this file"})
    return success_response(data=results, message=f"Accepted {len(results['successful'])} of {len(files)} resumes")


@router.get("")
def list_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resumes = ResumeService.get_user_resumes(db, current_user.id)
    return success_response(data=[{
        "id": r.id, "candidate_name": r.candidate_name, "candidate_email": r.candidate_email,
        "candidate_phone": r.candidate_phone, "skills": safe_json_loads(r.skills, []),
        "experience_years": r.experience_years, "created_at": r.created_at.isoformat(),
        "processing_status": r.processing_status, "processing_error": r.processing_error,
        "needs_review": bool((safe_json_loads(r.extraction_meta, {}) or {}).get("needs_review")),
    } for r in resumes])


@router.get("/{resume_id}")
def get_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        return fail(404, "Resume not found")
    meta = safe_json_loads(resume.extraction_meta, {}) or {}
    return success_response(data={
        "id": resume.id, "candidate_name": resume.candidate_name, "candidate_email": resume.candidate_email,
        "candidate_phone": resume.candidate_phone, "skills": safe_json_loads(resume.skills, []),
        "experience_years": resume.experience_years, "education": safe_json_loads(resume.education, []),
        "extracted_text": resume.extracted_text[:2000] if resume.extracted_text else "",
        "created_at": resume.created_at.isoformat(),
        "processing_status": resume.processing_status, "processing_error": resume.processing_error,
        "name_confidence": resume.name_confidence,
        "needs_review": bool(meta.get("needs_review")),
        "used_ocr": bool(meta.get("used_ocr")),
        "unrecognised_skills": meta.get("unrecognised_skills", []),
    })


@router.get("/{resume_id}/file")
def download_resume_file(resume_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The original PDF, streamed through the API after a tenant check. Storage
    URLs (Cloudinary or local) are never given to the browser."""
    resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        return fail(404, "Resume not found")
    try:
        data = get_storage(resume.storage_backend or "local").read_bytes(resume.file_path)
    except StorageError as e:
        return fail(502, "The stored file could not be retrieved", str(e))
    audit.record(db, "resume_downloaded", user_id=current_user.id, resource_type="resume", resource_id=resume.id, request=request)
    safe_name = (resume.file_name or "resume.pdf").replace('"', "")
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@router.post("/{resume_id}/reprocess")
def reprocess_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
    if not resume:
        return fail(404, "Resume not found")
    resume.is_processed = False
    resume.processing_error = None
    db.commit()
    enqueue_resume_processing(resume.id)
    return success_response(data={"resume_id": resume.id, "processing_status": "pending"}, message="Reprocessing queued")


@router.post("/reprocess-pending")
def reprocess_pending(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-queues this tenant's resumes that never finished (for example after a Redis restart lost the queue)."""
    stuck = [r for r in ResumeService.get_user_resumes(db, current_user.id, limit=1000)
             if not r.is_processed and not r.processing_error]
    for resume in stuck:
        enqueue_resume_processing(resume.id)
    return success_response(data={"queued": len(stuck)}, message=f"Queued {len(stuck)} resumes")


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not ResumeService.delete_resume(db, resume_id, current_user.id):
        return fail(404, "Resume not found")
    audit.record(db, "resume_deleted", user_id=current_user.id, resource_type="resume", resource_id=resume_id, request=request)
    return success_response(message="Resume deleted successfully")


@router.post("/reindex")
def reindex_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rebuilds this tenant's vectors from stored text. Use after changing the
    chunking/embedding strategy, or once when migrating from the old FAISS index."""
    count = reindex_user_resumes(db, current_user.id)
    return success_response(data={"reindexed": count}, message=f"Search index rebuilt for {count} resumes")
