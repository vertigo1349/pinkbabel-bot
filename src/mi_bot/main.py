"""Entry point for mi_bot."""

from __future__ import annotations

import sys

from .bot import TelegramTranslatorBot
from .config import ConfigError, load_settings
from .health import start_health_server


def main() -> int:
    """Start the Telegram translation bot."""

    try:
        settings = load_settings(require_bot_token=True)
        bot = TelegramTranslatorBot(settings)
        health_server = start_health_server()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net for startup
        print(f"Unexpected startup error: {exc}", file=sys.stderr)
        return 1

    print(f"{settings.bot_name} esta listo para traducir al idioma {settings.target_language}.")

    try:
        bot.run()
    except KeyboardInterrupt:
        print("Bot detenido.")
    except Exception as exc:  # pragma: no cover - runtime safety net
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1
    finally:
        if health_server is not None:
            health_server.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
