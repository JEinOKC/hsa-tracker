"""Tests for SimpleFINClient — token claiming, account fetching, error handling."""

import base64
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from app.providers.simplefin.client import (
    SimpleFINAuthError,
    SimpleFINClient,
    SimpleFINConnectionError,
    SimpleFINError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


def _mock_response(status_code: int, text: str = "", json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
        if status_code >= 400
        else None
    )
    return resp


# ---------------------------------------------------------------------------
# claim_setup_token
# ---------------------------------------------------------------------------


class TestClaimSetupToken:
    def test_decodes_base64_and_posts_to_claim_url(self):
        claim_url = "https://beta-bridge.simplefin.org/simplefin/claim/abc123"
        access_url = "https://user:pass@beta-bridge.simplefin.org/simplefin"
        token = _b64(claim_url)

        with patch("app.providers.simplefin.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(200, text=access_url)
            result = SimpleFINClient.claim_setup_token(token)

        mock_post.assert_called_once_with(claim_url, timeout=30)
        assert result == access_url

    def test_strips_whitespace_from_returned_url(self):
        token = _b64("https://example.com/claim")
        with patch("app.providers.simplefin.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(200, text="  https://u:p@bridge.com/sf  \n")
            result = SimpleFINClient.claim_setup_token(token)
        assert result == "https://u:p@bridge.com/sf"

    def test_invalid_base64_raises_simplefin_error(self):
        with pytest.raises(SimpleFINError, match="not valid base64"):
            SimpleFINClient.claim_setup_token("not!!valid!!base64")

    def test_401_raises_simplefin_auth_error(self):
        token = _b64("https://example.com/claim")
        with patch("app.providers.simplefin.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(401)
            with pytest.raises(SimpleFINAuthError, match="already been claimed"):
                SimpleFINClient.claim_setup_token(token)

    def test_403_raises_simplefin_auth_error(self):
        """SimpleFIN returns 403 (not 401) when a token has already been claimed."""
        token = _b64("https://example.com/claim")
        with patch("app.providers.simplefin.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(403)
            with pytest.raises(SimpleFINAuthError, match="already been claimed"):
                SimpleFINClient.claim_setup_token(token)

    def test_network_error_raises_connection_error(self):
        token = _b64("https://example.com/claim")
        with patch("app.providers.simplefin.client.httpx.post") as mock_post:
            mock_post.side_effect = httpx.RequestError("timeout")
            with pytest.raises(SimpleFINConnectionError, match="claim URL"):
                SimpleFINClient.claim_setup_token(token)


# ---------------------------------------------------------------------------
# get_accounts
# ---------------------------------------------------------------------------


class TestGetAccounts:
    def _make_client(self, access_url="https://u:p@bridge.simplefin.org/simplefin"):
        return SimpleFINClient(access_url)

    def test_fetches_from_access_url_accounts_endpoint(self):
        client = self._make_client("https://u:p@bridge.simplefin.org/simplefin")
        payload = {"accounts": [], "errors": []}

        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, json_data=payload)
            result = client.get_accounts()

        mock_get.assert_called_once_with(
            "https://u:p@bridge.simplefin.org/simplefin/accounts",
            params={},
            timeout=30,
        )
        assert result == payload

    def test_passes_start_date_as_unix_timestamp(self):
        client = self._make_client()
        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, json_data={"accounts": []})
            client.get_accounts(start_date=date(2026, 1, 1))

        call_params = mock_get.call_args[1]["params"]
        ts = int(call_params["start-date"])
        # 2026-01-01 00:00:00 UTC = 1767225600
        assert ts == 1767225600

    def test_no_start_date_sends_empty_params(self):
        client = self._make_client()
        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, json_data={"accounts": []})
            client.get_accounts()
        assert mock_get.call_args[1]["params"] == {}

    def test_401_raises_simplefin_auth_error(self):
        client = self._make_client()
        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(401)
            with pytest.raises(SimpleFINAuthError, match="invalid or expired"):
                client.get_accounts()

    def test_network_error_raises_connection_error(self):
        client = self._make_client()
        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.side_effect = httpx.RequestError("connection refused")
            with pytest.raises(SimpleFINConnectionError, match="Could not reach"):
                client.get_accounts()

    def test_trailing_slash_stripped_from_access_url(self):
        client = SimpleFINClient("https://u:p@bridge.simplefin.org/simplefin/")
        with patch("app.providers.simplefin.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, json_data={"accounts": []})
            client.get_accounts()
        url_arg = mock_get.call_args[0][0]
        assert url_arg == "https://u:p@bridge.simplefin.org/simplefin/accounts"
        assert "//" not in url_arg.replace("https://", "")
