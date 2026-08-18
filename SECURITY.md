# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub's private vulnerability reporting](https://github.com/arnavsharmaa/blackbox/security/advisories/new)
rather than opening a public issue. You should get an initial response
within a week.

## Scope and threat model

BlackBox currently assumes a **trusted network**: there is no
authentication, and the API will ingest any well-formed upload. Do not
expose an instance to the public internet — deploy it behind a VPN or
reverse-proxy auth until first-party auth lands (see the roadmap).

Reports most useful right now:

- Parsing vulnerabilities in the ingestion adapters (JSON, CSV, and
  especially the MCAP/rosbag2 decoder path) — these process untrusted
  file contents by design.
- Path traversal, SQL injection, or SSRF anywhere in the API.
- Cross-site scripting in the web UI (incident fields render
  operator-supplied text).

Denial-of-service reports that require uploading very large files to an
unauthenticated instance are out of scope until auth exists — that
limitation is documented and by design for the MVP.

## Supported versions

Only the latest commit on `main` is supported.
