"""The API driver: reaches the todo service through its HTTP API, as a web client does."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import quote

from tests.acceptance.drivers import TodoDriver

TIMEOUT_SECONDS = 10
# No proxy: the server is local, and a machine's HTTP_PROXY must not route
# the suite's requests elsewhere.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Driver(TodoDriver):
    def _request(self, action, email, name=None):
        account = f"/accounts/{quote(email, safe='')}"
        if action == "account":
            status, payload = self._call("POST", "/accounts", {"email": email})
        elif action == "add":
            status, payload = self._call("POST", f"{account}/todos", {"name": name})
        else:
            status, payload = self._call("POST", f"{account}/todos/{quote(name, safe='')}/{action}", {})
        return None if status < 400 else payload.get("error", f"HTTP {status}")

    def _listed(self, email, state):
        status, payload = self._call("GET", f"/accounts/{quote(email, safe='')}/todos?state={state}")
        if status != 200:
            raise RuntimeError(f"listing the {state} todos of {email} failed: {status} {payload}")
        return payload["todos"]

    def _call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.system.api_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as answer:
                return answer.status, json.loads(answer.read() or b"{}")
        except urllib.error.HTTPError as refusal:
            return refusal.code, json.loads(refusal.read() or b"{}")
