"""EVE SSO OAuth2 authentication and JWT handling.

Provides:
- EVE SSO login URL generation
- Authorization code → token exchange
- JWT validation (offline, using JWKS)
- Session JWT issuance for the frontend
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

# EVE SSO endpoints
SSO_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
SSO_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
SSO_JWKS_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server/jwks"

# Local JWT settings
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


class EveSsoClient:
    """Handles EVE Online SSO OAuth2 Authorization Code flow."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        callback_url: str | None = None,
    ) -> None:
        self.client_id = client_id or settings.eve_client_id
        self.client_secret = client_secret or settings.eve_client_secret
        self.callback_url = callback_url or settings.eve_callback_url

    def get_authorization_url(self, scopes: list[str] | None = None) -> str:
        """Generate the EVE SSO login URL."""
        if scopes is None:
            scopes = ["publicData"]
        scope_str = " ".join(scopes)
        return (
            f"{SSO_AUTH_URL}?"
            f"response_type=code&"
            f"redirect_uri={self.callback_url}&"
            f"client_id={self.client_id}&"
            f"scope={scope_str}&"
            f"state=eve-market-tool"
        )

    async def exchange_code(self, code: str) -> dict | None:
        """Exchange an authorization code for access + refresh tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SSO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.callback_url,
                },
            )
            if resp.status_code != 200:
                logger.error("Token exchange failed: %s", resp.text)
                return None
            return resp.json()

    async def refresh_token(self, refresh_token: str) -> dict | None:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SSO_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if resp.status_code != 200:
                logger.error("Token refresh failed: %s", resp.text)
                return None
            return resp.json()

    async def validate_eve_jwt(self, access_token: str) -> dict | None:
        """Validate an EVE JWT access token offline using JWKS.

        Returns the decoded payload or None if invalid.
        """
        try:
            # Fetch JWKS
            async with httpx.AsyncClient() as client:
                jwks_resp = await client.get(SSO_JWKS_URL)
                jwks = jwks_resp.json()

            # Find RS256 key
            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("alg") == "RS256":
                    rsa_key = key
                    break

            if rsa_key is None:
                logger.error("No RS256 key found in JWKS")
                return None

            payload = jwt.decode(
                access_token,
                rsa_key,
                algorithms=["RS256"],
                issuer=["login.eveonline.com", "https://login.eveonline.com"],
                audience="EVE Online",
            )
            return payload

        except JWTError as e:
            logger.warning("JWT validation failed: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected error validating EVE JWT")
            return None


class JwtHandler:
    """Issues and validates local session JWTs for the frontend."""

    @staticmethod
    def create_session_token(character_id: int, character_name: str) -> str:
        """Create a short-lived session JWT for the frontend."""
        payload = {
            "sub": str(character_id),
            "name": character_name,
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_session_token(token: str) -> dict | None:
        """Decode and validate a session JWT. Returns payload or None."""
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[JWT_ALGORITHM]
            )
            return payload
        except JWTError:
            return None


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()
