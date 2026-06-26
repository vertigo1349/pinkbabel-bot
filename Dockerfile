FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_DATA_FILE=/data/bot_data.json \
    WEBHOOK_URL=https://pinkbabel-bot.onrender.com \
    WEBHOOK_PATH=telegram

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .
RUN useradd --create-home bot \
    && mkdir -p /data \
    && chown -R bot:bot /app /data

USER bot

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 mi_bot.webhook:flask_app"]
