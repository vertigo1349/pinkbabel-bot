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
    "bn": Language("bn", "Bengali"),
    "cs": Language("cs", "Checo"),
    "da": Language("da", "Danes"),
    "de": Language("de", "Aleman"),
    "el": Language("el", "Griego"),
    "en": Language("en", "Ingles"),
    "es": Language("es", "Espanol"),
    "fa": Language("fa", "Persa"),
    "fi": Language("fi", "Finlandes"),
    "fr": Language("fr", "Frances"),
    "hi": Language("hi", "Hindi"),
    "hu": Language("hu", "Hungaro"),
    "id": Language("id", "Indonesio"),
    "it": Language("it", "Italiano"),
    "iw": Language("iw", "Hebreo"),
    "ja": Language("ja", "Japones"),
    "ko": Language("ko", "Coreano"),
    "la": Language("la", "Latin"),
    "nl": Language("nl", "Neerlandes"),
    "no": Language("no", "Noruego"),
    "pl": Language("pl", "Polaco"),
    "pt": Language("pt", "Portugues"),
    "ro": Language("ro", "Rumano"),
    "ru": Language("ru", "Ruso"),
    "sv": Language("sv", "Sueco"),
    "sw": Language("sw", "Suajili"),
    "th": Language("th", "Tailandes"),
    "tl": Language("tl", "Tagalo"),
    "tr": Language("tr", "Turco"),
    "uk": Language("uk", "Ucraniano"),
    "ur": Language("ur", "Urdu"),
    "vi": Language("vi", "Vietnamita"),
    "zh-cn": Language("zh-cn", "Chino simplificado"),
}

FEATURED_LANGUAGE_CODES: tuple[str, ...] = (
    "es",
    "en",
    "fr",
    "de",
    "pt",
    "it",
    "ru",
    "uk",
    "ar",
    "hi",
    "ko",
    "ja",
    "zh-cn",
    "th",
    "vi",
)

LANGUAGE_ALIASES: dict[str, str] = {
    "aleman": "de",
    "arab": "ar",
    "arabic": "ar",
    "arabe": "ar",
    "bengali": "bn",
    "checo": "cs",
    "chinese": "zh-cn",
    "chino": "zh-cn",
    "chino simplificado": "zh-cn",
    "coreano": "ko",
    "czech": "cs",
    "danes": "da",
    "danish": "da",
    "deutsch": "de",
    "dutch": "nl",
    "english": "en",
    "espanol": "es",
    "farsi": "fa",
    "fines": "fi",
    "finlandes": "fi",
    "finnish": "fi",
    "french": "fr",
    "frances": "fr",
    "german": "de",
    "greek": "el",
    "griego": "el",
    "hebrew": "iw",
    "hebreo": "iw",
    "hindi": "hi",
    "hungarian": "hu",
    "hungaro": "hu",
    "indonesian": "id",
    "indonesio": "id",
    "ingles": "en",
    "italian": "it",
    "italiano": "it",
    "japanese": "ja",
    "japones": "ja",
    "korean": "ko",
    "koreano": "ko",
    "latin": "la",
    "mandarin": "zh-cn",
    "nederlands": "nl",
    "noruego": "no",
    "norwegian": "no",
    "persa": "fa",
    "polaco": "pl",
    "polish": "pl",
    "portugues": "pt",
    "portuguese": "pt",
    "romanian": "ro",
    "rumano": "ro",
    "ruso": "ru",
    "russian": "ru",
    "spanish": "es",
    "suajili": "sw",
    "sueco": "sv",
    "swahili": "sw",
    "swedish": "sv",
    "tagalog": "tl",
    "tagalo": "tl",
    "tailandes": "th",
    "thai": "th",
    "turco": "tr",
    "turkish": "tr",
    "ucraniano": "uk",
    "ukrainian": "uk",
    "urdu": "ur",
    "vietnamese": "vi",
    "vietnamita": "vi",
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
