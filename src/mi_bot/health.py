"""Small HTTP health server for web-service hosting platforms."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from threading import Thread


class HealthHandler(BaseHTTPRequestHandler):
    """Serve readiness responses without application dependencies."""

    def do_GET(self) -> None:
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return

        body = b'{"status":"ok","service":"PinkBabel"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server() -> ThreadingHTTPServer | None:
    """Start the health server when a hosting platform provides PORT."""

    raw_port = os.getenv("PORT")
    if not raw_port:
        return None

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("PORT must be a valid integer.") from exc

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    return server
