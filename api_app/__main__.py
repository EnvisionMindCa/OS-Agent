from __future__ import annotations

import os

import uvicorn

from . import app


def main() -> None:
    """Run the FastAPI application using uvicorn."""
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":  # pragma: no cover - entry point
    main()
