from __future__ import annotations

from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

from .document_service import (
    save_document,
    list_documents,
    get_document,
    read_content,
)
from src.log import get_logger


class DocumentInfo(BaseModel):
    id: int
    original_name: str
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentDetail(DocumentInfo):
    content: str


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Backend API")
    log = get_logger(__name__)

    @app.post("/users/{username}/documents", response_model=DocumentInfo)
    async def upload(username: str, file: UploadFile = File(...)) -> DocumentInfo:
        log.info("Uploading document %s for %s", file.filename, username)
        doc = save_document(username, file)
        return DocumentInfo.model_validate(doc.__data__)

    @app.get("/users/{username}/documents", response_model=List[DocumentInfo])
    async def list_docs(username: str) -> List[DocumentInfo]:
        docs = list_documents(username)
        return [DocumentInfo.model_validate(d.__data__) for d in docs]

    @app.get("/users/{username}/documents/{doc_id}", response_model=DocumentDetail)
    async def inspect(username: str, doc_id: int) -> DocumentDetail:
        doc = get_document(username, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        content = read_content(doc)
        data = DocumentDetail.model_validate(doc.__data__)
        data.content = content
        return data

    @app.get("/users/{username}/documents/{doc_id}/raw", response_class=PlainTextResponse)
    async def download(username: str, doc_id: int) -> PlainTextResponse:
        doc = get_document(username, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return PlainTextResponse(read_content(doc))

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
