FROM python:3.8-slim

# Dual-Python strategy:
#   - System python3 (3.8): used by bugsinpy-compile to create bug venvs.
#     BugsInPy projects require Python 3.6.9–3.8.3; 3.8 covers 96%+ of the
#     dataset. Venvs created here symlink to /usr/local/bin/python3 (3.8),
#     and agent test execution happens in THIS same container so the symlink
#     always resolves correctly.
#   - uv-managed Python 3.13 (UV_PYTHON_INSTALL_DIR=/opt/uv-python): used
#     exclusively by our agent code (pyproject.toml requires >=3.13).
#     UV_SYSTEM_PYTHON is NOT set so uv downloads its own Python 3.13 into
#     /opt/uv-python (world-readable after chmod), isolated from system 3.8.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git nodejs npm docker.io dos2unix curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (manages its own Python 3.13, isolated from system python3=3.8)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv

# Install BugsInPy tools
# Patch bugsinpy-compile to use `pip install -r <file>` instead of
# `xargs -I {} pip install {}` (92 separate pip processes → ~5 min;
# batch install with -r → ~30 s when wheels are cached).
COPY docker/patch-bugsinpy-compile.py /tmp/patch-bugsinpy-compile.py
RUN git clone --depth 1 https://github.com/soarsmu/BugsInPy.git /opt/bugsinpy \
    && chmod +x /opt/bugsinpy/framework/bin/* \
    && git config --system --add safe.directory /opt/bugsinpy \
    && chmod -R a+w /opt/bugsinpy \
    && python3 /tmp/patch-bugsinpy-compile.py
ENV PATH="/opt/bugsinpy/framework/bin:${PATH}"

WORKDIR /workspace

COPY pyproject.toml README.md Makefile /workspace/
COPY src /workspace/src
COPY tests /workspace/tests
COPY docker /workspace/docker

# uv downloads Python 3.13 into /opt/uv-python then syncs the project venv.
# chmod makes both accessible to the non-root uid used at runtime.
RUN uv sync \
    && chmod -R a+rX /workspace/.venv \
    && chmod -R a+rX /opt/uv-python

CMD ["uv", "run", "python", "-m", "llm_autofix_agents.batch.executor"]
