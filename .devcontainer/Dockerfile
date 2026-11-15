FROM mcr.microsoft.com/devcontainers/python:3.15

# GL/EGL libraries for offscreen VTK rendering and OpenCASCADE.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libegl1 libxrender1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv manages the Python environment from pyproject.toml / uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /usr/local/bin/
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN mkdir -p /opt/venv
