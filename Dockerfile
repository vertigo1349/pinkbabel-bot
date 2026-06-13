FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_DATA_FILE=/data/bot_data.json

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .
RUN useradd --create-home bot \
    && mkdir -p /data \
    && chown -R bot:bot /app /data

USER bot

CMD ["python", "-m", "mi_bot.main"]
