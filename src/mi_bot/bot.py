"""Telegram bot wiring for mi_bot."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Protocol, Sequence

from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import ConfigError, Settings
from .languages import (
    LanguageError,
    language_display,
    resolve_language_code,
    supported_language_lines,
)
from .storage import StorageError, create_preference_store
from .translator import DeepTranslatorService, TranslationError, Translator
from .ui import (
    build_config_keyboard,
    build_help_keyboard,
    build_language_keyboard,
    build_main_menu_keyboard,
)

TELEGRAM_MESSAGE_LIMIT = 4096
SAFE_MESSAGE_LENGTH = 4000


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """A single translation job."""

    target_language: str
    text: str


def _collect_text(parts: Sequence[str], reply_text: str | None) -> str:
    text = " ".join(piece.strip() for piece in parts if piece.strip()).strip()
    if text:
        return text

    if reply_text is not None:
        reply_text = reply_text.strip()
        if reply_text:
            return reply_text

    raise ValueError("Provide text to translate or reply to a text message.")


def build_default_request(
    args: Sequence[str],
    default_target_language: str,
    reply_text: str | None = None,
) -> TranslationRequest:
    """Build a request for the default target language."""

    return TranslationRequest(
        target_language=default_target_language,
        text=_collect_text(args, reply_text),
    )


def build_explicit_request(
    args: Sequence[str],
    reply_text: str | None = None,
) -> TranslationRequest:
    """Build a request that starts with a target language."""

    if not args:
        raise ValueError("Use /trto <idioma> <texto> or reply to a text message.")

    target_language = args[0].strip()
    if not target_language:
        raise ValueError("The target language cannot be empty.")

    try:
        target_language = resolve_language_code(target_language)
    except LanguageError as exc:
        raise ValueError(str(exc)) from exc

    return TranslationRequest(
        target_language=target_language,
        text=_collect_text(args[1:], reply_text),
    )


def split_telegram_text(text: str, limit: int = SAFE_MESSAGE_LENGTH) -> list[str]:
    """Split text into Telegram-safe message chunks."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit

        chunk = remaining[:split_at].rstrip()
        chunks.append(chunk or remaining[:limit])
        remaining = remaining[split_at:].lstrip()

    return chunks


class PreferenceStore(Protocol):
    """Store per-chat language preferences."""

    def get_chat_language(self, chat_id: int, default_language: str) -> str:
        """Return the target language for a chat."""

    def set_chat_language(self, chat_id: int, target_language: str) -> str:
        """Persist the target language for a chat."""

    def set_user_language(self, chat_id: int, user_id: int, language: str) -> str:
        """Persist one participant's language in a group."""

    def get_group_target_languages(self, chat_id: int, sender_user_id: int) -> list[str]:
        """Return languages needed by the other group participants."""

    def set_auto_translation(self, chat_id: int, enabled: bool) -> None:
        """Enable or disable automatic group translation."""

    def is_auto_translation_enabled(self, chat_id: int) -> bool:
        """Return whether automatic group translation is enabled."""

    def get_group_languages(self, chat_id: int) -> list[str]:
        """Return the participant languages configured in a group."""

    def get_user_language(self, chat_id: int, user_id: int) -> str | None:
        """Return one participant's configured language."""


@dataclass(slots=True)
class TelegramTranslatorBot:
    """Telegram bot that translates chat text."""

    settings: Settings
    translator: Translator | None = None
    preferences: PreferenceStore | None = None

    def __post_init__(self) -> None:
        if self.translator is None:
            self.translator = DeepTranslatorService()
        if self.preferences is None:
            self.preferences = create_preference_store(
                self.settings.data_file,
                supabase_url=self.settings.supabase_url,
                supabase_key=self.settings.supabase_key,
            )

    def build_application(self) -> Application:
        if not self.settings.bot_token:
            raise ConfigError("BOT_TOKEN is required but was not set.")

        application = (
            Application.builder()
            .token(self.settings.bot_token)
            .post_init(self.register_commands)
            .build()
        )
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("menu", self.menu))
        application.add_handler(CommandHandler("help", self.help))
        application.add_handler(CommandHandler(["config", "settings"], self.config))
        application.add_handler(CommandHandler("idioma", self.language_menu))
        application.add_handler(CommandHandler("lang", self.show_language))
        application.add_handler(CommandHandler("langs", self.list_languages))
        application.add_handler(CommandHandler("setlang", self.set_language))
        application.add_handler(CommandHandler("mylang", self.set_my_language))
        application.add_handler(CommandHandler(["autotr", "conversacion"], self.auto_translate))
        application.add_handler(CommandHandler("tr", self.translate_default_language))
        application.add_handler(CommandHandler("trto", self.translate_to_language))
        application.add_handler(
            CallbackQueryHandler(self.navigate_menu, pattern=r"^(menu|config):")
        )
        application.add_handler(
            CallbackQueryHandler(self.select_language_button, pattern=r"^(lang|mylang):")
        )
        application.add_handler(
            MessageHandler(
                filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
                self.translate_private_text,
            )
        )
        application.add_handler(
            MessageHandler(
                filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
                self.translate_group_text,
            )
        )
        application.add_error_handler(self.on_error)
        return application

    def run(self) -> None:
        """Start polling Telegram for updates."""

        self.build_application().run_polling()

    async def register_commands(self, application: Application) -> None:
        """Register Telegram's native command menu."""

        private_commands = [
            BotCommand("menu", "Abrir menu principal"),
            BotCommand("idioma", "Elegir idioma destino"),
            BotCommand("config", "Abrir configuracion"),
            BotCommand("help", "Ver ayuda"),
            BotCommand("tr", "Traducir un texto"),
            BotCommand("trto", "Traducir a otro idioma"),
        ]
        group_commands = [
            BotCommand("menu", "Abrir menu para todos"),
            BotCommand("mylang", "Registrar tu idioma"),
            BotCommand("autotr", "Controlar traduccion automatica"),
            BotCommand("config", "Ver configuracion del grupo"),
            BotCommand("help", "Ver ayuda"),
            BotCommand("tr", "Traducir un mensaje"),
            BotCommand("trto", "Traducir a otro idioma"),
        ]

        await application.bot.set_my_commands(private_commands)
        await application.bot.set_my_commands(
            private_commands,
            scope=BotCommandScopeAllPrivateChats(),
        )
        await application.bot.set_my_commands(
            group_commands,
            scope=BotCommandScopeAllGroupChats(),
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.menu(update, context)

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None:
            return

        target_language = self._target_language_for(update)
        await message.reply_text(
            self._main_menu_text(target_language, chat.type),
            reply_markup=build_main_menu_keyboard(self._is_group(chat.type)),
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        await message.reply_text(
            self._help_text(),
            reply_markup=build_help_keyboard(),
        )

    async def config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None:
            return

        auto_enabled = self._is_auto_translation_enabled(chat.id)
        await message.reply_text(
            self._config_text(update, auto_enabled),
            reply_markup=build_config_keyboard(
                self._is_group(chat.type),
                auto_enabled,
            ),
        )

    async def navigate_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        query = update.callback_query
        chat = update.effective_chat
        if query is None or chat is None:
            return

        await query.answer()
        action = query.data or "menu:main"
        is_group = self._is_group(chat.type)
        auto_enabled = self._is_auto_translation_enabled(chat.id)

        if action == "menu:main":
            await self._edit_query_message(
                query,
                self._main_menu_text(self._target_language_for(update), chat.type),
                build_main_menu_keyboard(is_group),
            )
        elif action == "menu:help":
            await self._edit_query_message(
                query,
                self._help_text(),
                build_help_keyboard(),
            )
        elif action == "menu:config":
            await self._edit_query_message(
                query,
                self._config_text(update, auto_enabled),
                build_config_keyboard(is_group, auto_enabled),
            )
        elif action == "menu:language":
            target_language = self._target_language_for(update)
            await self._edit_query_message(
                query,
                f"🌍 Elige idioma destino\nActual: {language_display(target_language)}",
                build_language_keyboard(target_language),
            )
        elif action == "menu:mylang":
            user = query.from_user
            selected_language = self._user_language_for(chat.id, user.id)
            await self._edit_query_message(
                query,
                "🗣️ Elige tu idioma\nPinkBabel traducira los mensajes de los demas para ti.",
                build_language_keyboard(selected_language, callback_prefix="mylang"),
            )
        elif action == "menu:translate":
            text = (
                "🌐 Traduccion manual\nUsa /tr <texto> o responde a un mensaje con /tr."
                if is_group
                else "🌐 Traduccion rapida\nEnviame cualquier texto y lo traducire al idioma configurado.\n"
                "Tambien puedes responder a un mensaje con /tr."
            )
            await self._edit_query_message(
                query,
                text,
                build_main_menu_keyboard(is_group),
            )
        elif action == "menu:conversation":
            await self._edit_query_message(
                query,
                self._conversation_help_text(is_group),
                build_config_keyboard(is_group, auto_enabled),
            )
        elif action == "config:mylang":
            user = query.from_user
            selected_language = self._user_language_for(chat.id, user.id)
            await self._edit_query_message(
                query,
                "🗣️ Elige tu idioma para esta conversacion.",
                build_language_keyboard(selected_language, callback_prefix="mylang"),
            )
        elif action in {"config:auto:on", "config:auto:off"}:
            enabled = action.endswith(":on")
            try:
                self.preferences.set_auto_translation(chat.id, enabled)
            except StorageError as exc:
                self._log_storage_error(exc)
                await self._edit_query_message(
                    query,
                    self._storage_error_text(),
                    build_config_keyboard(is_group, auto_enabled),
                )
                return
            await self._edit_query_message(
                query,
                self._config_text(update, enabled),
                build_config_keyboard(is_group, enabled),
            )

    async def language_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        target_language = self._target_language_for(update)
        await message.reply_text(
            f"🌍 Elige idioma destino\nActual: {language_display(target_language)}",
            reply_markup=build_language_keyboard(target_language),
        )

    async def select_language_button(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        query = update.callback_query
        chat = update.effective_chat
        if query is None or chat is None:
            return

        await query.answer()
        callback_data = query.data or ""
        prefix, _, raw_language = callback_data.partition(":")

        try:
            if prefix == "mylang":
                language_code = self.preferences.set_user_language(
                    chat.id,
                    query.from_user.id,
                    raw_language,
                )
            else:
                language_code = self.preferences.set_chat_language(chat.id, raw_language)
        except LanguageError:
            await self._edit_query_message(
                query,
                "⚠️ Ese idioma ya no esta disponible. Abre el menu de nuevo.",
            )
            return

        except StorageError as exc:
            self._log_storage_error(exc)
            await self._edit_query_message(query, self._storage_error_text())
            return

        if prefix == "mylang":
            text = (
                f"✅ Tu idioma fue guardado: {language_display(language_code)}\n"
                "La traduccion automatica ya puede usar esta preferencia."
            )
            keyboard = build_language_keyboard(language_code, callback_prefix="mylang")
        else:
            text = (
                f"✅ Idioma destino guardado: {language_display(language_code)}\n"
                "Ahora enviame cualquier texto para traducir."
            )
            keyboard = build_language_keyboard(language_code)

        await self._edit_query_message(query, text, keyboard)

    async def show_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        target_language = self._target_language_for(update)
        await message.reply_text(f"🌍 Idioma destino actual: {language_display(target_language)}")

    async def list_languages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        await message.reply_text(
            "🌍 Idiomas soportados:\n"
            + "\n".join(supported_language_lines())
            + "\n\nTambien puedes usar nombres como `english`, `espanol` o `frances`."
        )

    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None:
            return

        raw_language = " ".join(context.args).strip()
        if not raw_language:
            await message.reply_text("Uso: /setlang <idioma>\nEjemplo: /setlang english")
            return

        try:
            language_code = self.preferences.set_chat_language(chat.id, raw_language)
        except LanguageError as exc:
            await message.reply_text(f"⚠️ No reconozco ese idioma: {exc}\nUsa /langs para ver opciones.")
            return

        await message.reply_text(f"✅ Idioma destino guardado: {language_display(language_code)}")

    async def set_my_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if message is None or chat is None or user is None:
            return

        if chat.type not in {"group", "supergroup"}:
            await message.reply_text("👥 Este comando se usa dentro del grupo donde hablaran las dos personas.")
            return

        raw_language = " ".join(context.args).strip()
        if not raw_language:
            await message.reply_text("Uso: /mylang <idioma>\nEjemplo: /mylang espanol")
            return

        try:
            language_code = self.preferences.set_user_language(chat.id, user.id, raw_language)
        except LanguageError as exc:
            await message.reply_text(f"⚠️ No reconozco ese idioma: {exc}\nUsa /langs para ver opciones.")
            return

        await message.reply_text(
            f"✅ Tu idioma en este grupo es {language_display(language_code)}."
        )

    async def auto_translate(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None:
            return

        if chat.type not in {"group", "supergroup"}:
            await message.reply_text(
                "👥 La conversacion en tiempo real funciona en un grupo con PinkBabel y las dos personas."
            )
            return

        action = context.args[0].strip().lower() if context.args else "status"
        if action in {"on", "activar", "start"}:
            self.preferences.set_auto_translation(chat.id, True)
            await message.reply_text(
                "🟢 Traduccion automatica activada.\n"
                "Cada participante debe registrar su idioma con /mylang <idioma>."
            )
            return

        if action in {"off", "desactivar", "stop"}:
            self.preferences.set_auto_translation(chat.id, False)
            await message.reply_text("🔴 Traduccion automatica desactivada.")
            return

        if action not in {"status", "estado"}:
            await message.reply_text("Uso: /autotr on, /autotr off o /autotr status")
            return

        enabled = self._is_auto_translation_enabled(chat.id)
        languages = self._group_languages_for(chat.id)
        language_names = ", ".join(language_display(code) for code in languages) or "ninguno"
        await message.reply_text(
            f"💬 Traduccion automatica: {'activada' if enabled else 'desactivada'}\n"
            f"🗣️ Idiomas registrados: {language_names}"
        )

    async def translate_default_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        reply_text = getattr(getattr(message, "reply_to_message", None), "text", None)
        try:
            request = build_default_request(context.args, self._target_language_for(update), reply_text)
        except ValueError as exc:
            await message.reply_text(f"Uso: /tr <texto>\nDetalle: {exc}")
            return

        await self._translate_and_reply(update, request)

    async def translate_to_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        reply_text = getattr(getattr(message, "reply_to_message", None), "text", None)
        try:
            request = build_explicit_request(context.args, reply_text)
        except ValueError as exc:
            await message.reply_text(f"Uso: /trto <idioma> <texto>\nDetalle: {exc}")
            return

        await self._translate_and_reply(update, request)

    async def translate_private_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None:
            return

        if chat.type != "private":
            return

        request = TranslationRequest(
            target_language=self._target_language_for(update),
            text=message.text or "",
        )

        try:
            await self._translate_and_reply(update, request)
        except ValueError:
            return

    async def translate_group_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if message is None or chat is None or user is None:
            return

        if not self._is_auto_translation_enabled(chat.id):
            return

        text = (message.text or "").strip()
        if not text:
            return

        target_languages = self.preferences.get_group_target_languages(chat.id, user.id)
        if not target_languages:
            return

        translations = await asyncio.gather(
            *(self._translate_text(text, language) for language in target_languages[:3]),
            return_exceptions=True,
        )

        responses: list[str] = []
        translation_errors: list[TranslationError] = []
        for target_language, translated in zip(target_languages, translations):
            if isinstance(translated, Exception):
                if isinstance(translated, TranslationError):
                    translation_errors.append(translated)
                continue
            if translated.casefold() == text.casefold():
                continue
            responses.append(f"{language_display(target_language)}:\n{translated}")

        for response in responses:
            for chunk in split_telegram_text(response):
                await message.reply_text(chunk)

        if not responses and translation_errors:
            await message.reply_text(f"⚠️ No pude traducir el texto: {translation_errors[0]}")

    async def _translate_and_reply(self, update: Update, request: TranslationRequest) -> None:
        message = update.effective_message
        if message is None:
            return

        try:
            translated = await self._translate_text(request.text, request.target_language)
        except TranslationError as exc:
            await message.reply_text(f"⚠️ No pude traducir el texto: {exc}")
            return

        response = (
            f"🌐 Traduccion ({language_display(request.target_language)}):\n"
            f"{translated}\n\n"
            "Texto original:\n"
            f"{request.text}"
        )
        for chunk in split_telegram_text(response):
            await message.reply_text(chunk)

    async def _translate_text(self, text: str, target_language: str) -> str:
        translator = self.translator
        if translator is None:
            raise TranslationError("Translation service is not configured.")

        return await asyncio.to_thread(translator.translate, text, target_language)

    def _target_language_for(self, update: Update) -> str:
        chat = update.effective_chat
        if chat is None:
            return self.settings.target_language

        try:
            return self.preferences.get_chat_language(chat.id, self.settings.target_language)
        except StorageError as exc:
            self._log_storage_error(exc)
            return self.settings.target_language

    @staticmethod
    async def _edit_query_message(query, text: str, reply_markup=None) -> None:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    def _main_menu_text(self, target_language: str, chat_type: str) -> str:
        location = "grupo" if self._is_group(chat_type) else "chat privado"
        return (
            "🌸 PinkBabel\n\n"
            f"🌍 Idioma destino: {language_display(target_language)}\n"
            f"📍 Modo: {location}\n\n"
            "Elige una accion o enviame un texto."
        )

    def _config_text(self, update: Update, auto_enabled: bool) -> str:
        chat = update.effective_chat
        if chat is None:
            return "⚠️ Configuracion no disponible."

        target_language = self._target_language_for(update)
        lines = [
            "⚙️ Configuracion",
            f"🌍 Idioma destino: {language_display(target_language)}",
        ]
        if self._is_group(chat.type):
            languages = self._group_languages_for(chat.id)
            configured = ", ".join(language_display(code) for code in languages) or "ninguno"
            lines.extend(
                [
                    f"💬 Conversacion automatica: {'activada' if auto_enabled else 'desactivada'}",
                    f"🗣️ Idiomas registrados: {configured}",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _help_text() -> str:
        return (
            "❔ Ayuda PinkBabel\n\n"
            "🌐 Chat privado\n"
            "- Envia texto para traducirlo.\n"
            "- Usa /idioma para cambiar el destino.\n"
            "- Usa /trto <idioma> <texto> para una traduccion puntual.\n\n"
            "💬 Conversacion en grupo\n"
            "- Cada persona registra su idioma con /mylang <idioma>.\n"
            "- Activa con /autotr on.\n"
            "- Detenla con /autotr off."
        )

    @staticmethod
    def _conversation_help_text(is_group: bool) -> str:
        if not is_group:
            return (
                "💬 La conversacion automatica funciona dentro de un grupo.\n"
                "Agrega a PinkBabel y a la otra persona. Luego cada participante "
                "usa /mylang <idioma> y activa /autotr on."
            )
        return (
            "💬 Conversacion automatica\n\n"
            "1. Cada participante usa /mylang <idioma>.\n"
            "2. Activa la conversacion con el boton de configuracion.\n"
            "3. PinkBabel respondera con las traducciones necesarias."
        )

    def _is_auto_translation_enabled(self, chat_id: int) -> bool:
        try:
            return self.preferences.is_auto_translation_enabled(chat_id)
        except StorageError as exc:
            self._log_storage_error(exc)
            return False

    def _user_language_for(self, chat_id: int, user_id: int) -> str | None:
        try:
            return self.preferences.get_user_language(chat_id, user_id)
        except StorageError as exc:
            self._log_storage_error(exc)
            return None

    def _group_languages_for(self, chat_id: int) -> list[str]:
        try:
            return self.preferences.get_group_languages(chat_id)
        except StorageError as exc:
            self._log_storage_error(exc)
            return []

    @staticmethod
    def _storage_error_text() -> str:
        return (
            "No pude acceder a la configuracion guardada.\n"
            "Revisa SUPABASE_URL, SUPABASE_SECRET_KEY y las tablas pinkbabel_* en Supabase."
        )

    @staticmethod
    def _log_storage_error(exc: StorageError) -> None:
        print(f"Preference storage error: {exc}", file=sys.stderr)

    @staticmethod
    def _is_group(chat_type: str) -> bool:
        return chat_type in {"group", "supergroup"}

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        print(f"Telegram handler error: {context.error}", file=sys.stderr)

        message = getattr(update, "effective_message", None)
        if message is None:
            return

        try:
            await message.reply_text("⚠️ Se produjo un error inesperado. Intenta de nuevo.")
        except Exception:  # pragma: no cover - best effort only
            return
