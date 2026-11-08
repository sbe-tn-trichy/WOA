import threading
import time
from collections.abc import Mapping

from utils.http_utils import http_transport
from utils.http_utils.http import get_json_value, request_json

from zoho.core_sdk.exceptions import ZohoAuthError, ZohoConfigurationError, ZohoTokenResponseError, ZohoTokenServiceError


class HttpTokenProvider:
    """Retrieve service tokens from an HTTP token broker without persisting them."""

    def __init__(
        self,
        url: str,
        timeout: float = 10.0,
        fallback_services: Mapping[str, str] | None = None,
    ):
        if not url:
            raise ZohoConfigurationError("Token provider URL is required.")
        if timeout <= 0:
            raise ZohoConfigurationError("Token provider timeout must be positive.")
        self.url = url
        self.timeout = timeout
        self.fallback_services = dict(fallback_services or {})

    def __repr__(self) -> str:
        return f"{type(self).__name__}(url={self.url!r}, tokens=<not-stored>)"

    def get_tokens(self) -> dict[str, str | None]:
        try:
            tokens = request_json(
                "POST",
                self.url,
                headers={"Content-Type": "application/json"},
                json={},
                timeout=self.timeout,
                key="tokens",
                unwrap_body=True,
            )
            if not isinstance(tokens, Mapping) or any(
                not isinstance(key, str)
                or (value is not None and not isinstance(value, str))
                for key, value in tokens.items()
            ):
                raise ValueError("Response does not contain a tokens object.")
            return {
                k: v.strip() if isinstance(v, str) and v.strip() else None
                for k, v in tokens.items()
            }
        except http_transport.TransportError:
            raise ZohoTokenServiceError(
                "Unable to retrieve tokens from the token service."
            ) from None
        except (ValueError, LookupError, AttributeError):
            raise ZohoTokenResponseError(
                "Token service returned an invalid tokens object."
            ) from None

    def get_token(self, service: str) -> str:
        tokens = self.get_tokens()
        fallback = self.fallback_services.get(service)
        token = tokens.get(service) or (fallback and tokens.get(fallback))
        if not token:
            raise ZohoTokenResponseError(
                f"Token service did not return a token for {service!r}."
            )
        return token


class ZohoOAuth2Manager:
    """Caches a Zoho OAuth 2.0 access token and refreshes it when expired."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str | None = None,
        domain: str = "com",
        access_token: str | None = None,
        expires_at: float | None = None,
        keyring_service: str | None = None,
        keyring_username: str | None = None,
    ):
        if not client_id or not client_secret:
            raise ZohoConfigurationError("OAuth client_id and client_secret are required.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.domain = domain
        self.keyring_service = keyring_service
        self.keyring_username = keyring_username
        self._refresh_token = refresh_token
        self._access_token = access_token
        self._expires_at = expires_at or 0.0
        self._token_lock = threading.RLock()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(credentials=<redacted>)"

    @property
    def refresh_token(self) -> str:
        """Direct token, else the system keyring entry."""
        if self._refresh_token:
            return self._refresh_token
        if not (self.keyring_service and self.keyring_username):
            raise ZohoConfigurationError(
                "Must provide either 'refresh_token' or both "
                "'keyring_service' and 'keyring_username' parameters."
            )
        try:
            import keyring
        except ImportError:
            raise ZohoConfigurationError(
                "The 'keyring' library is required to retrieve the refresh "
                "token from the system keyring. Configure a direct refresh_token "
                "or provision keyring in the workspace environment."
            ) from None
        try:
            token = keyring.get_password(self.keyring_service, self.keyring_username)
        except Exception:
            # Keyring backends expose different exception types and may include
            # private entry details; keep this optional dependency boundary safe.
            raise ZohoConfigurationError("Unable to read the configured keyring entry.") from None
        if not token:
            raise ZohoConfigurationError(
                "No refresh token found in the configured keyring entry."
            )
        return token

    def get_token_url(self) -> str:
        return f"https://accounts.zoho.{self.domain}/oauth/v2/token"

    def refresh_access_token(self) -> str:
        """Exchange the refresh token for a new access token."""
        with self._token_lock:
            return self._refresh_access_token()

    def _refresh_access_token(self) -> str:
        payload = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }
        try:
            data = request_json(
                "POST", self.get_token_url(), data=payload, timeout=10,
                unwrap_body=True,
            )
        except http_transport.TransportError:
            raise ZohoTokenServiceError("Unable to refresh the OAuth access token.") from None
        except (ValueError, LookupError):
            raise ZohoTokenResponseError("OAuth service returned an invalid token response.") from None
        token = get_json_value(data, "access_token")
        if not isinstance(token, str) or not token.strip():
            raise ZohoTokenResponseError("OAuth service did not return a valid access token.")
        lifetime = get_json_value(data, "expires_in", default=3600)
        if isinstance(lifetime, bool) or not isinstance(lifetime, (str, int)):
            raise ZohoTokenResponseError("OAuth expires_in must be a positive integer.")
        try:
            expires_in = int(lifetime)
        except ValueError:
            raise ZohoTokenResponseError("OAuth expires_in must be a positive integer.") from None
        if expires_in <= 0:
            raise ZohoTokenResponseError("OAuth expires_in must be a positive integer.")
        # 60-second safety buffer before the real expiry
        try:
            expires_at = time.time() + expires_in - min(60, expires_in / 2)
        except OverflowError:
            raise ZohoTokenResponseError("OAuth expires_in exceeds the supported range.") from None
        self._access_token = token.strip()
        self._expires_at = expires_at
        return self._access_token

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if missing or expired."""
        with self._token_lock:
            if not self._access_token or time.time() >= self._expires_at:
                return self.refresh_access_token()
            return self._access_token


def fetch_token_from_catalyst(url: str, service_key: str) -> str:
    """
    Fetches the OAuth token for a specific service from the local Catalyst token endpoint.

    Raises ZohoAuthError when the broker cannot be reached or does not return the
    requested token. Error messages never include response payloads or tokens.
    """
    provider = HttpTokenProvider(url)
    return provider.get_token(service_key)


class CatalystAuth(str):
    """
    Dynamic authentication wrapper that behaves like a string.
    Allows explicit request mutation token switching via get_token_for_request(is_mutation).
    """
    def __new__(
        cls,
        direct_token: str,
        catalyst_token_url: str,
        service_key: str,
        allow_direct_token_fallback: bool = False,
    ):
        obj = str.__new__(cls, direct_token)
        obj.direct_token = direct_token
        obj.catalyst_token_url = catalyst_token_url
        obj.service_key = service_key
        obj.allow_direct_token_fallback = allow_direct_token_fallback
        return obj

    def get_token_for_request(self, is_mutation: bool) -> str:
        """Broker token for mutations; direct token for reads."""
        if not (is_mutation and self.catalyst_token_url):
            return self.direct_token
        try:
            return fetch_token_from_catalyst(
                self.catalyst_token_url, self.service_key
            )
        except ZohoAuthError:
            if self.allow_direct_token_fallback:
                return self.direct_token
            raise

    def __str__(self) -> str:
        # Default string conversion returns the direct token to avoid unexpected Catalyst triggers
        return self.direct_token
