"""Module entry point for running the WebSocket server."""

from __future__ import annotations

from .server.__main__ import main


if __name__ == "__main__":  # pragma: no cover - manual invocation
    try:
        main()
    except KeyboardInterrupt:
        pass
