ARG VERSION=0.0.0+local
ARG REVISION=unknown

FROM python:3.12-alpine3.24 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY requirements.txt requirements-build.txt ./
COPY src ./src
RUN python -m pip install --require-hashes -r requirements-build.txt \
    && python -m pip download --require-hashes --only-binary=:all: \
       --dest /wheels -r requirements.txt \
    && python -m pip wheel --no-build-isolation --no-deps --wheel-dir /wheels .

FROM python:3.12-alpine3.24 AS runtime

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

RUN addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app

COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels --require-hashes \
       -r /tmp/requirements.txt \
    && python -m pip install --no-index --no-deps --find-links=/wheels trading212-mcp \
    && rm -rf /wheels /tmp/requirements.txt

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-m", "trading212_mcp.tls"]

CMD ["python", "-m", "trading212_mcp.server"]
