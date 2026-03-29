FROM ghcr.io/astral-sh/uv:debian
WORKDIR /app
COPY .python-version /app/
COPY pyproject.toml /app/
COPY pytest.ini /app/
COPY README.md /app/
RUN uv sync
COPY ./backend /app/backend