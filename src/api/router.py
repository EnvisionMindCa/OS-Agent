from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .models import ChatRequest, ChatResponse, ResetRequest, ResetResponse
from ..chat import ChatSession
from ..db import reset_history
from ..log import get_logger

router = APIRouter()
log = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    log.debug("chat request user=%s session=%s", payload.user, payload.session)
    async with ChatSession(user=payload.user, session=payload.session) as chat:
        try:
            reply = await chat.chat(payload.prompt)
        except Exception as exc:  # pragma: no cover - runtime errors
            log.exception("chat processing failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(reply=reply)


@router.post("/reset", response_model=ResetResponse, status_code=status.HTTP_200_OK)
async def reset_endpoint(payload: ResetRequest) -> ResetResponse:
    removed = reset_history(payload.user, payload.session)
    return ResetResponse(removed=removed)
