#!/bin/sh
set -eu

umask 077

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
SECRET_DIR="$SCRIPT_DIR/secrets"
KEY_FILE="$SECRET_DIR/control_plane_api_key"

usage() {
    printf 'Usage: %s init|lock\n' "$0" >&2
    exit 2
}

init_files() {
    mkdir -p "$SECRET_DIR"
    chmod 700 "$SECRET_DIR"

    if [ ! -e "$ENV_FILE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        printf 'Created protected configuration file: %s\n' "$ENV_FILE"
    fi
    chmod 600 "$ENV_FILE"

    if [ ! -e "$KEY_FILE" ]; then
        : > "$KEY_FILE"
        printf 'Created protected runtime-key file: %s\n' "$KEY_FILE"
    fi
    chmod 600 "$KEY_FILE"

    printf '%s\n' 'Populate both files with a secure editor or protected file transfer, then run lock.'
}

lock_files() {
    if [ ! -s "$ENV_FILE" ]; then
        printf 'Configuration file is missing or empty: %s\n' "$ENV_FILE" >&2
        exit 1
    fi
    if [ ! -s "$KEY_FILE" ]; then
        printf 'Runtime-key file is missing or empty: %s\n' "$KEY_FILE" >&2
        exit 1
    fi

    chmod 600 "$ENV_FILE"
    chown 10001:10001 "$KEY_FILE"
    chmod 400 "$KEY_FILE"
    printf '%s\n' 'Tunnel credential permissions locked.'
}

case "${1:-}" in
    init)
        init_files
        ;;
    lock)
        lock_files
        ;;
    *)
        usage
        ;;
esac
