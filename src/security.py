from __future__ import annotations

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable, Awaitable, MutableMapping
from time import monotonic
import asyncio

from .config import API_KEYS, RATE_LIMIT


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid API key via the ``X-API-Key`` header."""

    def __init__(self, app):
        super().__init__(app)
        self._keys = {k.strip() for k in API_KEYS if k.strip()}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self._keys:
            key = request.headers.get("X-API-Key")
            if key not in self._keys:
                raise HTTPException(status_code=401, detail="Invalid API key")
        return await call_next(request)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per client."""

    def __init__(self, app, rate_limit: int = RATE_LIMIT) -> None:
        super().__init__(app)
        self.rate_limit = rate_limit
        self._requests: MutableMapping[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        identifier = request.headers.get("X-API-Key") or request.client.host
        now = monotonic()
        async with self._lock:
            timestamps = self._requests.setdefault(identifier, [])
            while timestamps and now - timestamps[0] > 60:
                timestamps.pop(0)
            if len(timestamps) >= self.rate_limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            timestamps.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add common security-related HTTP headers."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "geolocation=()")
        headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
        return response
