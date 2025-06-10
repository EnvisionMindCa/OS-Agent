from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import os
import tempfile
from pathlib import Path
from typing import List
import shutil

from src.config import UPLOAD_DIR

from src.team import TeamChatSession
from src.log import get_logger
from src.db import list_sessions, list_sessions_info


_LOG = get_logger(__name__)


class ChatRequest(BaseModel):
    user: str = "default"
    session: str = "default"
    prompt: str


class FileWriteRequest(BaseModel):
    path: str
    content: str


def _vm_host_path(user: str, vm_path: str) -> Path:
    """Return the host path for a given ``vm_path`` inside ``/data``."""

    try:
        rel = Path(vm_path).relative_to("/data")
    except ValueError as exc:  # pragma: no cover - invalid path
        raise HTTPException(status_code=400, detail="Path must start with /data") from exc

    base = (Path(UPLOAD_DIR) / user).resolve()
    target = (base / rel).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Backend API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest):
        async def stream() -> asyncio.AsyncIterator[str]:
            async with TeamChatSession(user=req.user, session=req.session) as chat:
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
        async with TeamChatSession(user=user, session=session) as chat:
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

    @app.get("/sessions/{user}/info")
    async def list_user_sessions_info(user: str):
        data = list_sessions_info(user)
        if not data:
            raise HTTPException(status_code=404, detail="User not found")
        return {"sessions": data}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/vm/{user}/list")
    async def list_vm_dir(user: str, path: str = "/data"):
        target = _vm_host_path(user, path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="Not a directory")
        entries: List[dict[str, str | bool]] = []
        for entry in sorted(target.iterdir()):
            entries.append({"name": entry.name, "is_dir": entry.is_dir()})
        return {"entries": entries}

    @app.get("/vm/{user}/file")
    async def read_vm_file(user: str, path: str):
        target = _vm_host_path(user, path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target.is_dir():
            raise HTTPException(status_code=400, detail="Path is a directory")
        try:
            content = target.read_text()
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Binary file not supported")
        return {"content": content}

    @app.post("/vm/{user}/file")
    async def write_vm_file(user: str, req: FileWriteRequest):
        target = _vm_host_path(user, req.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content)
        return {"status": "ok"}

    @app.delete("/vm/{user}/file")
    async def delete_vm_file(user: str, path: str):
        target = _vm_host_path(user, path)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        else:
            raise HTTPException(status_code=404, detail="File not found")
        return {"status": "deleted"}

    return app


app = create_app()
