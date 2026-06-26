"""Flask webhook entry point for Render."""

from __future__ import annotations

import asyncio
import atexit
import os
import sys
from concurrent.futures import Future
from threading import Thread
from typing import Any

from flask import Flask, abort, jsonify, request
from telegram import Update

from .bot import TelegramTranslatorBot
from .config import ConfigError, Settings, load_settings

flask_app = Flask(__name__)

_settings: Settings | None = None
_bot: TelegramTranslatorBot | None = None
_application = None
_loop = asyncio.new_event_loop()
_loop_thread: Thread | None = None


def _run_loop() -> None:
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def _schedule(coro) -> Future:
    return asyncio.run_coroutine_threadsafe(coro, _loop)


async def _startup() -> None:
    global _application

    if _bot is None or _settings is None:
        raise RuntimeError("Webhook application was not configured.")

    application = _bot.build_application()
    _application = application

    await application.initialize()
    await _bot.register_commands(application)

    if _settings.webhook_url:
        webhook_endpoint = f"{_settings.webhook_url}/{_settings.webhook_path}"
        await application.bot.set_webhook(
            url=webhook_endpoint,
            secret_token=_settings.webhook_secret,
            drop_pending_updates=False,
        )
        print(f"Webhook configurado en {webhook_endpoint}")

    await application.start()


async def _shutdown() -> None:
    if _application is None:
        return

    await _application.stop()
    await _application.shutdown()


def _log_update_error(done: Future) -> None:
    try:
        done.result()
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Webhook update error: {exc}", file=sys.stderr)


def _start_once() -> None:
    global _settings, _bot, _loop_thread

    if _loop_thread is not None:
        return

    try:
        _settings = load_settings(require_bot_token=True)
        _bot = TelegramTranslatorBot(_settings)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise

    _loop_thread = Thread(target=_run_loop, name="telegram-webhook-loop", daemon=True)
    _loop_thread.start()
    _schedule(_startup()).result(timeout=60)

    print(f"{_settings.bot_name} esta listo para webhook.")


def _stop_once() -> None:
    if _loop_thread is None:
        return

    try:
        _schedule(_shutdown()).result(timeout=20)
    finally:
        _loop.call_soon_threadsafe(_loop.stop)


@flask_app.get("/")
@flask_app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "PinkBabel", "mode": "webhook"})


@flask_app.post("/<path:path>")
def telegram_webhook(path: str):
    if _settings is None or _bot is None:
        abort(503)
    if path.strip("/") != _settings.webhook_path:
        abort(404)
    if _settings.webhook_secret:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if received_secret != _settings.webhook_secret:
            abort(403)

    payload: dict[str, Any] = request.get_json(force=True, silent=False)
    if _application is None:
        abort(503)

    update = Update.de_json(payload, _application.bot)
    future = _schedule(_application.process_update(update))
    future.add_done_callback(_log_update_error)
    return jsonify({"ok": True})


_start_once()
atexit.register(_stop_once)


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
