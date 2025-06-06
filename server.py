from __future__ import annotations

import uvicorn

from src.api import create_app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover - manual start
    main()
