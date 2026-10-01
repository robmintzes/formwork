"""Loopback HTTP boundary for the wizard (ADR 0006).

Request rules, enforced on every request:

* bound to 127.0.0.1 only; the Host header must be 127.0.0.1:<port> or
  localhost:<port> (blocks DNS rebinding);
* an Origin header, when present, must be this server's own origin;
* /api/* requires the per-launch token in X-Toolkit-Token (constant-time
  compare). Cross-site pages cannot send that header without a CORS preflight,
  which this server never approves;
* /preview/* additionally accepts an HttpOnly, SameSite=Strict cookie that
  POST /api/session sets, so the preview iframe can load generated assets;
* request bodies are JSON with a size cap; static files come from a fixed
  allow-list, never from arbitrary paths.

The token is generated per launch, printed in the URL fragment (never sent to
the server by the browser), and held only in memory.
"""

from __future__ import annotations

import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import threading
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from toolkit_wizard.session import WizardError, WizardSession

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY = 64 * 1024 * 1024
COOKIE = "toolkit_wizard"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".md": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".xaml": "text/plain; charset=utf-8",
    ".ps1": "text/plain; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
    ".yaml": "text/plain; charset=utf-8",
    ".yml": "text/plain; charset=utf-8",
}
APP_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "font-src 'self'; connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
PREVIEW_CSP = (
    "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)


class WizardServer(HTTPServer):
    """Single-threaded on purpose: one draft, no concurrent mutation."""

    def __init__(self, port: int = 0, session: WizardSession | None = None, token: str | None = None) -> None:
        self.session = session or WizardSession()
        self.token = token or secrets.token_urlsafe(32)
        self.stop_requested = threading.Event()
        super().__init__(("127.0.0.1", port), WizardHandler)

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def allowed_hosts(self) -> set[str]:
        return {"127.0.0.1:{}".format(self.port), "localhost:{}".format(self.port)}

    @property
    def allowed_origins(self) -> set[str]:
        return {"http://" + host for host in self.allowed_hosts}

    def launch_url(self) -> str:
        return "http://127.0.0.1:{}/#token={}".format(self.port, self.token)


def _static_allow_list() -> dict[str, Path]:
    allowed = {}
    if STATIC_DIR.is_dir():
        for path in STATIC_DIR.rglob("*"):
            if path.is_file() and path.suffix.lower() in CONTENT_TYPES:
                allowed["/static/" + path.relative_to(STATIC_DIR).as_posix()] = path
    return allowed


class WizardHandler(BaseHTTPRequestHandler):
    server: WizardServer
    server_version = "toolkit-wizard"
    sys_version = ""

    # ----- plumbing ---------------------------------------------------------
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        pass  # Never log request lines: preview URLs and paths stay local.

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: Any, extra: dict[str, str] | None = None) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), CONTENT_TYPES[".json"], extra)

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in self.server.allowed_origins

    def _token_ok(self) -> bool:
        supplied = self.headers.get("X-Toolkit-Token", "")
        return bool(supplied) and hmac.compare_digest(supplied, self.server.token)

    def _cookie_ok(self) -> bool:
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE and value and hmac.compare_digest(value, self.server.token):
                return True
        return False

    def _body(self) -> Any:
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise WizardError("request.content-type", "Requests must be application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise WizardError("request.length", "Invalid Content-Length.") from exc
        if length < 0 or length > MAX_BODY:
            raise WizardError("request.too-large", "Request body is too large.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WizardError("request.json", "Request body is not valid JSON.") from exc

    # ----- dispatch ---------------------------------------------------------
    def _guard(self) -> bool:
        if not self._host_ok():
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "request.host", "Unexpected Host header.")
            return False
        if not self._origin_ok():
            self._error(HTTPStatus.FORBIDDEN, "request.origin", "Cross-origin requests are not allowed.")
            return False
        return True

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib naming
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._static(STATIC_DIR / "index.html")
        elif path.startswith("/static/"):
            target = _static_allow_list().get(path)
            if target is None:
                self._error(HTTPStatus.NOT_FOUND, "static.not-found", "Not found.")
            else:
                self._static(target)
        elif path.startswith("/preview/"):
            self._preview(unquote(path[len("/preview/") :]))
        elif path.startswith("/api/"):
            self._api("GET", path)
        else:
            self._error(HTTPStatus.NOT_FOUND, "route.not-found", "Not found.")

    def do_POST(self) -> None:  # noqa: N802
        if self._guard():
            self._api("POST", urlsplit(self.path).path)

    def do_PUT(self) -> None:  # noqa: N802
        if self._guard():
            self._api("PUT", urlsplit(self.path).path)

    def _static(self, target: Path) -> None:
        if not target.is_file():
            self._error(HTTPStatus.NOT_FOUND, "static.not-found", "Not found.")
            return
        extra = {"Content-Security-Policy": APP_CSP, "X-Frame-Options": "DENY"}
        self._send(HTTPStatus.OK, target.read_bytes(), CONTENT_TYPES[target.suffix.lower()], extra)

    def _preview(self, rel: str) -> None:
        if not (self._token_ok() or self._cookie_ok()):
            self._error(HTTPStatus.FORBIDDEN, "auth.required", "Preview requires an active wizard session.")
            return
        content = self.server.session.preview.get(rel)
        suffix = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
        if content is None or suffix not in CONTENT_TYPES:
            self._error(HTTPStatus.NOT_FOUND, "preview.not-found", "Not in the current preview; validate the draft first.")
            return
        extra = {"Content-Security-Policy": PREVIEW_CSP, "X-Frame-Options": "SAMEORIGIN"}
        self._send(HTTPStatus.OK, content, CONTENT_TYPES[suffix], extra)

    def _api(self, method: str, path: str) -> None:
        if not self._token_ok():
            self._error(HTTPStatus.FORBIDDEN, "auth.required", "Missing or invalid wizard token.")
            return
        route = ROUTES.get((method, path))
        if route is None:
            self._error(HTTPStatus.NOT_FOUND, "route.not-found", "Unknown API route.")
            return
        try:
            body = self._body() if method in ("POST", "PUT") else {}
            status, payload, extra = route(self, body)
        except WizardError as exc:
            self._error(HTTPStatus.BAD_REQUEST, exc.code, str(exc))
            return
        self._json(status, payload, extra)


Route = Callable[[WizardHandler, Any], "tuple[int, Any, dict[str, str] | None]"]


def _obj(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise WizardError("request.invalid", "Expected a JSON object.")
    return body


def _session_route(handler: WizardHandler, body: Any) -> tuple[int, Any, dict[str, str] | None]:
    cookie = "{}={}; HttpOnly; SameSite=Strict; Path=/preview".format(COOKIE, handler.server.token)
    return HTTPStatus.OK, {"ok": True}, {"Set-Cookie": cookie}


def _start_route(handler: WizardHandler, body: Any) -> tuple[int, Any, dict[str, str] | None]:
    body = _obj(body)
    session = handler.server.session
    if "profile" in body:
        return HTTPStatus.OK, session.start_from_profile(str(body["profile"])), None
    if "workspace" in body:
        return HTTPStatus.OK, session.start_from_workspace(body["workspace"]), None
    raise WizardError("request.invalid", "Provide 'profile' or 'workspace'.")


def _shutdown_route(handler: WizardHandler, body: Any) -> tuple[int, Any, dict[str, str] | None]:
    handler.server.stop_requested.set()
    threading.Thread(target=handler.server.shutdown, daemon=True).start()
    return HTTPStatus.OK, {"ok": True}, None


ROUTES: dict[tuple[str, str], Route] = {
    ("POST", "/api/session"): _session_route,
    ("GET", "/api/starters"): lambda h, b: (HTTPStatus.OK, {"starters": h.server.session.starters()}, None),
    ("GET", "/api/state"): lambda h, b: (HTTPStatus.OK, h.server.session.state(), None),
    ("POST", "/api/start"): _start_route,
    ("PUT", "/api/files"): lambda h, b: (
        HTTPStatus.OK,
        h.server.session.put_files(_obj(b).get("files", {}), _obj(b).get("remove", [])),
        None,
    ),
    ("POST", "/api/validate"): lambda h, b: (HTTPStatus.OK, h.server.session.validate(), None),
    ("POST", "/api/plan"): lambda h, b: (HTTPStatus.OK, h.server.session.plan(_obj(b).get("workspace")), None),
    ("POST", "/api/apply"): lambda h, b: (HTTPStatus.OK, h.server.session.apply(_obj(b).get("workspace")), None),
    ("POST", "/api/shutdown"): _shutdown_route,
}


def serve(port: int = 0, open_browser: bool = True, announce: Callable[[str], None] = print) -> None:
    server = WizardServer(port)
    url = server.launch_url()
    announce("Wizard running at {}".format(url))
    announce("Press Ctrl+C to stop. The link contains a one-time token; do not share it.")
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
