"""JWT validation for dynamic authentication."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient

from omcp.auth.errors import (
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
    TokenExpiredError,
)

if TYPE_CHECKING:
    from omcp.config.models import JWTValidationConfig

logger = logging.getLogger(__name__)


class JWTValidator:
    """Validates JWT tokens using JWKS.

    Supports RS256, RS384, RS512, ES256, ES384, ES512 algorithms.
    Fetches and caches signing keys from JWKS endpoint.
    """

    def __init__(self, config: JWTValidationConfig) -> None:
        """Initialize the JWT validator.

        Args:
            config: JWT validation configuration

        Raises:
            ValueError: If JWKS URL is not HTTPS (security requirement)
        """
        self.config = config
        self._jwks_client: PyJWKClient | None = None

        # Validate JWKS URL uses HTTPS to prevent MITM attacks
        if config.jwks_url:
            parsed = urlparse(config.jwks_url)
            if parsed.scheme != "https":
                # Allow localhost for development
                if parsed.hostname not in ("localhost", "127.0.0.1"):
                    raise ValueError(
                        f"JWKS URL must use HTTPS for security. Got: {config.jwks_url}"
                    )

    @property
    def jwks_client(self) -> PyJWKClient:
        """Get or create the JWKS client."""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                self.config.jwks_url,
                cache_keys=True,
                lifespan=self.config.jwks_cache_ttl_seconds,
            )
        return self._jwks_client

    async def validate(self, token: str) -> dict[str, Any]:
        """Validate a JWT token and return its claims.

        Args:
            token: The JWT token string

        Returns:
            Decoded token claims

        Raises:
            TokenExpiredError: If token has expired
            InvalidAudienceError: If audience doesn't match
            InvalidIssuerError: If issuer doesn't match
            InvalidTokenError: If token is invalid
        """
        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Build decode options
            options = {
                "require": self.config.required_claims or ["exp", "sub"],
                "verify_exp": True,
                "verify_aud": self.config.audience is not None,
                "verify_iss": self.config.issuer is not None,
            }

            # Decode and verify
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.config.algorithms or ["RS256"],
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.clock_skew_seconds or 30,
                options=options,
            )

            return claims

        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidAudienceError:
            raise InvalidAudienceError(self.config.audience or "unknown")
        except jwt.InvalidIssuerError:
            raise InvalidIssuerError(self.config.issuer or "unknown")
        except jwt.DecodeError as e:
            logger.debug("JWT decode error: %s", e)
            raise InvalidTokenError(f"Decode error: {e}")
        except jwt.InvalidTokenError as e:
            logger.debug("JWT validation error: %s", e)
            raise InvalidTokenError(str(e))
        except Exception as e:
            # Log unexpected errors at warning level for debugging
            logger.warning("Unexpected JWT validation error: %s", e, exc_info=True)
            raise InvalidTokenError(f"Validation failed: {e}")

    def clear_cache(self) -> None:
        """Clear the JWKS cache."""
        if self._jwks_client:
            self._jwks_client = None


def create_jwt_validator(config: JWTValidationConfig) -> JWTValidator:
    """Create a JWT validator from configuration.

    Args:
        config: JWT validation configuration

    Returns:
        Configured JWTValidator instance
    """
    return JWTValidator(config)
