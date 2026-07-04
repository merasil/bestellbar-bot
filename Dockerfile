FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && adduser --system --group --uid 10001 bestellbar \
    && mkdir -p /data \
    && chown -R bestellbar:bestellbar /data

USER bestellbar

CMD ["bestellbar-bot", "watch"]
