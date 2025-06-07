from __future__ import annotations

from pathlib import Path
import shutil
from typing import List, Optional

from fastapi import UploadFile

from src.config import UPLOAD_DIR
from src.db import Document, User, init_db


def _ensure_user_dir(username: str) -> Path:
    path = Path(UPLOAD_DIR) / username
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_document(username: str, file: UploadFile) -> Document:
    """Persist an uploaded file and return its database entry."""
    init_db()
    user, _ = User.get_or_create(username=username)
    dest_dir = _ensure_user_dir(username)
    dest = dest_dir / file.filename
    with dest.open('wb') as buffer:
        shutil.copyfileobj(file.file, buffer)
    doc = Document.create(user=user, file_path=str(dest), original_name=file.filename)
    return doc


def list_documents(username: str) -> List[Document]:
    """Return all documents for ``username`` sorted by creation time."""
    init_db()
    try:
        user = User.get(User.username == username)
    except User.DoesNotExist:
        return []
    docs = Document.select().where(Document.user == user).order_by(Document.created_at)
    return list(docs)


def get_document(username: str, doc_id: int) -> Optional[Document]:
    """Retrieve a single document for ``username`` by id."""
    init_db()
    try:
        user = User.get(User.username == username)
    except User.DoesNotExist:
        return None
    try:
        return Document.get(Document.id == doc_id, Document.user == user)
    except Document.DoesNotExist:
        return None


def read_content(doc: Document) -> str:
    """Read and return the text content of ``doc``. Errors yield empty string."""
    try:
        return Path(doc.file_path).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''
