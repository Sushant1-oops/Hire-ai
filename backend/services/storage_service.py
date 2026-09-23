import io
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import requests

import core.config as config
from core.utils import logger


@dataclass
class StoredFile:
    key: str
    backend: str
    size: int


class StorageError(RuntimeError):
    pass


def _retry(fn, attempts: int = 3, base_delay: float = 0.6):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    raise StorageError(str(last)) from last


class LocalStorage:
    backend = "local"

    def __init__(self, base_dir: str = config.LOCAL_STORAGE_DIR):
        self.base_dir = os.path.realpath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        path = os.path.realpath(os.path.join(self.base_dir, key))
        if not path.startswith(self.base_dir + os.sep):
            raise StorageError("invalid storage key")
        return path

    def save_bytes(self, data: bytes, user_id: int) -> StoredFile:
        key = f"{user_id}/{uuid.uuid4().hex}.pdf"
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return StoredFile(key=key, backend=self.backend, size=len(data))

    def read_bytes(self, key: str) -> bytes:
        try:
            with open(self._path(key), "rb") as f:
                return f.read()
        except FileNotFoundError as e:
            raise StorageError(f"file not found: {key}") from e

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass


class CloudinaryStorage:
    """Resume PDFs as Cloudinary 'raw' assets with delivery type 'authenticated':
    the asset URL only works when signed with our API secret, and we never hand
    that URL to a browser. Downloads go through the API, which checks the tenant
    first (see GET /api/resumes/{id}/file)."""

    backend = "cloudinary"

    def __init__(self):
        import cloudinary
        if not config.CLOUDINARY_URL:
            cloudinary.config(
                cloud_name=config.CLOUDINARY_CLOUD_NAME,
                api_key=config.CLOUDINARY_API_KEY,
                api_secret=config.CLOUDINARY_API_SECRET,
                secure=True,
            )
        else:
            cloudinary.config(secure=True)
        self._cloudinary = cloudinary

    def save_bytes(self, data: bytes, user_id: int) -> StoredFile:
        import cloudinary.uploader
        public_id = f"{config.CLOUDINARY_FOLDER}/{user_id}/{uuid.uuid4().hex}.pdf"

        def _upload():
            return cloudinary.uploader.upload(
                io.BytesIO(data),
                resource_type="raw",
                type="authenticated",
                public_id=public_id,
                overwrite=False,
                use_filename=False,
                unique_filename=False,
            )

        result = _retry(_upload)
        return StoredFile(key=result.get("public_id", public_id), backend=self.backend, size=len(data))

    def read_bytes(self, key: str) -> bytes:
        import cloudinary.utils
        url, _ = cloudinary.utils.cloudinary_url(key, resource_type="raw", type="authenticated", sign_url=True, secure=True)

        def _get():
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content

        return _retry(_get)

    def delete(self, key: str) -> None:
        import cloudinary.uploader
        try:
            _retry(lambda: cloudinary.uploader.destroy(key, resource_type="raw", type="authenticated", invalidate=True))
        except StorageError as e:
            logger.warning(f"Cloudinary delete failed for {key}: {e}")


def cloudinary_configured() -> bool:
    return bool(config.CLOUDINARY_URL or (config.CLOUDINARY_CLOUD_NAME and config.CLOUDINARY_API_KEY and config.CLOUDINARY_API_SECRET))


def default_backend_name() -> str:
    if config.STORAGE_BACKEND in {"local", "cloudinary"}:
        return config.STORAGE_BACKEND
    return "cloudinary" if cloudinary_configured() else "local"


_instances: dict = {}


def get_storage(backend: str = None):
    """Storage for a given backend name. Each resume records the backend it was
    written to, so old local files stay readable after switching to Cloudinary."""
    backend = backend or default_backend_name()
    if backend not in _instances:
        if backend == "cloudinary":
            if not cloudinary_configured():
                raise StorageError("Cloudinary is selected but CLOUDINARY_URL (or the three CLOUDINARY_* variables) is not set")
            _instances[backend] = CloudinaryStorage()
        else:
            _instances[backend] = LocalStorage()
    return _instances[backend]


@contextmanager
def local_copy(backend: str, key: str) -> Iterator[str]:
    """Temporary on-disk copy of a stored file, for libraries that need a path."""
    data = get_storage(backend).read_bytes(key)
    fd, path = tempfile.mkstemp(suffix=".pdf", prefix="hireai_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
