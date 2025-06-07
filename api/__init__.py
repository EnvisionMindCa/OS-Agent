"""Public interface for the API package."""

from .api import create_app, app
from .document_service import (
    save_document,
    list_documents,
    get_document,
    read_content,
)

__all__ = [
    "create_app",
    "app",
    "save_document",
    "list_documents",
    "get_document",
    "read_content",
]

