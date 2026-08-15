#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
TUNNEL_DIR="$SCRIPT_DIR/tunnel"

usage() {
    printf 'Usage: %s [mcp|tunnel|all]\n' "$0" >&2
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
    "$DOCKER" exec trading212-mcp python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

    binding=$($DOCKER port trading212-mcp 8000/tcp 2>/dev/null || true)
    case "$binding" in
        0.0.0.0:*|'[::]':*)
            printf '%s\n' 'MCP port is bound to a wildcard address: FAIL' >&2
            exit 1
            ;;
        '')
            printf '%s\n' 'MCP published-port binding was not found: FAIL' >&2
            exit 1
            ;;
    esac

    "$DOCKER" exec -i trading212-mcp python - http://127.0.0.1:8000/mcp \
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

    if "$DOCKER" compose \
        --env-file "$TUNNEL_DIR/.env" \
        -f "$TUNNEL_DIR/docker-compose.yml" \
        run --rm \
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

case "${1:-all}" in
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
