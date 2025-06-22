"""Compatibility layer importing WebSocket client helpers."""

from .ws_client import WSApiClient
from .connection import WSConnection

__all__ = ["WSApiClient", "WSConnection"]
