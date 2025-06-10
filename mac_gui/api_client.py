from __future__ import annotations

import os
from typing import Iterator, List, Dict, Any

import httpx


class APIClient:
    """Simple client for the LLM backend API."""

    def __init__(self, server: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self._server = server.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self._server}{path}"

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------
    def list_sessions(self, user: str) -> List[str]:
        resp = httpx.get(self._url(f"/sessions/{user}"), headers=self._headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("sessions", [])

    def stream_chat(self, user: str, session: str, prompt: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            self._url("/chat/stream"),
            json={"user": user, "session": session, "prompt": prompt},
            headers=self._headers,
            timeout=None,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    yield line.decode()

    def upload_document(self, user: str, session: str, path: str) -> str:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            files = {"file": (name, f)}
            data = {"user": user, "session": session}
            resp = httpx.post(self._url("/upload"), data=data, files=files, headers=self._headers)
        resp.raise_for_status()
        return resp.json()["path"]

    def list_vm_dir(self, user: str, path: str = "/data") -> List[Dict[str, Any]]:
        resp = httpx.get(self._url(f"/vm/{user}/list"), params={"path": path}, headers=self._headers)
        resp.raise_for_status()
        return resp.json().get("entries", [])

    def read_vm_file(self, user: str, path: str) -> str:
        resp = httpx.get(self._url(f"/vm/{user}/file"), params={"path": path}, headers=self._headers)
        resp.raise_for_status()
        return resp.json().get("content", "")

    def write_vm_file(self, user: str, path: str, content: str) -> None:
        payload = {"path": path, "content": content}
        resp = httpx.post(self._url(f"/vm/{user}/file"), json=payload, headers=self._headers)
        resp.raise_for_status()

    def delete_vm_file(self, user: str, path: str) -> None:
        resp = httpx.delete(self._url(f"/vm/{user}/file"), params={"path": path}, headers=self._headers)
        resp.raise_for_status()
