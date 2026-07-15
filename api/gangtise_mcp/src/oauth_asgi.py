"""OAuth 2.1 ASGI routes for Gangtise MCP (authorize / token / discovery / DCR)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from oauth_tokens import (
    AUTH_CODE_TTL,
    SCOPE,
    TokenConfigError,
    TokenError,
    decode_token,
    encrypt_credentials,
    mint_token_pair,
    oauth_configured,
)

OPEN_PLATFORM_URL = "https://open-platform.gangtise.com/"

ALLOWED_REDIRECT_HOSTS = {
    "claude.ai",
    "claude.com",
    "chatgpt.com",
    "chat.openai.com",
    "cursor.com",
    "www.cursor.com",
}
ALLOWED_REDIRECT_DOMAINS = {
    "cursor.sh",
    "anthropic.com",
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

_HTML_PATH = Path(__file__).resolve().parent / "authorization.html"


def is_valid_redirect_uri(redirect_uri: str) -> bool:
    if not redirect_uri:
        return False
    try:
        parsed = urllib.parse.urlparse(redirect_uri)
    except ValueError:
        return False
    host = parsed.hostname or ""
    if host in LOOPBACK_HOSTS:
        return parsed.scheme in ("http", "https")
    if parsed.scheme != "https":
        return False
    if host in ALLOWED_REDIRECT_HOSTS:
        return True
    return any(host == d or host.endswith(f".{d}") for d in ALLOWED_REDIRECT_DOMAINS)


def verify_pkce_challenge(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return expected == code_challenge


def resolve_base_url(request: Request) -> str:
    domain = os.environ.get("GTS_OAUTH_ISSUER") or os.environ.get("DOMAIN_NAME")
    if domain:
        domain = domain.strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain.rstrip("/")
        return f"https://{domain}".rstrip("/")
    # Prefer proxy headers when behind reverse proxy
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        host = request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _json(data: dict, status: int = 200, extra_headers: Optional[dict] = None) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(data, status_code=status, headers=headers)


def _oauth_misconfig() -> JSONResponse:
    return _json(
        {
            "error": "server_error",
            "error_description": "OAuth is not configured (GTS_JWT_SECRET / GTS_CRED_ENC_KEY)",
        },
        500,
    )


async def metadata_authorization_server(request: Request) -> Response:
    base = resolve_base_url(request)
    return JSONResponse(
        {
            "issuer": base,
            "authorization_endpoint": f"{base}/authorize",
            "token_endpoint": f"{base}/token",
            "registration_endpoint": f"{base}/register",
            "scopes_supported": [SCOPE, "offline_access"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def metadata_protected_resource(request: Request) -> Response:
    base = resolve_base_url(request)
    return JSONResponse(
        {
            "resource": f"{base}/mcp",
            "authorization_servers": [base],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def authorize(request: Request) -> Response:
    if not oauth_configured():
        return _oauth_misconfig()

    params = dict(request.query_params)
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    response_type = params.get("response_type")
    state = params.get("state")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method", "S256")

    if not client_id or not redirect_uri:
        return _json(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            400,
        )
    if not is_valid_redirect_uri(redirect_uri):
        return _json(
            {"error": "invalid_request", "error_description": "Invalid redirect URI"},
            400,
        )
    if response_type != "code":
        return _error_redirect(redirect_uri, "unsupported_response_type", state)
    if not code_challenge or code_challenge_method != "S256":
        return _error_redirect(
            redirect_uri,
            "invalid_request",
            state,
            "PKCE S256 code_challenge is required",
        )

    if request.method == "POST":
        return await _authorize_submit(request, params)

    html = _HTML_PATH.read_text(encoding="utf-8")
    q = urllib.parse.urlencode(
        {
            k: params.get(k, "")
            for k in (
                "response_type",
                "client_id",
                "redirect_uri",
                "code_challenge",
                "code_challenge_method",
                "state",
            )
            if params.get(k)
        }
    )
    html = html.replace('action="/authorize"', f'action="/authorize?{q}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _error_redirect(
    redirect_uri: str,
    error: str,
    state: Optional[str],
    description: Optional[str] = None,
) -> RedirectResponse:
    q: Dict[str, str] = {"error": error}
    if description:
        q["error_description"] = description
    if state:
        q["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urllib.parse.urlencode(q)}", status_code=302)


async def _authorize_submit(request: Request, params: dict) -> Response:
    redirect_uri = params["redirect_uri"]
    state = params.get("state")
    form = await request.form()
    access_key = str(form.get("access_key") or form.get("accessKey") or "").strip()
    secret_key = str(form.get("secret_key") or form.get("secretKey") or "").strip()
    if not access_key or not secret_key:
        return _error_redirect(
            redirect_uri, "access_denied", state, "Access Key and Secret Key are required"
        )

    try:
        enc = encrypt_credentials(access_key, secret_key)
        code = encode_auth_code(
            enc_creds=enc,
            client_id=params["client_id"],
            redirect_uri=redirect_uri,
            code_challenge=params["code_challenge"],
        )
    except TokenConfigError:
        return _oauth_misconfig()
    except Exception:
        return _error_redirect(redirect_uri, "server_error", state, "Failed to mint code")

    q: Dict[str, str] = {"code": code}
    if state:
        q["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urllib.parse.urlencode(q)}", status_code=302)


def encode_auth_code(
    *,
    enc_creds: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
) -> str:
    from oauth_tokens import encode_token

    return encode_token(
        {
            "typ": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "enc_creds": enc_creds,
        },
        AUTH_CODE_TTL,
    )


async def token(request: Request) -> Response:
    if not oauth_configured():
        return _oauth_misconfig()
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            params = await request.json()
        except Exception:
            return _json({"error": "invalid_request", "error_description": "Malformed JSON"}, 400)
    else:
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}

    grant_type = params.get("grant_type")
    try:
        if grant_type == "authorization_code":
            return _handle_code_grant(params)
        if grant_type == "refresh_token":
            return _handle_refresh_grant(params)
    except TokenConfigError:
        return _oauth_misconfig()
    return _json({"error": "unsupported_grant_type"}, 400)


def _handle_code_grant(params: dict) -> JSONResponse:
    code = params.get("code")
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    code_verifier = params.get("code_verifier")
    if not all([code, client_id, redirect_uri]):
        return _json(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            400,
        )
    try:
        data = decode_token(str(code))
    except TokenError as exc:
        err = "Authorization code expired" if "expired" in str(exc).lower() else "Invalid authorization code"
        return _json({"error": "invalid_grant", "error_description": err}, 400)

    if data.get("typ") != "code":
        return _json({"error": "invalid_grant", "error_description": "Invalid authorization code"}, 400)
    if data.get("client_id") != client_id or data.get("redirect_uri") != redirect_uri:
        return _json({"error": "invalid_grant", "error_description": "Code validation failed"}, 400)
    challenge = data.get("code_challenge")
    if not challenge or not code_verifier or not verify_pkce_challenge(str(code_verifier), str(challenge)):
        return _json({"error": "invalid_grant", "error_description": "PKCE verification failed"}, 400)
    enc = data.get("enc_creds")
    if not enc:
        return _json({"error": "invalid_grant", "error_description": "No credentials in code"}, 400)
    return _json(mint_token_pair(str(enc), client_id))


def _handle_refresh_grant(params: dict) -> JSONResponse:
    refresh_token = params.get("refresh_token")
    if not refresh_token:
        return _json({"error": "invalid_request", "error_description": "Missing refresh_token"}, 400)
    try:
        data = decode_token(str(refresh_token))
    except TokenError as exc:
        err = "Refresh token expired" if "expired" in str(exc).lower() else "Invalid refresh token"
        return _json({"error": "invalid_grant", "error_description": err}, 400)
    if data.get("typ") != "refresh" or not data.get("enc_creds"):
        return _json({"error": "invalid_grant", "error_description": "Invalid refresh token"}, 400)
    return _json(mint_token_pair(str(data["enc_creds"]), data.get("client_id")))


async def register(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid_request", "error_description": "Malformed JSON"}, 400)
    redirect_uris = body.get("redirect_uris") or []
    if not isinstance(redirect_uris, list):
        return _json({"error": "invalid_request", "error_description": "redirect_uris must be array"}, 400)
    for uri in redirect_uris:
        if not is_valid_redirect_uri(str(uri)):
            return _json(
                {"error": "invalid_redirect_uri", "error_description": f"Invalid redirect URI: {uri}"},
                400,
            )
    client_id = f"mcp-client-{secrets.token_urlsafe(16)}"
    return _json(
        {
            "client_id": client_id,
            "client_id_issued_at": int(time.time()),
            "redirect_uris": redirect_uris or ["http://localhost:8080/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        201,
    )


def oauth_routes() -> List[Route]:
    """Starlette routes to mount before MCP endpoints."""
    return [
        Route(
            "/.well-known/oauth-authorization-server",
            endpoint=metadata_authorization_server,
            methods=["GET"],
        ),
        Route(
            "/.well-known/oauth-protected-resource",
            endpoint=metadata_protected_resource,
            methods=["GET"],
        ),
        Route(
            "/.well-known/oauth-protected-resource/mcp",
            endpoint=metadata_protected_resource,
            methods=["GET"],
        ),
        Route("/authorize", endpoint=authorize, methods=["GET", "POST"]),
        Route("/token", endpoint=token, methods=["POST"]),
        Route("/register", endpoint=register, methods=["POST"]),
    ]

