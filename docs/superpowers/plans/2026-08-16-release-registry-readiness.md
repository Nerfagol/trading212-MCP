# Release and Registry Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare `Nerfagol/trading212-MCP` for a reviewed `v0.1.0` release, versioned GHCR distribution, and later MCP Registry publication without changing its read-only behavior.

**Architecture:** Keep normal CI and release publishing separate. Pull requests and `main` pushes run installation, Ruff, MyPy, pytest, Python package build, and Docker build; a published GitHub Release alone can push versioned OCI images. Registry metadata identifies the release image as `io.github.nerfagol/trading212-mcp`, while the final Registry publication remains a manual owner action.

**Tech Stack:** Python 3.12, pytest, Ruff, MyPy, Hatchling, Docker/BuildKit, GitHub Actions, GHCR, MCP Registry `server.json`, Mermaid, SVG.

## Global Constraints

- Preserve the six-path Trading 212 GET allowlist and the exact eight read-only MCP tools.
- Never add POST, PUT, PATCH, DELETE, order placement, order cancellation, order modification, or a generic HTTP request interface.
- Never read, print, commit, upload, or log `.env`, Trading 212 credentials, tunnel credentials, account values, or portfolio values.
- Keep QNAP MCP binding LAN-only and the OpenAI Secure MCP Tunnel admin listener loopback-only.
- Build and review on `chore/release-registry-readiness`; merge only after pull-request CI succeeds.
- Publish GHCR only from a published GitHub Release, using `GITHUB_TOKEN` with `contents: read` and `packages: write`.
- Prepare and validate the MCP Registry metadata, but never run `mcp-publisher publish` in this implementation.
- Use `io.github.nerfagol/trading212-mcp` consistently for the Registry identity and required OCI annotation.

---

### Task 1: Release-readiness tests and baseline typing

**Files:**
- Create: `tests/test_release_readiness.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: the existing repository files and test suite.
- Produces: automated assertions for documentation, workflows, OCI metadata, Registry metadata, and a clean full-project MyPy check.

- [ ] **Step 1: Add tests for the intended files and invariant values**

  Assert the README first-screen claims, eight tools, versioned GHCR reference, workflow triggers and permissions, required OCI labels, `server.json` identity/schema/package, policy files, and social-preview content.

- [ ] **Step 2: Run the new tests and verify they fail because the release files do not exist yet**

  Run: `.venv/bin/pytest tests/test_release_readiness.py -q`

- [ ] **Step 3: Correct only the existing test-double type annotations**

  Declare forwarded argument dictionaries as `dict[str, object]` and use an explicit `cast` at the typed production-client factory boundary.

- [ ] **Step 4: Verify full-project MyPy and the existing server tests**

  Run: `.venv/bin/mypy src tests && .venv/bin/pytest tests/test_server.py -q`

### Task 2: Discoverability, policies, and release documentation

**Files:**
- Modify: `README.md`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `.github/pull_request_template.md`
- Create: `docs/releasing.md`
- Create: `docs/directory-submissions.md`
- Create: `docs/assets/social-preview.svg`
- Create if tooling permits: `docs/assets/social-preview.png`

**Interfaces:**
- Consumes: the existing deployment and security documentation.
- Produces: a concise first screen, secure GHCR instructions, owner release runbook, submission-ready summary, and social-preview asset.

- [ ] **Step 1: Improve only the README upper section and installation paths**

  Add at most three badges, the compact value proposition, a Mermaid architecture diagram with optional local/LAN and outbound-tunnel routes, explicit credential isolation, and a secure versioned-image command bound to `127.0.0.1`.

- [ ] **Step 2: Add concise contributor and vulnerability-reporting policies**

  Link `SECURITY.md` to `docs/security.md`, direct sensitive reports to GitHub private vulnerability reporting, and make the read-only boundary a pull-request checklist item.

- [ ] **Step 3: Document releases, Registry validation, and external submission material**

  Record the GHCR tags, validation command, prohibited automatic Registry publication, MCP Directory submission form, and the actively maintained awesome-list submission route without opening third-party PRs.

- [ ] **Step 4: Create and inspect the 1280x640 social-preview asset**

  Use independent-project wording and generic MCP/network imagery, without Trading 212 logos or any implication of affiliation.

### Task 3: Pull-request CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `pyproject.toml`, the Python package, tests, and Dockerfile.
- Produces: a least-privilege PR and `main` validation workflow with separate Python and Docker jobs.

- [ ] **Step 1: Add the CI workflow using current stable official actions pinned to commit SHAs**

  Trigger on pull requests and pushes to `main`; grant only `contents: read`; install `.[dev]`; run Ruff, MyPy, pytest, `python -m build`, and a non-publishing Docker build.

- [ ] **Step 2: Run the release-readiness workflow assertions**

  Run: `.venv/bin/pytest tests/test_release_readiness.py -q`

### Task 4: Release-only GHCR publishing and OCI metadata

**Files:**
- Modify: `Dockerfile`
- Create: `.github/workflows/release-image.yml`

**Interfaces:**
- Consumes: a published GitHub Release tagged `v0.1.0`.
- Produces: `ghcr.io/nerfagol/trading212-mcp:0.1.0` and `:latest` for stable releases, with multi-architecture OCI metadata.

- [ ] **Step 1: Add static Dockerfile ownership and OCI labels**

  Include title, description, source, version, revision, license, and `io.modelcontextprotocol.server.name=io.github.nerfagol/trading212-mcp`; preserve the non-root runtime user and healthcheck.

- [ ] **Step 2: Add a release-published workflow using official Docker actions pinned to SHAs**

  Grant `contents: read` and `packages: write`, authenticate with `GITHUB_TOKEN`, derive the semantic version from the release tag, and publish `0.1.0` plus `latest`; never run for pull requests or ordinary pushes.

- [ ] **Step 3: Verify Docker and workflow tests locally**

  Run: `.venv/bin/pytest tests/test_release_readiness.py tests/test_deployment_kit.py -q && docker build -t trading212-mcp:release-test .`

### Task 5: Official MCP Registry metadata

**Files:**
- Create: `server.json`

**Interfaces:**
- Consumes: MCP Registry schema `2025-12-11` and the versioned GHCR image.
- Produces: a schema-valid OCI package entry using Streamable HTTP at `/mcp` with secret environment-variable declarations.

- [ ] **Step 1: Add exact stable-schema metadata**

  Use `io.github.nerfagol/trading212-mcp`, version `0.1.0`, the versioned GHCR identifier, `streamable-http`, loopback transport URL, and secret declarations for `T212_API_KEY` and `T212_API_SECRET`.

- [ ] **Step 2: Run local metadata tests**

  Run: `.venv/bin/pytest tests/test_release_readiness.py -q`

- [ ] **Step 3: Install the official publisher under `/tmp` and validate without authentication or publication**

  Run: `/tmp/mcp-publisher validate`

### Task 6: Local review, commits, and pull request

**Files:**
- Review: all files changed from `main...HEAD`

**Interfaces:**
- Consumes: the completed feature branch.
- Produces: logical commits and a reviewable GitHub pull request.

- [ ] **Step 1: Run all local release gates**

  Run: `.venv/bin/ruff check . && .venv/bin/mypy src tests && .venv/bin/pytest && .venv/bin/python -m build && docker build .`

- [ ] **Step 2: Audit secrets and the read-only boundary**

  Inspect tracked files only, run the security tests, review all HTTP method calls, tool names, allowlisted paths, Docker privileges, QNAP binding, tunnel listeners, and workflow permissions.

- [ ] **Step 3: Create logical commits and push the feature branch**

  Separate documentation/policies, CI, GHCR/OCI, and Registry metadata where the final diff permits.

- [ ] **Step 4: Open a pull request and wait for every required check**

  Do not merge while a check is pending or failing.

- [ ] **Step 5: Review the final PR diff as an independent security/release reviewer**

  Record material findings in the PR or fix them in additional reviewed commits, then rerun CI.

### Task 7: Merge, release, GHCR verification, and Registry readiness

**Files:**
- No source changes unless a failed gate requires a new pull-request fix.

**Interfaces:**
- Consumes: an approved, green pull request.
- Produces: merged `main`, `v0.1.0`, a GitHub Release, versioned public GHCR images, and validated Registry readiness.

- [ ] **Step 1: Merge the pull request and verify CI on the merge commit**

  Do not tag until `main` CI completes successfully.

- [ ] **Step 2: Create and push annotated tag `v0.1.0` and publish matching release notes**

  Mention the eight read-only tools, Docker, QNAP, Secure MCP Tunnel, and write-surface validation.

- [ ] **Step 3: Wait for the release workflow and inspect both GHCR tags**

  Verify `0.1.0` and `latest`, platforms, non-root user, healthcheck, OCI fields, and exact MCP ownership annotation without using credentials.

- [ ] **Step 4: Re-run official Registry validation against the published image**

  Confirm namespace compatibility and metadata validity. Do not authenticate to or publish to the MCP Registry.

- [ ] **Step 5: Report the remaining manual social-preview upload and Registry command**

  The unexecuted publication command is `mcp-publisher publish`.
