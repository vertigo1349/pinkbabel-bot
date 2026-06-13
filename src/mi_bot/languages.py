"""Supported language helpers for mi_bot."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


class LanguageError(ValueError):
    """Raised when a language is not supported."""


@dataclass(frozen=True, slots=True)
class Language:
    """A supported translation target language."""

    code: str
    name: str


SUPPORTED_LANGUAGES: dict[str, Language] = {
    "ar": Language("ar", "Arabe"),
    "de": Language("de", "Aleman"),
    "en": Language("en", "Ingles"),
    "es": Language("es", "Espanol"),
    "fr": Language("fr", "Frances"),
    "hi": Language("hi", "Hindi"),
    "it": Language("it", "Italiano"),
    "ja": Language("ja", "Japones"),
    "ko": Language("ko", "Coreano"),
    "nl": Language("nl", "Neerlandes"),
    "pt": Language("pt", "Portugues"),
    "ru": Language("ru", "Ruso"),
    "tr": Language("tr", "Turco"),
    "zh-cn": Language("zh-cn", "Chino simplificado"),
}

FEATURED_LANGUAGE_CODES: tuple[str, ...] = (
    "es",
    "en",
    "fr",
    "de",
    "pt",
    "ru",
    "ko",
    "ja",
    "zh-cn",
)

LANGUAGE_ALIASES: dict[str, str] = {
    "aleman": "de",
    "arab": "ar",
    "arabic": "ar",
    "arabe": "ar",
    "chinese": "zh-cn",
    "chino": "zh-cn",
    "chino simplificado": "zh-cn",
    "coreano": "ko",
    "deutsch": "de",
    "dutch": "nl",
    "english": "en",
    "espanol": "es",
    "french": "fr",
    "frances": "fr",
    "german": "de",
    "hindi": "hi",
    "ingles": "en",
    "italian": "it",
    "italiano": "it",
    "japanese": "ja",
    "japones": "ja",
    "korean": "ko",
    "koreano": "ko",
    "mandarin": "zh-cn",
    "nederlands": "nl",
    "portugues": "pt",
    "portuguese": "pt",
    "ruso": "ru",
    "russian": "ru",
    "spanish": "es",
    "turco": "tr",
    "turkish": "tr",
}


def normalize_language_name(value: str) -> str:
    """Normalize user-provided language names for matching."""

    if not isinstance(value, str):
        raise LanguageError(f"Unsupported language: {value}")

    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.replace("_", "-").split())


def resolve_language_code(value: str) -> str:
    """Resolve a language code or alias into a supported code."""

    key = normalize_language_name(value)
    if key in SUPPORTED_LANGUAGES:
        return key
    if key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[key]

    raise LanguageError(f"Unsupported language: {value}")


def language_display(code: str) -> str:
    """Return a friendly language display name."""

    language = SUPPORTED_LANGUAGES.get(code)
    if language is None:
        return code
    return f"{language.name} ({language.code})"


def supported_language_lines() -> list[str]:
    """Return short display lines for the supported languages."""

    languages = sorted(SUPPORTED_LANGUAGES.values(), key=lambda item: item.name)
    return [f"- {language.name}: `{language.code}`" for language in languages]
