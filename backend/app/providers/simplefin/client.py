"""SimpleFIN Bridge HTTP client.

Protocol:
  1. User gets a one-time Setup Token from simplefin.org (base64-encoded claim URL).
  2. Claim the token: POST to the decoded URL → response body is the Access URL.
  3. Access URL includes embedded basic-auth credentials:
       https://user:pass@beta-bridge.simplefin.org/simplefin
  4. Fetch accounts + transactions:
       GET {access_url}/accounts?start-date={unix_timestamp}
"""

import base64
from datetime import date, datetime, timezone

import httpx


class SimpleFINError(Exception):
    """Base error for SimpleFIN client problems."""


class SimpleFINAuthError(SimpleFINError):
    """Access URL credentials are invalid or expired (HTTP 401/403)."""


class SimpleFINConnectionError(SimpleFINError):
    """Network-level error reaching SimpleFIN Bridge."""


class SimpleFINClient:
    """Low-level HTTP client for the SimpleFIN Bridge API."""

    @staticmethod
    def claim_setup_token(setup_token: str) -> str:
        """Decode a Setup Token and POST to the claim URL to obtain an Access URL.

        The returned Access URL is the long-lived credential that should be
        stored in the database as ``enrollment_token``.

        Raises:
            SimpleFINError: If the token is not valid base64.
            SimpleFINAuthError: If the token has already been claimed.
            SimpleFINConnectionError: If the claim URL is unreachable.
        """
        try:
            claim_url = base64.b64decode(setup_token.strip()).decode()
        except Exception as exc:
            raise SimpleFINError(f"Invalid setup token (not valid base64): {exc}") from exc

        try:
            resp = httpx.post(claim_url, timeout=30)
        except httpx.RequestError as exc:
            raise SimpleFINConnectionError(f"Could not reach SimpleFIN claim URL: {exc}") from exc

        if resp.status_code in (401, 403):
            raise SimpleFINAuthError("Setup token has already been claimed or is invalid.")
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise SimpleFINError(f"SimpleFIN claim failed (HTTP {resp.status_code}): {exc}") from exc
        return resp.text.strip()

    def __init__(self, access_url: str):
        """
        Args:
            access_url: The long-lived Access URL returned by claim_setup_token().
                        Contains embedded basic-auth credentials in the URL.
        """
        self._access_url = access_url.rstrip("/")

    def get_accounts(self, start_date: date | None = None) -> dict:
        """Fetch all connected accounts and their embedded transactions.

        Args:
            start_date: If provided, only return transactions on or after this date.
                        Converted to a Unix timestamp as required by the API.

        Returns:
            Raw SimpleFIN response dict with 'accounts' list and top-level 'errors'.

        Raises:
            SimpleFINAuthError: If credentials are invalid (HTTP 401).
            SimpleFINConnectionError: On network failure.
        """
        params: dict = {}
        if start_date is not None:
            ts = int(
                datetime.combine(start_date, datetime.min.time())
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            params["start-date"] = str(ts)

        try:
            resp = httpx.get(
                f"{self._access_url}/accounts",
                params=params,
                timeout=30,
            )
        except httpx.RequestError as exc:
            raise SimpleFINConnectionError(f"Could not reach SimpleFIN: {exc}") from exc

        if resp.status_code == 401:
            raise SimpleFINAuthError("SimpleFIN access URL credentials are invalid or expired.")
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise SimpleFINError(f"SimpleFIN accounts request failed (HTTP {resp.status_code}): {exc}") from exc
        return resp.json()
