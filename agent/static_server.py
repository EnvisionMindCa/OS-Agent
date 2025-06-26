from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

__all__ = ["run_server", "main"]


def run_server(host: str, port: int, static_dir: str, returns_dir: str) -> None:
    static_path = Path(static_dir).resolve()
    returns_path = Path(returns_dir).resolve()

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:  # type: ignore[override]
            if path.startswith('/files/'):
                rel = path[len('/files/') :]
                return str((returns_path / rel).resolve())
            return str((static_path / path.lstrip('/')).resolve())

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"HTTP server listening on {host}:{port}")
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple static file server")
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--static-dir', default=str(Path(__file__).resolve().parent.parent / 'frontend'))
    parser.add_argument('--returns-dir', default=str(Path.cwd() / 'returns'))
    args = parser.parse_args()
    run_server(args.host, args.port, args.static_dir, args.returns_dir)


if __name__ == '__main__':
    main()
