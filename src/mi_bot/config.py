"""Configuration helpers for mi_bot."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .languages import LanguageError, resolve_language_code


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    bot_token: str | None
    bot_name: str
    target_language: str
    data_file: Path
    supabase_url: str | None = None
    supabase_key: str | None = None


def load_settings(*, require_bot_token: bool = False) -> Settings:
    """Load settings from environment variables.

    Args:
        require_bot_token: Set to True when the bot is ready to connect to a
            real API and the token must be present.
    """

    bot_token = os.getenv("BOT_TOKEN")
    bot_name = os.getenv("BOT_NAME", "mi_bot").strip() or "mi_bot"
    raw_target_language = os.getenv("TARGET_LANG", "es").strip() or "es"
    data_file = Path(os.getenv("BOT_DATA_FILE", "bot_data.json"))
    supabase_url = os.getenv("SUPABASE_URL", "").strip() or None
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip() or None

    if require_bot_token and not bot_token:
        raise ConfigError("BOT_TOKEN is required but was not set.")
    if bool(supabase_url) != bool(supabase_key):
        raise ConfigError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY must be configured together."
        )

    try:
        target_language = resolve_language_code(raw_target_language)
    except LanguageError as exc:
        raise ConfigError(str(exc)) from exc

    return Settings(
        bot_token=bot_token,
        bot_name=bot_name,
        target_language=target_language,
        data_file=data_file,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )
