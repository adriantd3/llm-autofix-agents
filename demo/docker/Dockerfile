FROM python:3.13-slim

ENV UV_SYSTEM_PYTHON=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir uv

# Copiamos SOLO lo necesario primero (mejor cache)
COPY pyproject.toml .
COPY README.md .
COPY src ./src

# Instala deps
RUN uv sync

# Ahora copiamos el resto del proyecto
COPY demo/docker/test.py ./test.py

ENV OLLAMA_BASE_URL=http://host.docker.internal:11500/v1
ENV OLLAMA_MODEL=qwen3.5:9b
ENV OLLAMA_API_KEY=ollama

CMD ["uv", "run", "test.py"]