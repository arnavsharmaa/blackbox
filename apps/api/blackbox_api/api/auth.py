"""Optional bearer-token authentication for the API.

With BLACKBOX_API_TOKENS and BLACKBOX_READONLY_TOKENS both unset, the
API stays open — the documented trusted-network default. When either is
set, every /api route requires a token, sent as 'Authorization: Bearer
<token>' or an 'X-API-Key' header. Read-only tokens are limited to safe
methods (GET/HEAD/OPTIONS) and get a 403 on mutating routes — meant for
wallboards and dashboards. /health stays open for probes.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request

from blackbox_api.config import get_settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _matches(provided: str, tokens: list[str]) -> bool:
    # Constant-time comparison against every configured token.
    return any(secrets.compare_digest(provided, token) for token in tokens)


def require_api_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    settings = get_settings()
    full_tokens = settings.api_token_list
    readonly_tokens = settings.readonly_api_token_list
    if not full_tokens and not readonly_tokens:
        return

    provided = x_api_key
    if provided is None and authorization is not None:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            provided = value.strip()

    if not provided:
        raise HTTPException(
            status_code=401,
            detail="missing API token; send 'Authorization: Bearer <token>' "
            "or an 'X-API-Key' header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if _matches(provided, full_tokens):
        return
    if _matches(provided, readonly_tokens):
        if request.method in _SAFE_METHODS:
            return
        raise HTTPException(
            status_code=403,
            detail="this API token is read-only",
        )
    raise HTTPException(
        status_code=401,
        detail="invalid API token",
        headers={"WWW-Authenticate": "Bearer"},
    )
