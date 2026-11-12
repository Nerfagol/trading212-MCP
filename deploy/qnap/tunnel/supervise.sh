#!/bin/sh
# Run without privileges or Docker access. Docker owns container restarts.
set -u

tunnel-client run "$@" &
client_pid=$!
watch_pid=

cleanup() {
    trap '' TERM INT
    [ -z "$watch_pid" ] || kill "$watch_pid" 2>/dev/null || true
    kill -TERM "$client_pid" 2>/dev/null || true
    wait "$client_pid" 2>/dev/null || true
    [ -z "$watch_pid" ] || wait "$watch_pid" 2>/dev/null || true
}
trap 'cleanup; exit 0' TERM INT

(
    # Three-minute MCP wait plus time for catalog registration and first poll.
    sleep 210
    failures=0
    while kill -0 "$client_pid" 2>/dev/null; do
        if timeout -k 1 5 tunnel-client health --url=http://127.0.0.1:18080 \
            --require-control-plane-poll >/dev/null 2>&1; then
            failures=0
        else
            failures=$((failures + 1))
        fi
        if [ "$failures" -ge 3 ]; then
            printf '%s\n' 'Tunnel health failed repeatedly; requesting container restart.' >&2
            kill -TERM "$client_pid" 2>/dev/null || true
            sleep 5
            kill -KILL "$client_pid" 2>/dev/null || true
            exit 0
        fi
        sleep 30
    done
) &
watch_pid=$!

wait "$client_pid" 2>/dev/null || true
cleanup
# Even a clean unexpected child exit must let Docker recover the service.
exit 1
