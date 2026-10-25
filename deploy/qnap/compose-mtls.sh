# Shared by the scoped deploy/update/verify commands; never source credential files.
if [ -f "$SCRIPT_DIR/mtls.enabled" ]; then
    for name in server/ca.crt server/server.crt server/server.key server/health.crt \
        server/health.key tunnel/ca.crt tunnel/tunnel.crt tunnel/tunnel.key; do
        [ -s "$SCRIPT_DIR/secrets/mtls/$name" ] || {
            echo 'Enabled mTLS material is incomplete; refusing plaintext fallback.' >&2
            exit 1
        }
    done
fi

compose_mcp() {
    mode=$1
    shift
    if [ -f "$SCRIPT_DIR/mtls.enabled" ] && [ "${1:-}" = up ]; then
        shift
        set -- up --force-recreate "$@"
    fi
    if [ "$mode" = snapshots ]; then
        if [ -f "$SCRIPT_DIR/storage.conf" ]; then
            set -- -f "$SCRIPT_DIR/docker-compose.logs.yml" "$@"
        fi
        set -- -f "$PROJECT_DIR/docker-compose.snapshots.yml" "$@"
    fi
    if [ -f "$SCRIPT_DIR/mtls.enabled" ]; then
        set -- -f "$SCRIPT_DIR/docker-compose.mtls.yml" "$@"
    fi
    set -- -f "$PROJECT_DIR/docker-compose.yml" "$@"
    if [ -f "$SCRIPT_DIR/storage.conf" ]; then
        set -- --env-file "$SCRIPT_DIR/storage.conf" "$@"
    fi
    "$DOCKER" compose --env-file "$PROJECT_DIR/.env" "$@"
}

compose_tunnel() {
    if [ -f "$SCRIPT_DIR/mtls.enabled" ]; then
        if [ "${1:-}" = up ]; then
            shift
            set -- up --force-recreate "$@"
        fi
        "$DOCKER" compose --env-file "$PROJECT_DIR/.env" --env-file "$TUNNEL_DIR/.env" \
            -f "$TUNNEL_DIR/docker-compose.yml" -f "$TUNNEL_DIR/docker-compose.mtls.yml" "$@"
    else
        "$DOCKER" compose --env-file "$TUNNEL_DIR/.env" \
            -f "$TUNNEL_DIR/docker-compose.yml" "$@"
    fi
}
