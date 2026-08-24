FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root

COPY src ./src
COPY infra ./infra
RUN poetry install --only main

CMD ["uvicorn", "order_pipeline.api.main:app", "--host", "0.0.0.0", "--port", "8000"]