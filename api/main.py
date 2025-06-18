from __future__ import annotations

import os
import tempfile

from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends
from fastapi.security import (
    OAuth2PasswordRequestForm,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
from agent.config import DEFAULT_CONFIG
from agent.db import (
    delete_history,
    reset_memory,
    list_sessions_info,
    register_user,
    authenticate_user,
)

import agent
from agent.utils.logging import get_logger

app = FastAPI(title="llmOS Agent API")
LOG = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    cfg = DEFAULT_CONFIG
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=cfg.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, cfg.secret_key, algorithm="HS256")


def get_current_username(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    token = credentials.credentials if credentials else None
    cfg = DEFAULT_CONFIG
    if not token:
        if cfg.require_auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return None
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=["HS256"])
        username: str | None = payload.get("sub")
        if username is None:
            raise JWTError
        return username
    except JWTError:
        if cfg.require_auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return None


def _use_user(request_user: str, token_user: str | None) -> str:
    """Return ``token_user`` if set, otherwise ``request_user``."""

    return token_user or request_user


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


class RegisterRequest(BaseModel):
    username: str
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
async def chat_solo(
    req: ChatRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    text = await _chat(agent.solo_chat, req)
    return {"response": text}


@app.post("/chat/team")
async def chat_team(
    req: ChatRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    text = await _chat(agent.team_chat, req)
    return {"response": text}


@app.post("/auth/register", status_code=201)
async def register(req: RegisterRequest) -> TokenResponse:
    cfg = DEFAULT_CONFIG
    if cfg.require_auth:
        if not req.password:
            raise HTTPException(status_code=400, detail="Password required")
        hashed = get_password_hash(req.password)
        user = register_user(req.username, hashed)
        token = create_access_token({"sub": user.username})
    else:
        register_user(req.username)
        token = ""
    return TokenResponse(access_token=token)


@app.post("/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    cfg = DEFAULT_CONFIG
    if cfg.require_auth:
        user = authenticate_user(form.username)
        if not user or not verify_password(form.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_access_token({"sub": user.username})
    else:
        register_user(form.username)
        token = ""
    return TokenResponse(access_token=token)


class CommandRequest(BaseModel):
    command: str
    user: str = "default"
    timeout: int | None = 5


@app.post("/vm/execute")
async def vm_execute(
    req: CommandRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    output = await agent.vm_execute(req.command, user=req.user, timeout=req.timeout)
    return {"output": output}


class PathRequest(BaseModel):
    path: str
    user: str = "default"


@app.get("/vm/list")
async def list_directory(
    req: PathRequest,
    token_user: str | None = Depends(get_current_username),
) -> list[dict[str, str]]:
    req.user = _use_user(req.user, token_user)
    rows = await agent.list_dir(req.path, user=req.user)
    return [{"name": name, "is_dir": is_dir} for name, is_dir in rows]


@app.get("/vm/read")
async def read_file(
    req: PathRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    content = await agent.read_file(req.path, user=req.user)
    return {"content": content}


class WriteRequest(PathRequest):
    content: str


@app.post("/vm/write")
async def write_file(
    req: WriteRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    result = await agent.write_file(req.path, req.content, user=req.user)
    return {"result": result}


@app.delete("/vm/delete")
async def delete(
    req: PathRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    result = await agent.delete_path(req.path, user=req.user)
    return {"result": result}


async def _save_temp(file: UploadFile) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    contents = await file.read()
    tmp.write(contents)
    tmp.close()
    return tmp.name


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    user: str = "default",
    session: str = "default",
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    user = _use_user(user, token_user)
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
async def memory_edit(
    req: MemoryEditRequest,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    req.user = _use_user(req.user, token_user)
    if req.protected:
        mem = agent.edit_protected_memory(req.user, req.field, req.value)
    else:
        mem = agent.edit_memory(req.user, req.field, req.value)
    return {"memory": mem}


@app.get("/memory/{user}")
async def memory_get(
    user: str,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    user = _use_user(user, token_user)
    return {"memory": agent.get_memory(user)}


@app.post("/memory/{user}/reset")
async def memory_reset_endpoint(
    user: str,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, str]:
    user = _use_user(user, token_user)
    memory = reset_memory(user)
    return {"memory": memory}


@app.post("/sessions/{user}/{session}/delete")
async def session_delete(
    user: str,
    session: str,
    token_user: str | None = Depends(get_current_username),
) -> dict[str, int]:
    user = _use_user(user, token_user)
    deleted = delete_history(user, session)
    return {"deleted": deleted}


@app.get("/sessions/{user}")
async def sessions(
    user: str,
    token_user: str | None = Depends(get_current_username),
) -> list[dict[str, str]]:
    user = _use_user(user, token_user)
    return list_sessions_info(user)



from agent.utils.debug import debug_all
debug_all(globals())
