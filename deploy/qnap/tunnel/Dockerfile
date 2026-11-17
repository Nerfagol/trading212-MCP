FROM ghcr.io/openai/tunnel-client:0.0.21@sha256:983df88cd56d49ae3863ae52b751d106c95aba8a03783c87ac2304b4e0cd154a AS upstream

FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf

RUN apk add --no-cache ca-certificates \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app

# The direct OpenAI polling transport needs only this official binary.
# Do not copy the optional cloudflared helper or other upstream image contents.
COPY --from=upstream /usr/bin/tunnel-client /usr/bin/tunnel-client
COPY deploy/qnap/tunnel/supervise.sh /usr/local/bin/tunnel-supervise

LABEL org.opencontainers.image.title="Trading 212 private MCP tunnel" \
    org.opencontainers.image.source="https://github.com/Nerfagol/trading212-MCP" \
    org.opencontainers.image.version="0.0.21"

USER 10001:10001
ENTRYPOINT ["/bin/sh", "/usr/local/bin/tunnel-supervise"]
