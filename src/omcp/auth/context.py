"""Authentication context for request-scoped auth data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TokenClaims:
    """Parsed JWT claims."""

    sub: str | None = None  # Subject (user ID)
    exp: datetime | None = None  # Expiration time
    iat: datetime | None = None  # Issued at
    iss: str | None = None  # Issuer
    aud: str | list[str] | None = None  # Audience
    scopes: list[str] = field(default_factory=list)  # OAuth scopes
    raw: dict[str, Any] = field(default_factory=dict)  # All claims

    @classmethod
    def from_jwt(cls, claims: dict[str, Any]) -> TokenClaims:
        """Create TokenClaims from decoded JWT payload."""
        exp = None
        if "exp" in claims:
            exp = datetime.fromtimestamp(claims["exp"])

        iat = None
        if "iat" in claims:
            iat = datetime.fromtimestamp(claims["iat"])

        scopes = []
        if "scope" in claims:
            scopes = claims["scope"].split() if isinstance(claims["scope"], str) else claims["scope"]
        elif "scopes" in claims:
            scopes = claims["scopes"] if isinstance(claims["scopes"], list) else [claims["scopes"]]

        return cls(
            sub=claims.get("sub"),
            exp=exp,
            iat=iat,
            iss=claims.get("iss"),
            aud=claims.get("aud"),
            scopes=scopes,
            raw=claims,
        )


@dataclass
class AuthContext:
    """Request-scoped authentication context.

    Contains the validated token and parsed claims for the current request.
    This is passed through the tool execution pipeline.
    """

    token: str  # Raw token string (for forwarding to upstream)
    claims: TokenClaims | None = None  # Parsed claims (if validated)
    validated: bool = False  # Whether token was validated by OMCP
    # Header configuration for forwarding (preserves how token was received)
    header_name: str = "Authorization"  # Header name for forwarding
    header_scheme: str | None = "Bearer"  # Scheme (None for raw token)

    def get_header_value(self) -> str:
        """Get the full header value for forwarding.

        Returns the token formatted with scheme if configured,
        or raw token if scheme is None.
        """
        if self.header_scheme:
            return f"{self.header_scheme} {self.token}"
        return self.token

    def get_auth_headers(self) -> dict[str, str]:
        """Get auth headers dict for forwarding to upstream.

        Returns:
            Dict with header name and formatted value
        """
        return {self.header_name: self.get_header_value()}

    @property
    def user_id(self) -> str | None:
        """Get user ID from token claims."""
        if self.claims:
            return self.claims.sub
        return None

    @property
    def scopes(self) -> list[str]:
        """Get scopes from token claims."""
        if self.claims:
            return self.claims.scopes
        return []

    def has_scope(self, scope: str) -> bool:
        """Check if token has a specific scope."""
        return scope in self.scopes

    def get_claim(self, name: str, default: Any = None) -> Any:
        """Get a specific claim from the token."""
        if self.claims and self.claims.raw:
            return self.claims.raw.get(name, default)
        return default
