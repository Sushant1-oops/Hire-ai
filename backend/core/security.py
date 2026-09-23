import hashlib
import os
import re
from dataclasses import dataclass

from core.config import MAX_UPLOAD_MB


class UploadRejected(ValueError):
    pass


@dataclass
class ValidatedUpload:
    filename: str
    data: bytes
    sha256: str
    size: int


def safe_filename(name: str) -> str:
    """Basename only, restricted characters, bounded length. The stored object
    key never contains the client's filename, this is just for display."""
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._ \-()]", "_", base)
    base = re.sub(r"_{2,}", "_", base).strip(" .")
    if not base:
        base = "resume.pdf"
    stem, ext = os.path.splitext(base)
    return stem[:80] + ext[:10]


async def read_pdf_upload(upload, max_mb: int = MAX_UPLOAD_MB) -> ValidatedUpload:
    """Reads at most max_mb + 1 byte (so an oversized upload is rejected without
    being pulled fully into memory), then checks extension and PDF magic bytes."""
    filename = safe_filename(upload.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise UploadRejected("Only PDF files are supported")
    limit = max_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise UploadRejected(f"File is larger than {max_mb} MB")
    if len(data) < 100:
        raise UploadRejected("File is empty or too small to be a resume")
    if not data.startswith(b"%PDF-"):
        raise UploadRejected("File does not look like a valid PDF")
    return ValidatedUpload(filename=filename, data=data, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
