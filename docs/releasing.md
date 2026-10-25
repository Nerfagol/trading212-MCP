# Release and MCP Registry Readiness

Release operations are intentionally separate from normal pull-request CI.
Only a published GitHub Release can run the GHCR publishing workflow.

`pyproject.toml` is the source of truth for the Python package version. Runtime
MCP metadata and the HTTP User-Agent read the installed distribution version.
`server.json` remains explicit release metadata, and the test suite requires its
version to match `pyproject.toml`.

## Current release

[GitHub release 0.2.0](https://github.com/Nerfagol/trading212-MCP/releases/tag/v0.2.0)
includes fourteen tools, optional native mTLS, four-hour CSV history, private
rotating operational logs, locked dependencies and strict image audits.
The wheel, source archive and `SHA256SUMS` are attached to the release.

The published GHCR image supports `linux/amd64` and `linux/arm64`. Both published
platforms passed installed-version/MCP metadata/User-Agent/health/tool discovery
checks and scans with zero HIGH/CRITICAL findings at release verification time.
`latest` and `0.2.0` resolve to the same verified multi-platform index:

```text
sha256:43c4c4e4af9b3c2ec07aeba68c6e8907690ced6e0213413d5b5a4d02bcebccf9
```

`server.json` pins this published digest. No PyPI or MCP Registry publication is
performed by this GitHub/GHCR release. Existing NAS containers are not upgraded
automatically; preserve private credentials, TLS identities and snapshot paths
when choosing to upgrade. The old 0.1.0 image predates these features and fixes.

Source distributions explicitly exclude credentials, TLS private directories,
financial storage, deployment markers and backup/staging state, even when built
outside Git. Sanitized `.env.example` templates remain included. Wheels contain
only the Python package and standard distribution metadata; NAS configuration
and persistent data remain outside the installed package.

## Install the published image

Create a private project directory and protected `.env` from the release's
sanitized template. Start with Demo credentials. For a new local installation:

```sh
docker pull ghcr.io/nerfagol/trading212-mcp:0.2.0
docker run -d --name trading212-mcp --restart unless-stopped --init \
  --read-only --tmpfs /tmp:size=16m,mode=1777 \
  --cap-drop ALL --security-opt no-new-privileges \
  --env-file .env -p 127.0.0.1:8000:8000 \
  ghcr.io/nerfagol/trading212-mcp:0.2.0
curl --fail --silent http://127.0.0.1:8000/health
```

Expected health is `{"status":"ok"}`. Keep local port 8000 on loopback. Use the
[QNAP guide](qnap-deployment.md), [mTLS procedure](qnap-deployment.md#mutual-tls-on-the-nas)
and [snapshots guide](snapshots.md) for a NAS or authenticated deployment. Use
the supplied Compose scripts when those overlays are enabled; the bare local
example is not a replacement for an existing mTLS/snapshot configuration.

## Release gate

Before tagging a release, verify the final `main` commit:

```bash
ruff check .
mypy src tests
pytest
python -m build
docker build -t trading212-mcp:release-check .
```

Review the full diff, run `pytest tests/test_security.py -q`, and confirm that
tracked files contain no credentials or generated build artifacts.

## GitHub and GHCR release

For a new version, first complete the release gate on the final `main` commit.
After explicit owner authorization, create its matching annotated `vX.Y.Z` tag
and GitHub Release. The release workflow publishes the versioned image and:

- `ghcr.io/nerfagol/trading212-mcp:X.Y.Z`
- `ghcr.io/nerfagol/trading212-mcp:latest`

The versioned tag is the reproducible installation reference. `latest` is only
a convenience pointer for the newest stable release. OCI tags are mutable; users
requiring strict artifact immutability can pin the published manifest digest.

The release workflow verifies that the GitHub tag matches `pyproject.toml` and
passes that version to the image's OCI label. After a multi-platform image is
published, retrieve its index digest from GHCR before using a digest reference in
`server.json`, then run the Registry validation step below.

## MCP Registry validation

The intended Registry name is `io.github.nerfagol/trading212-mcp`. It appears in
both `server.json` and the image's required
`io.modelcontextprotocol.server.name` annotation.

Install the official publisher from the
[MCP Registry quickstart](https://modelcontextprotocol.io/registry/quickstart),
then validate from the repository root:

```bash
mcp-publisher validate
```

Registry publication is deliberately not automated. After the owner has
reviewed the published image and metadata, the final command must be run manually:

```bash
mcp-publisher login github
mcp-publisher publish
```

Do not run the publication command as part of ordinary CI or release-image
publishing. The official Registry is currently a preview service, so re-check
its schema and package requirements before every future publication.
