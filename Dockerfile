FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml ./
COPY agents ./agents
COPY config ./config
COPY scripts ./scripts
COPY shared ./shared

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

CMD ["bash", "scripts/run_news_briefing.sh"]
