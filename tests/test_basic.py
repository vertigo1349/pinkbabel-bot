from __future__ import annotations

import asyncio
import json
from pathlib import Path
import urllib.request
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from mi_bot.bot import (
    TelegramTranslatorBot,
    build_default_request,
    build_explicit_request,
    build_language_keyboard,
    build_main_menu_keyboard,
    split_telegram_text,
)
from mi_bot.config import ConfigError, Settings, load_settings
from mi_bot.languages import LanguageError, resolve_language_code
from mi_bot.health import start_health_server
from mi_bot.main import TelegramTranslatorBot as MainTelegramTranslatorBot, main
from mi_bot.storage import (
    JsonPreferenceStore,
    SupabasePreferenceStore,
    create_preference_store,
)


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def translate(self, text: str, target_language: str) -> str:
        self.calls.append((text, target_language))
        return f"{target_language}:{text}"


def make_settings(data_file: Path) -> Settings:
    return Settings(
        bot_token="token",
        bot_name="mi_bot",
        target_language="es",
        data_file=data_file,
    )


def test_load_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("BOT_NAME", raising=False)
    monkeypatch.delenv("TARGET_LANG", raising=False)
    monkeypatch.delenv("BOT_DATA_FILE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = load_settings()

    assert settings.bot_token is None
    assert settings.bot_name == "mi_bot"
    assert settings.target_language == "es"
    assert settings.data_file == Path("bot_data.json")
    assert settings.supabase_url is None
    assert settings.supabase_key is None


def test_load_settings_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    with pytest.raises(ConfigError, match="BOT_TOKEN is required"):
        load_settings(require_bot_token=True)


def test_load_settings_requires_complete_supabase_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(ConfigError, match="must be configured together"):
        load_settings()


def test_health_server_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORT", raising=False)

    assert start_health_server() is None


def test_health_server_responds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "0")
    server = start_health_server()
    assert server is not None

    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
            assert response.status == 200
            assert b'"status":"ok"' in response.read()
    finally:
        server.shutdown()
        server.server_close()


def test_language_aliases_are_resolved() -> None:
    assert resolve_language_code("spanish") == "es"
    assert resolve_language_code("espa\u00f1ol") == "es"
    assert resolve_language_code("frances") == "fr"
    assert resolve_language_code("ruso") == "ru"
    assert resolve_language_code("aleman") == "de"
    assert resolve_language_code("portugues") == "pt"
    assert resolve_language_code("coreano") == "ko"
    assert resolve_language_code("japones") == "ja"
    assert resolve_language_code("chino") == "zh-cn"

    with pytest.raises(LanguageError):
        resolve_language_code("klingon")


def test_translation_request_helpers_use_reply_text() -> None:
    default_request = build_default_request([], "es", "Hola mundo")
    explicit_request = build_explicit_request(["en"], "Hola mundo")

    assert default_request.target_language == "es"
    assert default_request.text == "Hola mundo"
    assert explicit_request.target_language == "en"
    assert explicit_request.text == "Hola mundo"


def test_split_telegram_text_respects_limit() -> None:
    chunks = split_telegram_text("palabra " * 20, limit=25)

    assert "".join(chunks).replace(" ", "") == ("palabra" * 20)
    assert all(len(chunk) <= 25 for chunk in chunks)


def test_language_keyboard_marks_selected_language() -> None:
    keyboard = build_language_keyboard("ru")
    buttons = [button for row in keyboard.inline_keyboard for button in row]

    assert any(button.callback_data == "lang:ru" and button.text == "[x] Ruso" for button in buttons)
    assert any(button.callback_data == "lang:ko" and button.text == "Coreano" for button in buttons)


def test_main_menu_contains_help_and_config_buttons() -> None:
    keyboard = build_main_menu_keyboard(is_group=True)
    callbacks = {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    }

    assert "menu:help" in callbacks
    assert "menu:config" in callbacks
    assert "menu:conversation" in callbacks
    assert "menu:mylang" in callbacks


def test_preference_store_persists_chat_language(tmp_path: Path) -> None:
    data_file = tmp_path / "bot_data.json"
    store = JsonPreferenceStore(data_file)

    saved_language = store.set_chat_language(123, "english")
    reloaded_store = JsonPreferenceStore(data_file)

    assert saved_language == "en"
    assert reloaded_store.get_chat_language(123, "es") == "en"


def test_preference_store_persists_group_conversation(tmp_path: Path) -> None:
    data_file = tmp_path / "bot_data.json"
    store = JsonPreferenceStore(data_file)
    store.set_chat_language(123, "frances")
    store.set_user_language(123, 1, "espanol")
    store.set_user_language(123, 2, "ingles")
    store.set_auto_translation(123, True)

    reloaded_store = JsonPreferenceStore(data_file)

    assert reloaded_store.get_chat_language(123, "es") == "fr"
    assert reloaded_store.is_auto_translation_enabled(123) is True
    assert reloaded_store.get_group_target_languages(123, 1) == ["en"]
    assert reloaded_store.get_group_target_languages(123, 2) == ["es"]


def test_preference_store_uses_supabase_when_configured(tmp_path: Path) -> None:
    store = create_preference_store(
        tmp_path / "bot_data.json",
        supabase_url="https://example.supabase.co",
        supabase_key="secret",
    )

    assert isinstance(store, SupabasePreferenceStore)


def test_supabase_store_reads_group_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_body = json.dumps(
        [
            {"user_id": 1, "language": "es"},
            {"user_id": 2, "language": "en"},
            {"user_id": 3, "language": "de"},
        ]
    ).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self) -> bytes:
            return response_body

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("mi_bot.storage.urlopen", fake_urlopen)
    store = SupabasePreferenceStore("https://example.supabase.co", "secret")

    assert store.get_group_target_languages(456, 1) == ["de", "en"]
    assert requests[0][1] == 10.0
    assert "/rest/v1/pinkbabel_users?" in requests[0][0].full_url


def test_supabase_store_upserts_chat_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self) -> bytes:
            return b""

    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr("mi_bot.storage.urlopen", fake_urlopen)
    store = SupabasePreferenceStore("https://example.supabase.co", "secret")

    assert store.set_chat_language(123, "aleman") == "de"
    assert requests[0].method == "POST"
    assert json.loads(requests[0].data) == {
        "chat_id": 123,
        "target_language": "de",
    }


def test_set_language_command_updates_preference(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))

    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123, type="private"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(args=["english"])

    asyncio.run(bot.set_language(update, context))

    assert bot.preferences.get_chat_language(123, "es") == "en"
    assert "Ingles (en)" in reply_text.await_args.args[0]


def test_language_button_updates_preference(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))
    query = SimpleNamespace(
        data="lang:ja",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=123, type="private"),
    )

    asyncio.run(bot.select_language_button(update, SimpleNamespace()))

    assert bot.preferences.get_chat_language(123, "es") == "ja"
    query.answer.assert_awaited_once()
    assert "Japones (ja)" in query.edit_message_text.await_args.args[0]


def test_group_language_button_updates_participant_preference(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))
    query = SimpleNamespace(
        data="mylang:en",
        from_user=SimpleNamespace(id=99),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=456, type="group"),
    )

    asyncio.run(bot.select_language_button(update, SimpleNamespace()))

    assert bot.preferences.get_user_language(456, 99) == "en"
    assert "Tu idioma fue guardado: Ingles (en)" in query.edit_message_text.await_args.args[0]


def test_config_button_enables_group_conversation(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))
    query = SimpleNamespace(
        data="config:auto:on",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=456, type="group"),
    )

    asyncio.run(bot.navigate_menu(update, SimpleNamespace()))

    assert bot.preferences.is_auto_translation_enabled(456) is True
    query.answer.assert_awaited_once()
    assert "Conversacion automatica: activada" in query.edit_message_text.await_args.args[0]
    keyboard = query.edit_message_text.await_args.kwargs["reply_markup"]
    assert any(
        button.callback_data == "config:auto:off"
        for row in keyboard.inline_keyboard
        for button in row
    )


def test_register_commands_adds_menu_help_and_config(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))
    set_my_commands = AsyncMock()
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=set_my_commands))

    asyncio.run(bot.register_commands(application))

    assert set_my_commands.await_count == 3
    calls = set_my_commands.await_args_list
    default_names = {command.command for command in calls[0].args[0]}
    private_scope = type(calls[1].kwargs["scope"]).__name__
    group_scope = type(calls[2].kwargs["scope"]).__name__
    group_names = {command.command for command in calls[2].args[0]}

    assert {"menu", "help", "config"} <= default_names
    assert private_scope == "BotCommandScopeAllPrivateChats"
    assert group_scope == "BotCommandScopeAllGroupChats"
    assert {"menu", "mylang", "autotr"} <= group_names


def test_group_commands_register_language_and_enable_translation(tmp_path: Path) -> None:
    bot = TelegramTranslatorBot(make_settings(tmp_path / "bot_data.json"))
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456, type="group"),
        effective_user=SimpleNamespace(id=7),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )

    asyncio.run(bot.set_my_language(update, SimpleNamespace(args=["espanol"])))
    asyncio.run(bot.auto_translate(update, SimpleNamespace(args=["on"])))

    assert bot.preferences.get_group_languages(456) == ["es"]
    assert bot.preferences.is_auto_translation_enabled(456) is True
    assert reply_text.await_count == 2


def test_private_text_uses_saved_language_and_replies(tmp_path: Path) -> None:
    translator = FakeTranslator()
    preferences = JsonPreferenceStore(tmp_path / "bot_data.json")
    preferences.set_chat_language(123, "english")
    bot = TelegramTranslatorBot(
        make_settings(tmp_path / "bot_data.json"),
        translator=translator,
        preferences=preferences,
    )

    reply_text = AsyncMock()
    message = SimpleNamespace(text="Hello world", reply_text=reply_text)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123, type="private"),
        effective_message=message,
    )

    asyncio.run(bot.translate_private_text(update, SimpleNamespace()))

    assert translator.calls == [("Hello world", "en")]
    reply_text.assert_awaited_once()
    assert "en:Hello world" in reply_text.await_args.args[0]


def test_group_text_is_translated_for_other_participant(tmp_path: Path) -> None:
    translator = FakeTranslator()
    preferences = JsonPreferenceStore(tmp_path / "bot_data.json")
    preferences.set_user_language(456, 1, "espanol")
    preferences.set_user_language(456, 2, "ingles")
    preferences.set_auto_translation(456, True)
    bot = TelegramTranslatorBot(
        make_settings(tmp_path / "bot_data.json"),
        translator=translator,
        preferences=preferences,
    )

    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456, type="group"),
        effective_user=SimpleNamespace(id=1),
        effective_message=SimpleNamespace(text="Hola, como estas?", reply_text=reply_text),
    )

    asyncio.run(bot.translate_group_text(update, SimpleNamespace()))

    assert translator.calls == [("Hola, como estas?", "en")]
    reply_text.assert_awaited_once()
    assert "Ingles (en)" in reply_text.await_args.args[0]
    assert "en:Hola, como estas?" in reply_text.await_args.args[0]


def test_group_text_is_ignored_when_auto_translation_is_off(tmp_path: Path) -> None:
    translator = FakeTranslator()
    preferences = JsonPreferenceStore(tmp_path / "bot_data.json")
    preferences.set_user_language(456, 1, "espanol")
    preferences.set_user_language(456, 2, "ingles")
    bot = TelegramTranslatorBot(
        make_settings(tmp_path / "bot_data.json"),
        translator=translator,
        preferences=preferences,
    )
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456, type="group"),
        effective_user=SimpleNamespace(id=1),
        effective_message=SimpleNamespace(text="Hola", reply_text=reply_text),
    )

    asyncio.run(bot.translate_group_text(update, SimpleNamespace()))

    assert translator.calls == []
    reply_text.assert_not_awaited()


def test_main_prints_success_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("BOT_NAME", "mi_bot")
    monkeypatch.setenv("TARGET_LANG", "es")
    monkeypatch.setattr(MainTelegramTranslatorBot, "run", lambda self: None)

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "mi_bot esta listo para traducir al idioma es." in captured.out
