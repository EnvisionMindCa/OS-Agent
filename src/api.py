from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import os
import tempfile
from pathlib import Path

from .chat import ChatSession
from .log import get_logger
from .db import list_sessions


_LOG = get_logger(__name__)


class ChatRequest(BaseModel):
    user: str = "default"
    session: str = "default"
    prompt: str


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Backend API")

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest):
        async def stream() -> asyncio.AsyncIterator[str]:
            async with ChatSession(user=req.user, session=req.session) as chat:
                try:
                    async for part in chat.chat_stream(req.prompt):
                        yield part
                except Exception as exc:  # pragma: no cover - runtime failures
                    _LOG.error("Streaming chat failed: %s", exc)
                    yield f"Error: {exc}"

        return StreamingResponse(stream(), media_type="text/plain")

    @app.post("/upload")
    async def upload_document(
        user: str = Form(...),
        session: str = Form("default"),
        file: UploadFile = File(...),
    ):
        async with ChatSession(user=user, session=session) as chat:
            tmpdir = tempfile.mkdtemp(prefix="upload_")
            tmp_path = Path(tmpdir) / file.filename
            try:
                contents = await file.read()
                tmp_path.write_bytes(contents)
                vm_path = chat.upload_document(str(tmp_path))
            finally:
                try:
                    os.remove(tmp_path)
                    os.rmdir(tmpdir)
                except OSError:
                    pass
        return {"path": vm_path}

    @app.get("/sessions/{user}")
    async def list_user_sessions(user: str):
        return {"sessions": list_sessions(user)}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover - manual start
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
