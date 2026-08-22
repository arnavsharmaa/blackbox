"""Optional bearer-token authentication for the API.

With BLACKBOX_API_TOKENS unset, the API stays open — the documented
trusted-network default. When set (comma-separated), every /api route
requires one of the tokens, sent as either 'Authorization: Bearer
<token>' or an 'X-API-Key' header. /health stays open for probes and
load balancers.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from blackbox_api.config import get_settings


def require_api_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    tokens = get_settings().api_token_list
    if not tokens:
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
    # Constant-time comparison against every configured token.
    if not any(secrets.compare_digest(provided, token) for token in tokens):
        raise HTTPException(
            status_code=401,
            detail="invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
