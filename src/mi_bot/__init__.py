"""mi_bot package."""

from .config import ConfigError, Settings, load_settings
from .languages import LanguageError, resolve_language_code

__all__ = [
    "ConfigError",
    "DeepTranslatorService",
    "LanguageError",
    "Settings",
    "TelegramTranslatorBot",
    "TranslationError",
    "load_settings",
    "resolve_language_code",
]


def __getattr__(name: str):
    """Load optional runtime classes only when they are requested."""

    if name == "TelegramTranslatorBot":
        from .bot import TelegramTranslatorBot

        return TelegramTranslatorBot
    if name in {"DeepTranslatorService", "TranslationError"}:
        from .translator import DeepTranslatorService, TranslationError

        return {
            "DeepTranslatorService": DeepTranslatorService,
            "TranslationError": TranslationError,
        }[name]
    raise AttributeError(f"module 'mi_bot' has no attribute {name!r}")
