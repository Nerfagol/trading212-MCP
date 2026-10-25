#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd "$SCRIPT_DIR/../.." && pwd)
TUNNEL_DIR="$SCRIPT_DIR/tunnel"

usage() {
    printf 'Usage: %s [mcp|snapshots|tunnel|all]\n' "$0" >&2
    exit 2
}

find_docker() {
    if [ -n "${DOCKER_BIN:-}" ]; then
        if [ ! -x "$DOCKER_BIN" ]; then
            printf 'DOCKER_BIN is not executable: %s\n' "$DOCKER_BIN" >&2
            exit 1
        fi
        printf '%s\n' "$DOCKER_BIN"
        return
    fi

    qnap_docker=/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker
    if [ -x "$qnap_docker" ]; then
        printf '%s\n' "$qnap_docker"
        return
    fi

    if command -v docker >/dev/null 2>&1; then
        command -v docker
        return
    fi

    printf '%s\n' 'Docker was not found. Set DOCKER_BIN to the Container Station Docker path.' >&2
    exit 1
}

require_running() {
    state=$($DOCKER inspect --format '{{.State.Status}}' "$1" 2>/dev/null || true)
    if [ "$state" != running ]; then
        printf 'Container is not running: %s\n' "$1" >&2
        exit 1
    fi
}

verify_mcp() {
    require_running trading212-mcp
    if [ -f "$SCRIPT_DIR/mtls.enabled" ]; then
        for cert in server/server.crt server/health.crt tunnel/tunnel.crt; do
            openssl x509 -checkend 7776000 -noout \
                -in "$SCRIPT_DIR/secrets/mtls/$cert" >/dev/null 2>&1 || {
                echo 'mTLS certificate invalid or expires within 90 days; renew it.' >&2
                exit 1
            }
        done
    fi
    "$DOCKER" exec trading212-mcp python -m trading212_mcp.tls

    binding=$($DOCKER port trading212-mcp 8000/tcp 2>/dev/null || true)
    "$DOCKER" exec -i trading212-mcp python - --check-bindings "$binding" \
        < "$SCRIPT_DIR/verify_mcp.py"

    scheme=http
    [ ! -f "$SCRIPT_DIR/mtls.enabled" ] || scheme=https
    "$DOCKER" exec -i trading212-mcp python - "$scheme://127.0.0.1:8000/mcp" \
        < "$SCRIPT_DIR/verify_mcp.py"
    printf '%s\n' 'MCP health and LAN binding: PASS'
}

verify_tunnel() {
    require_running openai-mcp-tunnel
    command -v curl >/dev/null 2>&1 || {
        printf '%s\n' 'curl is required for tunnel health verification.' >&2
        exit 1
    }
    curl -fsS -o /dev/null http://127.0.0.1:18080/healthz
    curl -fsS -o /dev/null http://127.0.0.1:18080/readyz

    port_bindings=$($DOCKER inspect --format '{{json .HostConfig.PortBindings}}' openai-mcp-tunnel)
    if [ "$port_bindings" != null ] && [ "$port_bindings" != '{}' ]; then
        printf '%s\n' 'Tunnel container has published ports: FAIL' >&2
        exit 1
    fi

    if [ -f "$SCRIPT_DIR/mtls.enabled" ]; then
        # v0.0.18 doctor omits the MCP client certificate from its diagnostic
        # transport. Runtime startup probes use the correct mTLS transport.
        "$DOCKER" exec openai-mcp-tunnel /usr/bin/tunnel-client health \
            --url=http://127.0.0.1:18080 --require-control-plane-poll >/dev/null 2>&1
        printf '%s\n' 'Tunnel authenticated startup probe and active polling: PASS'
    elif compose_tunnel run --rm \
        -e HEALTH_LISTEN_ADDR=127.0.0.1:18081 \
        --entrypoint /usr/bin/tunnel-client \
        tunnel-client doctor \
        --control-plane.api-key=file:/run/secrets/control_plane_api_key \
        --explain >/dev/null 2>&1; then
        printf '%s\n' 'Tunnel doctor: PASS'
    else
        printf '%s\n' 'Tunnel doctor: FAIL' >&2
        exit 1
    fi
    printf '%s\n' 'Tunnel health, readiness, and control-plane polling: PASS'
    printf '%s\n' 'ChatGPT-side tool discovery is verified when the app is created in ChatGPT Web.'
}

DOCKER=$(find_docker)
. "$SCRIPT_DIR/compose-mtls.sh"

verify_snapshots() {
    verify_mcp
    require_running trading212-snapshots
    "$DOCKER" exec trading212-snapshots python -m trading212_mcp.collector --health
    reader=$("$DOCKER" inspect --format '{{range .Mounts}}{{if eq .Destination "/snapshots"}}{{.RW}}{{end}}{{end}}' trading212-mcp)
    writer=$("$DOCKER" inspect --format '{{range .Mounts}}{{if eq .Destination "/snapshots"}}{{.RW}}{{end}}{{end}}' trading212-snapshots)
    [ "$reader" = false ] && [ "$writer" = true ] || {
        printf '%s\n' 'Snapshot mount permissions: FAIL' >&2
        exit 1
    }
    ports=$("$DOCKER" inspect --format '{{json .HostConfig.PortBindings}}' trading212-snapshots)
    [ "$ports" = null ] || [ "$ports" = '{}' ] || {
        printf '%s\n' 'Collector has published ports: FAIL' >&2
        exit 1
    }
    printf '%s\n' 'Snapshot collector health and mount permissions: PASS'
}

case "${1:-all}" in
    snapshots)
        verify_snapshots
        ;;
    mcp)
        verify_mcp
        ;;
    tunnel)
        verify_tunnel
        ;;
    all)
        verify_mcp
        verify_tunnel
        ;;
    *)
        usage
        ;;
esac
