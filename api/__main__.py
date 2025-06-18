from __future__ import annotations

import os
import uvicorn

from .main import app


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

from agent.utils.debug import debug_all
debug_all(globals())
