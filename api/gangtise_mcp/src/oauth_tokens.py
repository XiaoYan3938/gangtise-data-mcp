"""Stateless OAuth tokens carrying encrypted Gangtise AK/SK (1A).

JWT HS256 envelope + Fernet-encrypted credentials claim.
Env: GTS_JWT_SECRET, GTS_CRED_ENC_KEY (Fernet url-safe key).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import jwt
from cryptography.fernet import Fernet, InvalidToken

JWT_ALGORITHM = "HS256"
SCOPE = "gangtise:read"

ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)
AUTH_CODE_TTL = timedelta(seconds=60)


class TokenError(Exception):
    """Malformed, expired, tampered, or undecryptable token."""


class TokenConfigError(TokenError):
    """OAuth signing/encryption keys not configured."""


def _jwt_secret() -> str:
    secret = os.environ.get("GTS_JWT_SECRET", "").strip()
    if not secret:
        raise TokenConfigError("GTS_JWT_SECRET is not configured")
    return secret


def _fernet() -> Fernet:
    key = os.environ.get("GTS_CRED_ENC_KEY", "").strip()
    if not key:
        raise TokenConfigError("GTS_CRED_ENC_KEY is not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def oauth_configured() -> bool:
    return bool(
        os.environ.get("GTS_JWT_SECRET", "").strip()
        and os.environ.get("GTS_CRED_ENC_KEY", "").strip()
    )


def encrypt_credentials(access_key: str, secret_key: str) -> str:
    payload = json.dumps(
        {"accessKey": access_key, "secretKey": secret_key},
        separators=(",", ":"),
    )
    return _fernet().encrypt(payload.encode()).decode()


def decrypt_credentials(enc: str) -> Tuple[str, str]:
    try:
        raw = _fernet().decrypt(enc.encode()).decode()
        data = json.loads(raw)
    except (InvalidToken, json.JSONDecodeError, TypeError) as exc:
        raise TokenError("credentials decryption failed") from exc
    ak = str(data.get("accessKey") or "").strip()
    sk = str(data.get("secretKey") or "").strip()
    if not ak or not sk:
        raise TokenError("credentials missing in token")
    return ak, sk


def encode_token(claims: dict[str, Any], ttl: timedelta) -> str:
    payload = dict(claims)
    payload["exp"] = datetime.now(timezone.utc) + ttl
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


def decode_access_token(bearer: str) -> Optional[Tuple[str, str]]:
    """Validate access token and return (ak, sk). None if invalid type/expired."""
    try:
        data = decode_token(bearer)
    except TokenError:
        return None
    if data.get("typ") != "access":
        return None
    enc = data.get("enc_creds")
    if not enc:
        return None
    try:
        return decrypt_credentials(str(enc))
    except TokenError:
        return None


def mint_token_pair(enc_creds: str, client_id: Optional[str]) -> dict[str, Any]:
    access_token = encode_token(
        {
            "typ": "access",
            "client_id": client_id,
            "scope": SCOPE,
            "enc_creds": enc_creds,
        },
        ACCESS_TOKEN_TTL,
    )
    refresh_token = encode_token(
        {
            "typ": "refresh",
            "client_id": client_id,
            "scope": SCOPE,
            "enc_creds": enc_creds,
        },
        REFRESH_TOKEN_TTL,
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "refresh_token": refresh_token,
        "scope": SCOPE,
    }
