# Non-root FastAPI/Celery image for the DocIntel backend.
# Build context is backend/ (pyproject.toml + uv.lock live there).

FROM ghcr.io/astral-sh/uv:0.6.14 AS uv

FROM python:3.11.11-slim-bookworm

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libtesseract5 libpng-dev libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=uv /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
# README is referenced by pyproject but not needed to resolve deps.
RUN touch README.md \
    && uv sync --locked --no-dev --no-install-project \
    && rm README.md

COPY app ./app
RUN uv sync --locked --no-dev --no-install-project \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Factory form: settings are validated at create_app() via get_settings().
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
