"""Translation service abstractions for mi_bot."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

try:
    from deep_translator import GoogleTranslator
    from deep_translator.exceptions import (
        InvalidSourceOrTargetLanguage,
        LanguageNotSupportedException,
        NotValidLength,
        RequestError,
        TooManyRequests,
    )
except ImportError as exc:  # pragma: no cover - dependency issue only
    GoogleTranslator = None
    _IMPORT_ERROR = exc
else:  # pragma: no cover - import success is exercised indirectly
    _IMPORT_ERROR = None

logger = logging.getLogger(__name__)


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
            raise TranslationError("Envia un texto para traducir.")

        if GoogleTranslator is None:  # pragma: no cover - dependency issue only
            raise TranslationError("El servicio de traduccion no esta configurado.") from _IMPORT_ERROR

        try:
            translator = GoogleTranslator(
                source=self.source_language,
                target=target_language,
            )
            translated = translator.translate(cleaned_text)
        except Exception as exc:
            # Provider exceptions can contain the user's text; log only the type.
            logger.warning("Translation provider error: %s", type(exc).__name__)
            if isinstance(exc, TooManyRequests):
                detail = (
                    "Google limito temporalmente las solicitudes de traduccion. "
                    "Espera unos minutos antes de volver a intentarlo."
                )
            elif isinstance(exc, NotValidLength):
                detail = "El texto es demasiado largo. Envia menos de 5000 caracteres."
            elif isinstance(exc, (LanguageNotSupportedException, InvalidSourceOrTargetLanguage)):
                detail = "El proveedor no admite ese idioma. Elige otro con /idioma."
            elif isinstance(exc, (RequestError, OSError)):
                detail = "No se pudo conectar con Google. Intenta de nuevo mas tarde."
            else:
                detail = "El proveedor de traduccion fallo. Intenta de nuevo mas tarde."
            raise TranslationError(detail) from exc

        if not isinstance(translated, str) or not translated.strip():
            logger.warning("Translation provider error: EmptyResponse")
            raise TranslationError("Google devolvio una respuesta vacia. Intenta de nuevo mas tarde.")

        return translated.strip()
