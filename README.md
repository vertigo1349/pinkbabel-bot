# mi_bot

A small, modular Telegram translation bot with a `src` layout, environment-based configuration, and basic tests.

## Setup

1. Create and activate a virtual environment.
2. Install the project in editable mode with the test tools:

```bash
pip install -e .[dev]
```

## Run

Start the bot with either of these commands:

```bash
mi-bot
```

or

```bash
python -m mi_bot.main
```

The bot listens for text commands and translates messages with a simple, testable flow.

Copy `.env.example` to `.env` and replace `BOT_TOKEN` with the token generated
by BotFather. Never commit `.env`.

## Commands

- `/start` shows a short welcome message
- `/menu` opens the main button menu
- `/help` shows usage help
- `/config` opens the configuration buttons
- `/tr <texto>` translates to the saved target language for the chat
- `/trto <idioma> <texto>` translates to a chosen language
- `/idioma` shows buttons to select the target language
- `/setlang <idioma>` saves the target language for the chat
- `/mylang <idioma>` registers your language inside a group conversation
- `/autotr on|off|status` controls automatic group translation
- `/conversacion on|off|status` is an alias for `/autotr`
- `/lang` shows the current target language
- `/langs` lists supported target languages

If you send a plain text message in a private chat, the bot translates it to the saved target language.

Examples:

```text
/menu
/config
/idioma
/setlang english
/tr hola mundo
/trto frances good morning
```

## Real-time conversation in a group

Telegram bots cannot read a private conversation between two people. To use
real-time translation, create a group containing both people and PinkBabel.

Before testing, allow PinkBabel to receive normal group messages:

1. Open `@BotFather`.
2. Send `/mybots` and select PinkBabel.
3. Open `Bot Settings`.
4. Open `Group Privacy`.
5. Disable group privacy.
6. Add PinkBabel to the conversation group.

Inside the group:

```text
Person A: open /menu, select "Mi idioma", then choose Espanol
Person B: open /menu, select "Mi idioma", then choose Ingles
Anyone:   /autotr on
```

From then on, PinkBabel replies to each new text with the translation needed
by the other registered participants. The text commands `/mylang espanol`
and `/mylang ingles` remain available as alternatives. Use `/autotr off`
to stop it.

## Environment variables

This project is set up to keep secrets out of code. Use environment variables for real credentials later.

- `BOT_TOKEN`: required Telegram bot token from BotFather
- `BOT_NAME`: optional display name used by the startup message
- `TARGET_LANG`: default language for translations, for example `es` or `en` (defaults to `es`)
- `BOT_DATA_FILE`: optional path for saved chat preferences (defaults to `bot_data.json`)
- `SUPABASE_URL`: Supabase project URL; enables durable storage when set
- `SUPABASE_SECRET_KEY`: server-only Supabase secret key; never commit or expose it

The translation backend uses internet access and a free translation library. If you want a different provider later, the code is already split so we can swap it cleanly.

## Supabase storage

PinkBabel uses Supabase automatically when both Supabase environment variables
are configured. Otherwise it falls back to the local JSON file.

1. Open the Supabase SQL Editor.
2. Run the complete file `supabase/schema.sql`.
3. In Supabase, copy the project URL from `Integrations > Data API`.
4. Create or copy a server secret key from `Settings > API Keys`.
5. Store both values only as environment variables.

The secret key bypasses Row Level Security and must only exist in Render or
another trusted server environment. The SQL schema blocks the public `anon`
and `authenticated` roles from reading or changing bot preferences.

## Deploy with Docker

Build the image:

```bash
docker build -t pinkbabel .
```

Run it with automatic restart and persistent preferences:

```bash
docker run -d \
  --name pinkbabel \
  --restart unless-stopped \
  --env-file .env \
  -v pinkbabel-data:/data \
  pinkbabel
```

View logs:

```bash
docker logs -f pinkbabel
```

Only one PinkBabel process may poll Telegram at a time. Stop the local Windows
process before starting the deployed container.

## Deploy on Render

The repository includes `render.yaml` for a native Python Web Service:

1. Push the project to GitHub.
2. In Render, select `New` and then `Blueprint`.
3. Connect the GitHub repository.
4. Enter a newly generated `BOT_TOKEN` when Render requests it.
5. Enter `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
6. Deploy the Blueprint.
7. Stop the local Windows process before the Render service starts polling.

PinkBabel exposes `/health` on Render's `PORT` while Telegram polling runs in
the same process.

The Free Web Service has important limitations:

- It spins down after 15 minutes without inbound HTTP traffic.
- Its filesystem is ephemeral. Supabase prevents user and group preferences
  from being lost after a restart or redeploy.
- Background Workers and persistent disks require a paid instance.

For reliable continuous operation, use a paid Background Worker. Supabase
already provides durable preference storage, so a persistent disk is optional.

## Production notes

- Rotate any Telegram token that has been shared in a message or screenshot.
- Use persistent storage mounted at `/data`; otherwise chat preferences are lost
  when the container is replaced.
- `deep-translator` is suitable for an initial release but uses an unofficial
  free translation backend. A paid official provider is recommended if usage
  or reliability requirements increase.
- Keep the host online continuously. The bot currently uses Telegram long
  polling and does not require a public HTTP port.

## Tests

Run the basic test suite with:

```bash
pytest
```

## Project layout

```text
src/mi_bot/bot.py
src/mi_bot/main.py
src/mi_bot/config.py
src/mi_bot/languages.py
src/mi_bot/storage.py
src/mi_bot/translator.py
supabase/schema.sql
tests/test_basic.py
```
