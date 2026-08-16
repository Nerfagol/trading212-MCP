# Release and MCP Registry Readiness

Release operations are intentionally separate from normal pull-request CI.
Only a published GitHub Release can run the GHCR publishing workflow.

`pyproject.toml` is the source of truth for the Python package version. Runtime
MCP metadata and the HTTP User-Agent read the installed distribution version.
`server.json` remains explicit release metadata, and the test suite requires its
version to match `pyproject.toml`.

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

For version `0.1.0`, create and push the annotated `v0.1.0` tag only after CI on
`main` is green. Publish the matching GitHub Release. The release workflow then
publishes:

- `ghcr.io/nerfagol/trading212-mcp:0.1.0`
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
