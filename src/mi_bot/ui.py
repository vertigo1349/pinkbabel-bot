"""Telegram menu and keyboard builders for PinkBabel."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .languages import FEATURED_LANGUAGE_CODES, SUPPORTED_LANGUAGES

ICON_BACK = "\u2b05\ufe0f"
ICON_CHECK = "\u2705"
ICON_CONFIG = "\u2699\ufe0f"
ICON_GROUP = "\U0001f465"
ICON_HELP = "\u2754"
ICON_LANGUAGE = "\U0001f30d"
ICON_SPEAK = "\U0001f5e3\ufe0f"
ICON_TRANSLATE = "\U0001f310"
ICON_CHAT = "\U0001f4ac"
ICON_ON = "\U0001f7e2"
ICON_OFF = "\U0001f534"


def build_main_menu_keyboard(is_group: bool) -> InlineKeyboardMarkup:
    """Build the main navigation menu."""

    language_label = f"{ICON_SPEAK} Mi idioma" if is_group else f"{ICON_LANGUAGE} Idioma"
    language_callback = "menu:mylang" if is_group else "menu:language"
    rows = [
        [
            InlineKeyboardButton(f"{ICON_TRANSLATE} Traducir", callback_data="menu:translate"),
            InlineKeyboardButton(language_label, callback_data=language_callback),
        ],
        [
            InlineKeyboardButton(f"{ICON_HELP} Ayuda", callback_data="menu:help"),
            InlineKeyboardButton(f"{ICON_CONFIG} Config", callback_data="menu:config"),
        ],
    ]
    if is_group:
        rows.insert(
            1,
            [InlineKeyboardButton(f"{ICON_CHAT} Conversacion", callback_data="menu:conversation")],
        )
    return InlineKeyboardMarkup(rows)


def build_help_keyboard() -> InlineKeyboardMarkup:
    """Build navigation for the help screen."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{ICON_LANGUAGE} Idioma", callback_data="menu:language"),
                InlineKeyboardButton(f"{ICON_CONFIG} Config", callback_data="menu:config"),
            ],
            [InlineKeyboardButton(f"{ICON_BACK} Menu", callback_data="menu:main")],
        ]
    )


def build_config_keyboard(is_group: bool, auto_enabled: bool) -> InlineKeyboardMarkup:
    """Build the configuration controls."""

    rows = [
        [InlineKeyboardButton(f"{ICON_LANGUAGE} Cambiar idioma", callback_data="menu:language")],
    ]
    if is_group:
        action = "off" if auto_enabled else "on"
        label = (
            f"{ICON_OFF} Detener conversacion"
            if auto_enabled
            else f"{ICON_ON} Activar conversacion"
        )
        rows.append([InlineKeyboardButton(label, callback_data=f"config:auto:{action}")])
        rows.append(
            [InlineKeyboardButton(f"{ICON_SPEAK} Configurar mi idioma", callback_data="config:mylang")]
        )
    else:
        rows.append([InlineKeyboardButton(f"{ICON_GROUP} Usar en grupo", callback_data="menu:conversation")])
    rows.append([InlineKeyboardButton(f"{ICON_BACK} Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def build_language_keyboard(
    selected_language: str | None = None,
    callback_prefix: str = "lang",
) -> InlineKeyboardMarkup:
    """Build a compact language selector for Telegram."""

    buttons = []
    for code in FEATURED_LANGUAGE_CODES:
        language = SUPPORTED_LANGUAGES[code]
        marker = f"{ICON_CHECK} " if code == selected_language else ""
        buttons.append(
            InlineKeyboardButton(
                f"{marker}{language.name}",
                callback_data=f"{callback_prefix}:{code}",
            )
        )

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(f"{ICON_BACK} Volver", callback_data="menu:config")])
    return InlineKeyboardMarkup(rows)
