FROM ghcr.io/openai/tunnel-client:0.0.19@sha256:dcae53be336c062ffdc3f250a287b2a07724c344b8c370a50f54ad033af43151 AS upstream

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
