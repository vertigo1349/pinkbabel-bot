"""Translation service abstractions for mi_bot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

try:
    from deep_translator import GoogleTranslator
except ImportError as exc:  # pragma: no cover - dependency issue only
    GoogleTranslator = None
    _IMPORT_ERROR = exc
else:  # pragma: no cover - import success is exercised indirectly
    _IMPORT_ERROR = None


class TranslationError(RuntimeError):
    """Raised when text cannot be translated."""


class Translator(Protocol):
    """Translate text into a target language."""

    def translate(self, text: str, target_language: str) -> str:
        """Translate text into a target language."""


@dataclass(slots=True)
class DeepTranslatorService:
    """Blocking translation service backed by deep-translator."""

    source_language: str = "auto"

    def translate(self, text: str, target_language: str) -> str:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise TranslationError("No text was provided for translation.")

        if GoogleTranslator is None:  # pragma: no cover - dependency issue only
            raise TranslationError("deep-translator is not installed.") from _IMPORT_ERROR

        try:
            translator = GoogleTranslator(
                source=self.source_language,
                target=target_language,
            )
            translated = translator.translate(cleaned_text)
        except Exception as exc:  # pragma: no cover - provider/network failures
            raise TranslationError("Translation failed.") from exc

        if not isinstance(translated, str) or not translated.strip():
            raise TranslationError("Translation service returned an empty response.")

        return translated.strip()
