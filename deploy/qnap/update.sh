#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd "$SCRIPT_DIR/../.." && pwd)
TUNNEL_DIR="$SCRIPT_DIR/tunnel"

usage() {
    printf 'Usage: %s mcp|tunnel|all\n' "$0" >&2
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

require_nonempty() {
    if [ ! -s "$1" ]; then
        printf 'Required protected file is missing or empty: %s\n' "$1" >&2
        exit 1
    fi
}

DOCKER=$(find_docker)

update_mcp() {
    require_nonempty "$PROJECT_DIR/.env"
    "$DOCKER" compose \
        --env-file "$PROJECT_DIR/.env" \
        -f "$PROJECT_DIR/docker-compose.yml" \
        build --pull
    "$DOCKER" compose \
        --env-file "$PROJECT_DIR/.env" \
        -f "$PROJECT_DIR/docker-compose.yml" \
        up -d
}

update_tunnel() {
    require_nonempty "$TUNNEL_DIR/.env"
    require_nonempty "$TUNNEL_DIR/secrets/control_plane_api_key"
    "$DOCKER" compose \
        --env-file "$TUNNEL_DIR/.env" \
        -f "$TUNNEL_DIR/docker-compose.yml" \
        pull
    "$DOCKER" compose \
        --env-file "$TUNNEL_DIR/.env" \
        -f "$TUNNEL_DIR/docker-compose.yml" \
        up -d
}

case "${1:-}" in
    mcp)
        update_mcp
        ;;
    tunnel)
        update_tunnel
        ;;
    all)
        update_mcp
        update_tunnel
        ;;
    *)
        usage
        ;;
esac
