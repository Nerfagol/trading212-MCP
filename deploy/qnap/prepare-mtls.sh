#!/bin/sh
# Generate locally: never print or transfer private keys.
set -eu
umask 077
[ "$#" = 2 ] || { printf 'Usage: %s NEW_DIRECTORY NAS_IPV4\n' "$0" >&2; exit 2; }
target=$1
address=$2
case "$address" in ''|*[!0-9.]*) echo 'A NAS IPv4 address is required.' >&2; exit 2;; esac
command -v openssl >/dev/null 2>&1 || { echo 'openssl is required.' >&2; exit 1; }
mkdir "$target" || { echo 'Use a new directory; existing keys are never overwritten.' >&2; exit 1; }
trap 'echo "Certificate preparation failed; do not enable this directory." >&2' 0
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 1825 \
    -subj /CN=Trading212-Private-MCP-CA \
    -addext basicConstraints=critical,CA:TRUE,pathlen:0 \
    -addext keyUsage=critical,keyCertSign,cRLSign \
    -keyout "$target/ca.key" -out "$target/ca.crt" >/dev/null 2>&1
for role in server tunnel health; do
    case "$role" in
        server) directory="$target/server"; purpose=serverAuth;;
        tunnel) directory="$target/tunnel"; purpose=clientAuth;;
        health) directory="$target/server"; purpose=clientAuth;;
    esac
    mkdir -p "$directory"
    openssl req -new -newkey rsa:3072 -nodes -sha256 -subj "/CN=trading212-$role" \
        -keyout "$directory/$role.key" -out "$target/$role.csr" >/dev/null 2>&1
    {
        echo 'basicConstraints=critical,CA:FALSE'
        echo 'keyUsage=critical,digitalSignature,keyEncipherment'
        echo "extendedKeyUsage=$purpose"
        echo 'subjectKeyIdentifier=hash'
        echo 'authorityKeyIdentifier=keyid,issuer'
        if [ "$role" = server ]; then
            printf 'subjectAltName=DNS:localhost,DNS:trading212-mcp,IP:127.0.0.1,IP:%s\n' "$address"
        fi
    } > "$target/extensions.cnf"
    openssl x509 -req -sha256 -days 365 -in "$target/$role.csr" \
        -CA "$target/ca.crt" -CAkey "$target/ca.key" -CAcreateserial \
        -extfile "$target/extensions.cnf" -out "$directory/$role.crt" >/dev/null 2>&1
    [ -f "$directory/ca.crt" ] || cp "$target/ca.crt" "$directory/ca.crt"
    chmod 400 "$directory/$role.key"
    chmod 444 "$directory/$role.crt" "$directory/ca.crt"
    rm "$target/$role.csr"
done
rm "$target/extensions.cnf" "$target/ca.srl"
chmod 600 "$target/ca.key"
chmod 700 "$target/server" "$target/tunnel"
if [ "$(id -u)" = 0 ]; then
    chown -R 10001:10001 "$target/server" "$target/tunnel"
fi
trap - 0
echo 'Certificates generated. Leaves expire in 365 days; CA key is not mounted.'
