ARG VERSION=0.1.0
ARG REVISION=unknown

FROM python:3.12-slim AS builder

ARG VERSION

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ARG VERSION
ARG REVISION

LABEL org.opencontainers.image.title="Trading 212 Read-Only MCP Server" \
    org.opencontainers.image.description="Strictly read-only self-hosted Trading 212 MCP server" \
    org.opencontainers.image.source="https://github.com/Nerfagol/trading212-MCP" \
    org.opencontainers.image.url="https://github.com/Nerfagol/trading212-MCP" \
    org.opencontainers.image.revision="${REVISION}" \
    org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.licenses="MIT" \
    io.modelcontextprotocol.server.name="io.github.nerfagol/trading212-mcp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels "trading212-mcp==${VERSION}" \
    && rm -rf /wheels

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "trading212_mcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
