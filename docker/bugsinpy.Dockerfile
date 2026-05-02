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

# Install BugsInPy tools
RUN git clone --depth 1 https://github.com/soarsmu/BugsInPy.git /opt/bugsinpy \
    && chmod +x /opt/bugsinpy/framework/bin/* \
    && git config --system --add safe.directory /opt/bugsinpy \
    && chmod -R a+w /opt/bugsinpy
ENV PATH="/opt/bugsinpy/framework/bin:${PATH}"

WORKDIR /workspace

COPY pyproject.toml README.md Makefile /workspace/
COPY src /workspace/src
COPY tests /workspace/tests
COPY docker /workspace/docker

RUN uv sync \
    && chmod -R a+rX /workspace/.venv

CMD ["uv", "run", "autofix", "run"]
