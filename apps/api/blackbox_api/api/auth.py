"""Optional bearer-token authentication with per-token scopes.

Three token lists, all optional; if none is configured the API stays
open — the documented trusted-network default:

- ``BLACKBOX_API_TOKENS`` — full access to every facility.
- ``BLACKBOX_READONLY_TOKENS`` — GET/HEAD/OPTIONS only, every facility.
- ``BLACKBOX_FACILITY_TOKENS`` — a JSON object mapping token to
  facility name; the token reads and writes only that facility's
  incidents (per-fleet isolation on one shared instance).

Tokens are sent as 'Authorization: Bearer <token>' or an 'X-API-Key'
header. /health stays open for probes.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, Request

from blackbox_api.config import get_settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class TokenScope:
    """What the presented token may see and do."""

    #: Restrict every read and write to this facility; None = all.
    facility: str | None = None
    readonly: bool = False


#: The scope used when authentication is disabled entirely.
OPEN_SCOPE = TokenScope()


def _matches(provided: str, tokens: list[str]) -> bool:
    # Constant-time comparison against every configured token.
    return any(secrets.compare_digest(provided, token) for token in tokens)


def resolve_token(provided: str) -> TokenScope | None:
    """Map a presented token to its scope, or None if unknown."""
    settings = get_settings()
    if _matches(provided, settings.api_token_list):
        return TokenScope()
    if _matches(provided, settings.readonly_api_token_list):
        return TokenScope(readonly=True)
    facility: str | None = None
    for token, token_facility in settings.facility_token_map.items():
        # Check every entry to keep the comparison constant-time.
        if secrets.compare_digest(provided, token):
            facility = token_facility
    if facility is not None:
        return TokenScope(facility=facility)
    return None


def get_token_scope(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> TokenScope:
    settings = get_settings()
    if (
        not settings.api_token_list
        and not settings.readonly_api_token_list
        and not settings.facility_token_map
    ):
        return OPEN_SCOPE

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
    scope = resolve_token(provided)
    if scope is None:
        raise HTTPException(
            status_code=401,
            detail="invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if scope.readonly and request.method not in _SAFE_METHODS:
        raise HTTPException(
            status_code=403,
            detail="this API token is read-only",
        )
    return scope
