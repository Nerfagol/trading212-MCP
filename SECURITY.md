# Security Policy

This server handles credentials and sensitive financial account data even though
its Trading 212 integration is strictly read-only. Review the complete
[security design](docs/security.md) for the enforced GET allowlist, credential
handling, network boundaries, and automated write-surface tests.

## Report a vulnerability

Use GitHub's private vulnerability reporting for this repository:

1. Open the repository's **Security** tab.
2. Select **Advisories** and **Report a vulnerability**.
3. Describe the impact and a minimal reproduction without including real
   Trading 212 credentials, tunnel credentials, account data, or portfolio data.

Do not open a public issue for a suspected credential leak, authentication
problem, write-surface bypass, or exposure of private financial data.

## Supported versions

Security fixes are applied to the latest published release and the `main`
branch. Self-hosted operators should update to the newest stable image tag after
reviewing its release notes.
