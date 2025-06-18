import uvicorn
import uvicorn

from .main import app


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

from agent.utils.debug import debug_all
debug_all(globals())
