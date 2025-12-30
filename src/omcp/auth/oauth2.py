"""OAuth2 authentication provider with PKCE support."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import httpx

from omcp.auth.base import AuthProvider
from omcp.auth.storage import StoredToken, TokenStorage
from omcp.utils.errors import AuthError


class OAuth2Auth(AuthProvider):
    """OAuth2 authentication provider with PKCE support.

    Implements the Authorization Code flow with PKCE for secure
    authentication without client secrets.
    """

    def __init__(
        self,
        client_id: str,
        auth_url: str,
        token_url: str,
        scopes: list[str] | None = None,
        client_secret: str | None = None,
        redirect_port: int = 8765,
        provider_name: str = "default",
        storage: TokenStorage | None = None,
        auto_refresh: bool = True,
    ) -> None:
        """Initialize OAuth2 auth.

        Args:
            client_id: OAuth2 client ID
            auth_url: Authorization endpoint URL
            token_url: Token endpoint URL
            scopes: List of scopes to request
            client_secret: Optional client secret (not needed with PKCE)
            redirect_port: Local port for OAuth callback
            provider_name: Name for token storage
            storage: Token storage instance (default: new TokenStorage)
            auto_refresh: Automatically refresh expired tokens
        """
        self._client_id = client_id
        self._auth_url = auth_url
        self._token_url = token_url
        self._scopes = scopes or []
        self._client_secret = client_secret
        self._redirect_port = redirect_port
        self._provider_name = provider_name
        self._storage = storage or TokenStorage()
        self._auto_refresh = auto_refresh

        # Current token (loaded from storage or obtained via auth flow)
        self._token: StoredToken | None = None

        # PKCE values (generated per auth flow)
        self._code_verifier: str | None = None
        self._code_challenge: str | None = None

    @property
    def redirect_uri(self) -> str:
        """Get the redirect URI for OAuth callbacks."""
        return f"http://localhost:{self._redirect_port}/callback"

    def _load_token(self) -> StoredToken | None:
        """Load token from storage."""
        if self._token is None:
            self._token = self._storage.load(self._provider_name)
        return self._token

    def _save_token(self, token: StoredToken) -> None:
        """Save token to storage."""
        self._token = token
        self._storage.store(self._provider_name, token)

    async def get_headers(self) -> dict[str, str]:
        """Get Authorization header with access token."""
        token = self._load_token()

        if token is None:
            raise AuthError(
                "No OAuth2 token available",
                details="Run 'omcp auth' to authenticate",
            )

        # Auto-refresh if expired
        if self._auto_refresh and token.is_expired():
            if token.can_refresh():
                await self.refresh()
                token = self._token
            else:
                raise AuthError(
                    "OAuth2 token expired and cannot be refreshed",
                    details="Run 'omcp auth' to re-authenticate",
                )

        if token is None:
            raise AuthError("Failed to get valid token")

        return {"Authorization": f"{token.token_type} {token.access_token}"}

    async def refresh(self) -> None:
        """Refresh the access token using the refresh token."""
        token = self._load_token()

        if token is None or not token.can_refresh():
            raise AuthError(
                "Cannot refresh token",
                details="No refresh token available",
            )

        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": self._client_id,
        }

        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPError as e:
                raise AuthError("Failed to refresh token", details=str(e))

        new_token = self._parse_token_response(token_data)
        # Preserve refresh token if not returned
        if new_token.refresh_token is None:
            new_token.refresh_token = token.refresh_token
        self._save_token(new_token)

    def is_valid(self) -> bool:
        """Check if we have a valid (non-expired) token."""
        token = self._load_token()
        if token is None:
            return False
        if token.is_expired():
            return token.can_refresh()
        return True

    def _generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate 32-byte random verifier
        code_verifier = secrets.token_urlsafe(32)

        # SHA256 hash, base64url encode (without padding)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

        return code_verifier, code_challenge

    def get_authorization_url(self) -> str:
        """Generate the authorization URL for the OAuth flow.

        Returns:
            URL to open in browser for user authorization
        """
        self._code_verifier, self._code_challenge = self._generate_pkce()

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self.redirect_uri,
            "code_challenge": self._code_challenge,
            "code_challenge_method": "S256",
        }

        if self._scopes:
            params["scope"] = " ".join(self._scopes)

        # Add state for CSRF protection
        params["state"] = secrets.token_urlsafe(16)

        return f"{self._auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> StoredToken:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            StoredToken with access/refresh tokens
        """
        if self._code_verifier is None:
            raise AuthError("PKCE verifier not set - call get_authorization_url first")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self._client_id,
            "code_verifier": self._code_verifier,
        }

        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPError as e:
                raise AuthError("Failed to exchange code for token", details=str(e))

        token = self._parse_token_response(token_data)
        self._save_token(token)
        return token

    def _parse_token_response(self, data: dict[str, Any]) -> StoredToken:
        """Parse OAuth token response into StoredToken."""
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

        return StoredToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            provider_name=self._provider_name,
        )

    def run_auth_flow(self, open_browser: bool = True) -> StoredToken:
        """Run the interactive OAuth authorization flow.

        Opens browser for user to authorize, starts local server
        to receive callback, exchanges code for tokens.

        Args:
            open_browser: Whether to automatically open the browser

        Returns:
            StoredToken with obtained credentials
        """
        auth_url = self.get_authorization_url()

        # Callback server to receive the OAuth redirect
        received_code: dict[str, str | None] = {"code": None, "error": None}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if "code" in params:
                    received_code["code"] = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>Authorization successful!</h1>"
                        b"<p>You can close this window.</p></body></html>"
                    )
                elif "error" in params:
                    received_code["error"] = params.get("error_description", params["error"])[0]
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        f"<html><body><h1>Authorization failed</h1>"
                        f"<p>{received_code['error']}</p></body></html>".encode()
                    )
                else:
                    self.send_response(400)
                    self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                pass  # Suppress logging

        # Start callback server
        server = HTTPServer(("localhost", self._redirect_port), CallbackHandler)
        server_thread = Thread(target=server.handle_request)
        server_thread.start()

        # Open browser
        if open_browser:
            webbrowser.open(auth_url)

        # Wait for callback
        server_thread.join(timeout=300)  # 5 minute timeout
        server.server_close()

        if received_code["error"]:
            raise AuthError("OAuth authorization failed", details=received_code["error"])

        if received_code["code"] is None:
            raise AuthError("No authorization code received", details="Timeout or user cancelled")

        # Exchange code for tokens
        return asyncio.run(self.exchange_code(received_code["code"]))

    def clear_token(self) -> None:
        """Clear stored token for this provider."""
        self._token = None
        self._storage.delete(self._provider_name)
