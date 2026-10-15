from types import SimpleNamespace

import pytest
from deep_translator.exceptions import (
    LanguageNotSupportedException,
    NotValidLength,
    RequestError,
    TooManyRequests,
)

from mi_bot.translator import DeepTranslatorService, TranslationError


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (TooManyRequests(), "Google limito temporalmente"),
        (NotValidLength("private text", 0, 5000), "demasiado largo"),
        (LanguageNotSupportedException("unknown"), "no admite ese idioma"),
        (RequestError(), "No se pudo conectar"),
        (OSError("private text"), "No se pudo conectar"),
        (RuntimeError("private text"), "proveedor de traduccion fallo"),
    ],
)
def test_provider_errors_are_explained_without_logging_text(
    monkeypatch, caplog, failure, message
):
    def fail(text):
        raise failure

    monkeypatch.setattr(
        "mi_bot.translator.GoogleTranslator",
        lambda **kwargs: SimpleNamespace(translate=fail),
    )

    with pytest.raises(TranslationError, match=message) as caught:
        DeepTranslatorService().translate("private text", "es")

    assert caught.value.__cause__ is failure
    assert type(failure).__name__ in caplog.text
    assert "private text" not in caplog.text
    assert "private text" not in str(caught.value)


@pytest.mark.parametrize("response", ["", "   ", None])
def test_empty_provider_response_is_reported(monkeypatch, response):
    monkeypatch.setattr(
        "mi_bot.translator.GoogleTranslator",
        lambda **kwargs: SimpleNamespace(translate=lambda text: response),
    )

    with pytest.raises(TranslationError, match="respuesta vacia"):
        DeepTranslatorService().translate("Hello", "es")


def test_successful_translation_preserves_language_and_cleans_text(monkeypatch):
    def make_translator(**kwargs):
        assert kwargs == {"source": "auto", "target": "es"}

        def translate(text):
            assert text == "Hello"
            return " Hola "

        return SimpleNamespace(translate=translate)

    monkeypatch.setattr("mi_bot.translator.GoogleTranslator", make_translator)

    assert DeepTranslatorService().translate(" Hello ", "es") == "Hola"
