"""Teller.io HTTP client with mutual TLS authentication.

Teller requires a client certificate + private key (mTLS) for all requests.
Teller Connect returns a per-enrollment access token that must be sent as
HTTP Basic Auth (token as username, empty password) alongside the mTLS cert.

Certs are stored base64-encoded in Doppler and decoded at runtime. Temp files
are created, used to build the SSL context, then immediately deleted.
"""

import base64
import certifi
import os
import ssl
import tempfile
from typing import Any, Optional

import httpx

TELLER_BASE_URL = "https://api.teller.io"


class TellerAPIError(Exception):
    """Raised when Teller returns an unexpected HTTP error."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TellerDisconnectedError(TellerAPIError):
    """Raised when Teller returns 404 — the enrollment/account no longer exists."""


class TellerAuthError(TellerAPIError):
    """Raised when Teller returns 401 — the enrollment token is invalid or revoked."""


class TellerClient:
    def __init__(self, cert_b64: str, key_b64: str, access_token: Optional[str] = None):
        ssl_ctx = self._build_ssl_context(cert_b64, key_b64)
        self._client = httpx.Client(
            base_url=TELLER_BASE_URL,
            verify=ssl_ctx,
            auth=(access_token, "") if access_token else None,
            timeout=30.0,
        )

    def _build_ssl_context(self, cert_b64: str, key_b64: str) -> ssl.SSLContext:
        cert_bytes = base64.b64decode(cert_b64)
        key_bytes = base64.b64decode(key_b64)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(certifi.where())

        # Write to temp files, load into ctx, then delete immediately
        cert_path = key_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
                cf.write(cert_bytes)
                cert_path = cf.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as kf:
                kf.write(key_bytes)
                key_path = kf.name
            ctx.load_cert_chain(cert_path, key_path)
        finally:
            if cert_path:
                os.unlink(cert_path)
            if key_path:
                os.unlink(key_path)

        return ctx

    def get(self, path: str, params: dict | None = None) -> Any:
        response = self._client.get(path, params=params or {})
        if response.status_code == 401:
            raise TellerAuthError(
                f"Teller returned 401 for {path}. Enrollment token is invalid or revoked.",
                status_code=401,
            )
        if response.status_code == 404:
            raise TellerDisconnectedError(
                f"Teller returned 404 for {path}. Account or enrollment no longer exists.",
                status_code=404,
            )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
