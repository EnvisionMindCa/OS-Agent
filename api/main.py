from __future__ import annotations

import os
import tempfile

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel

import agent
from agent.db import reset_history, list_sessions_info
from agent.utils.logging import get_logger

app = FastAPI(title="llmOS Agent API")
LOG = get_logger(__name__)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health check."""
    return {"status": "ok"}


class ChatRequest(BaseModel):
    prompt: str
    user: str = "default"
    session: str = "default"
    think: bool = True
    extra: dict[str, str] | None = None


async def _chat(method, req: ChatRequest) -> str:
    parts: list[str] = []
    async for part in method(
        req.prompt,
        user=req.user,
        session=req.session,
        think=req.think,
        extra=req.extra,
    ):
        if part:
            parts.append(part)
    return "\n".join(parts)


@app.post("/chat/solo")
async def chat_solo(req: ChatRequest) -> dict[str, str]:
    text = await _chat(agent.solo_chat, req)
    return {"response": text}


@app.post("/chat/team")
async def chat_team(req: ChatRequest) -> dict[str, str]:
    text = await _chat(agent.team_chat, req)
    return {"response": text}


class CommandRequest(BaseModel):
    command: str
    user: str = "default"
    timeout: int | None = 5


@app.post("/vm/execute")
async def vm_execute(req: CommandRequest) -> dict[str, str]:
    output = await agent.vm_execute(req.command, user=req.user, timeout=req.timeout)
    return {"output": output}


class PathRequest(BaseModel):
    path: str
    user: str = "default"


@app.get("/vm/list")
async def list_directory(req: PathRequest) -> list[dict[str, str]]:
    rows = await agent.list_dir(req.path, user=req.user)
    return [{"name": name, "is_dir": is_dir} for name, is_dir in rows]


@app.get("/vm/read")
async def read_file(req: PathRequest) -> dict[str, str]:
    content = await agent.read_file(req.path, user=req.user)
    return {"content": content}


class WriteRequest(PathRequest):
    content: str


@app.post("/vm/write")
async def write_file(req: WriteRequest) -> dict[str, str]:
    result = await agent.write_file(req.path, req.content, user=req.user)
    return {"result": result}


@app.delete("/vm/delete")
async def delete(req: PathRequest) -> dict[str, str]:
    result = await agent.delete_path(req.path, user=req.user)
    return {"result": result}


async def _save_temp(file: UploadFile) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    contents = await file.read()
    tmp.write(contents)
    tmp.close()
    return tmp.name


@app.post("/upload")
async def upload(file: UploadFile = File(...), user: str = "default", session: str = "default") -> dict[str, str]:
    path = await _save_temp(file)
    try:
        vm_path = await agent.upload_document(path, user=user, session=session)
    finally:
        os.unlink(path)
    return {"vm_path": vm_path}


class MemoryEditRequest(BaseModel):
    field: str
    value: str | None = None
    protected: bool = False
    user: str = "default"


@app.post("/memory/edit")
async def memory_edit(req: MemoryEditRequest) -> dict[str, str]:
    if req.protected:
        mem = agent.edit_protected_memory(req.user, req.field, req.value)
    else:
        mem = agent.edit_memory(req.user, req.field, req.value)
    return {"memory": mem}


@app.get("/memory/{user}")
async def memory_get(user: str) -> dict[str, str]:
    return {"memory": agent.get_memory(user)}


@app.post("/sessions/{user}/{session}/reset")
async def session_reset(user: str, session: str) -> dict[str, int]:
    deleted = reset_history(user, session)
    return {"deleted": deleted}


@app.get("/sessions/{user}")
async def sessions(user: str) -> list[dict[str, str]]:
    return list_sessions_info(user)



from agent.utils.debug import debug_all
debug_all(globals())
