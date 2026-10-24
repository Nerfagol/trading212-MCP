FROM ghcr.io/openai/tunnel-client:v0.0.18@sha256:486321616c197fed2d3fbe7d44f22433ce9a1e6c1ee434c0d6652868a5fda5c1 AS upstream

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a

RUN apk add --no-cache ca-certificates \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app

# The direct OpenAI polling transport needs only this official binary.
# Do not copy the optional cloudflared helper or other upstream image contents.
COPY --from=upstream /usr/bin/tunnel-client /usr/bin/tunnel-client

LABEL org.opencontainers.image.title="Trading 212 private MCP tunnel" \
    org.opencontainers.image.source="https://github.com/Nerfagol/trading212-MCP" \
    org.opencontainers.image.version="0.0.18"

USER 10001:10001
ENTRYPOINT ["/usr/bin/tunnel-client", "run"]
