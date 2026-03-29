FROM ghcr.io/astral-sh/uv:debian
WORKDIR /app

# Copy dependency manifests first for layer caching.
COPY backend-module/.python-version /app/
COPY backend-module/pyproject.toml  /app/
COPY backend-module/pytest.ini      /app/
COPY backend-module/README.md       /app/
COPY backend-module/main.py         /app/

RUN uv sync && mkdir -p /app/logs

# Copy application source.
COPY backend-module/backend /app/backend

# Copy LLM agent package (imported directly by Celery worker).
COPY llm_agents /app/llm_agents
