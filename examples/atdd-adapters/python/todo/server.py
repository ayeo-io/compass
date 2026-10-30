"""The todo service's HTTP API.

    python -m todo.server --data-dir DATA [--host 127.0.0.1] [--port 8000]

It prints `listening on http://HOST:PORT` once it is ready. `--port 0` picks
a free port. With `--exit-with-parent` it stops when its standard input
closes, so a server a test run started cannot outlive the run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from todo.service import TodoError, TodoService

ROUTES = [
    ("POST", re.compile(r"/accounts"), "create_account"),
    ("POST", re.compile(r"/accounts/(?P<email>[^/]+)/todos"), "add"),
    ("POST", re.compile(r"/accounts/(?P<email>[^/]+)/todos/(?P<name>[^/]+)/complete"), "complete"),
    ("POST", re.compile(r"/accounts/(?P<email>[^/]+)/todos/(?P<name>[^/]+)/archive"), "archive"),
    ("GET", re.compile(r"/accounts/(?P<email>[^/]+)/todos"), "todos"),
]


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._serve("GET")

        def do_POST(self):
            self._serve("POST")

        def log_message(self, *args):
            # Quiet: nothing reads the server's log during a run.
            pass

        def _serve(self, method):
            url = urlsplit(self.path)
            for route_method, pattern, action in ROUTES:
                found = pattern.fullmatch(url.path)
                if route_method == method and found:
                    break
            else:
                return self._answer(404, {"error": f"nothing answers {method} {url.path}"})
            params = {key: unquote(value) for key, value in found.groupdict().items()}
            body = self._body() if method == "POST" else {}
            query = {key: values[0] for key, values in parse_qs(url.query).items()}
            try:
                if action == "create_account":
                    service.create_account(body.get("email", ""))
                    return self._answer(201, {})
                if action == "add":
                    service.add(params["email"], body.get("name", ""))
                    return self._answer(201, {})
                if action == "todos":
                    names = service.todos(params["email"], query.get("state", "open"))
                    return self._answer(200, {"todos": names})
                getattr(service, action)(params["email"], params["name"])
                return self._answer(200, {})
            except TodoError as refusal:
                return self._answer(refusal.status, {"error": str(refusal)})

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def _answer(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(prog="todo.server", description="The todo HTTP API.")
    parser.add_argument("--data-dir", required=True, help="the folder that holds the store")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="0 picks a free port")
    parser.add_argument("--exit-with-parent", action="store_true",
                        help="stop when standard input closes")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(TodoService(args.data_dir)))
    print(f"listening on http://{args.host}:{server.server_address[1]}", flush=True)
    if args.exit_with_parent:
        def stop_at_end_of_input():
            sys.stdin.read()
            server.shutdown()
        threading.Thread(target=stop_at_end_of_input, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
