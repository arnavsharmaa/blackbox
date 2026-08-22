# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub's private vulnerability reporting](https://github.com/arnavsharmaa/blackbox/security/advisories/new)
rather than opening a public issue. You should get an initial response
within a week.

## Scope and threat model

By default BlackBox assumes a **trusted network**: with
`BLACKBOX_API_TOKENS` unset there is no authentication and the API will
ingest any well-formed upload. Setting `BLACKBOX_API_TOKENS` requires a
bearer token (or `X-API-Key`) on every `/api` route — but tokens are
shared, not per-user, and there is no tenant isolation. Treat an
internet-exposed instance as experimental; a VPN or reverse proxy in
front remains the recommended deployment.

Reports most useful right now:

- Parsing vulnerabilities in the ingestion adapters (JSON, CSV, and
  especially the MCAP/rosbag2 decoder path) — these process untrusted
  file contents by design.
- Path traversal, SQL injection, or SSRF anywhere in the API.
- Cross-site scripting in the web UI (incident fields render
  operator-supplied text).

- Bypasses of the token check itself (timing, header parsing, routes
  that should be gated but aren't).

Denial-of-service reports that require uploading very large files to an
instance with auth disabled are out of scope — that deployment mode is
documented as trusted-network only.

## Supported versions

Only the latest commit on `main` is supported.
