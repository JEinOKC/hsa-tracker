"""Unit tests for app.utils.webauthn - challenge generation and base64url encoding."""

import os
from unittest.mock import MagicMock, patch

from app.utils.webauthn import (
    base64url_to_bytes,
    bytes_to_base64url,
    create_authentication_options,
    create_registration_options,
    generate_challenge,
)


class TestGenerateChallenge:
    def test_returns_bytes(self):
        assert isinstance(generate_challenge(), bytes)

    def test_is_32_bytes(self):
        assert len(generate_challenge()) == 32

    def test_unique_each_call(self):
        challenges = {generate_challenge() for _ in range(10)}
        assert len(challenges) == 10


class TestBase64urlConversion:
    def test_roundtrip(self):
        original = b"\x00\x01\x02\xff\xfe\xfd"
        encoded = bytes_to_base64url(original)
        decoded = base64url_to_bytes(encoded)
        assert decoded == original

    def test_roundtrip_random_data(self):
        for _ in range(20):
            original = os.urandom(32)
            assert base64url_to_bytes(bytes_to_base64url(original)) == original

    def test_no_padding_in_output(self):
        encoded = bytes_to_base64url(b"test data here!!")
        assert "=" not in encoded

    def test_url_safe_characters(self):
        # Run with enough random data to hit + and / in standard base64
        for _ in range(50):
            encoded = bytes_to_base64url(os.urandom(32))
            assert "+" not in encoded
            assert "/" not in encoded

    def test_empty_bytes_roundtrip(self):
        assert base64url_to_bytes(bytes_to_base64url(b"")) == b""


class TestCreateRegistrationOptions:
    @patch("app.utils.webauthn.options_to_json")
    @patch("app.utils.webauthn.generate_registration_options")
    def test_calls_library_with_correct_params(self, mock_gen, mock_json):
        mock_json.return_value = '{"challenge": "abc"}'
        create_registration_options("testuser", "Test User", b"\x01" * 16)
        mock_gen.assert_called_once()
        kwargs = mock_gen.call_args.kwargs
        assert kwargs["user_name"] == "testuser"
        assert kwargs["user_display_name"] == "Test User"

    @patch("app.utils.webauthn.options_to_json")
    @patch("app.utils.webauthn.generate_registration_options")
    def test_returns_dict(self, mock_gen, mock_json):
        mock_json.return_value = '{"rp": {"name": "HSA Tracker"}}'
        result = create_registration_options("testuser", "Test", b"\x01" * 16)
        assert isinstance(result, dict)


class TestCreateAuthenticationOptions:
    @patch("app.utils.webauthn.options_to_json")
    @patch("app.utils.webauthn.generate_authentication_options")
    def test_with_empty_credentials(self, mock_gen, mock_json):
        mock_json.return_value = '{"challenge": "xyz"}'
        result = create_authentication_options(user_credentials=[])
        assert isinstance(result, dict)

    @patch("app.utils.webauthn.options_to_json")
    @patch("app.utils.webauthn.generate_authentication_options")
    def test_with_credential_list(self, mock_gen, mock_json):
        mock_json.return_value = '{"challenge": "xyz"}'
        creds = [
            {"credential_id": "cred-1", "transports": '["usb"]'},
            {"credential_id": "cred-2", "transports": None},
        ]
        result = create_authentication_options(user_credentials=creds)
        mock_gen.assert_called_once()
        assert isinstance(result, dict)
