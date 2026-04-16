FROM python:3.13-slim

ENV UV_SYSTEM_PYTHON=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git nodejs npm docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir uv

WORKDIR /workspace

COPY pyproject.toml README.md Makefile /workspace/
COPY src /workspace/src
COPY tests /workspace/tests
COPY docker /workspace/docker

RUN uv sync

CMD ["sh", "-lc", "sleep infinity"]
