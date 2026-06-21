"""Telegram menu and keyboard builders for PinkBabel."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .languages import FEATURED_LANGUAGE_CODES, SUPPORTED_LANGUAGES


def build_main_menu_keyboard(is_group: bool) -> InlineKeyboardMarkup:
    """Build the main navigation menu."""

    language_label = "🗣️ Mi idioma" if is_group else "🌍 Idioma"
    language_callback = "menu:mylang" if is_group else "menu:language"
    rows = [
        [
            InlineKeyboardButton("🌐 Traducir", callback_data="menu:translate"),
            InlineKeyboardButton(language_label, callback_data=language_callback),
        ],
        [
            InlineKeyboardButton("❔ Ayuda", callback_data="menu:help"),
            InlineKeyboardButton("⚙️ Config", callback_data="menu:config"),
        ],
    ]
    if is_group:
        rows.insert(
            1,
            [InlineKeyboardButton("💬 Conversacion", callback_data="menu:conversation")],
        )
    return InlineKeyboardMarkup(rows)


def build_help_keyboard() -> InlineKeyboardMarkup:
    """Build navigation for the help screen."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌍 Idioma", callback_data="menu:language"),
                InlineKeyboardButton("⚙️ Config", callback_data="menu:config"),
            ],
            [InlineKeyboardButton("⬅️ Menu", callback_data="menu:main")],
        ]
    )


def build_config_keyboard(is_group: bool, auto_enabled: bool) -> InlineKeyboardMarkup:
    """Build the configuration controls."""

    rows = [
        [InlineKeyboardButton("🌍 Cambiar idioma", callback_data="menu:language")],
    ]
    if is_group:
        action = "off" if auto_enabled else "on"
        label = "🔴 Detener conversacion" if auto_enabled else "🟢 Activar conversacion"
        rows.append([InlineKeyboardButton(label, callback_data=f"config:auto:{action}")])
        rows.append([InlineKeyboardButton("🗣️ Configurar mi idioma", callback_data="config:mylang")])
    else:
        rows.append([InlineKeyboardButton("👥 Usar en grupo", callback_data="menu:conversation")])
    rows.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def build_language_keyboard(
    selected_language: str | None = None,
    callback_prefix: str = "lang",
) -> InlineKeyboardMarkup:
    """Build a compact language selector for Telegram."""

    buttons = []
    for code in FEATURED_LANGUAGE_CODES:
        language = SUPPORTED_LANGUAGES[code]
        marker = "✅ " if code == selected_language else ""
        buttons.append(
            InlineKeyboardButton(
                f"{marker}{language.name}",
                callback_data=f"{callback_prefix}:{code}",
            )
        )

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu:config")])
    return InlineKeyboardMarkup(rows)
