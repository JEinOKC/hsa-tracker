"""Unit tests for app.utils.security - JWT tokens and WebAuthn helpers."""

from datetime import timedelta

from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_webauthn_challenge,
    encode_webauthn_challenge,
    generate_webauthn_challenge,
)


class TestJWTTokens:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_access_token(self):
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_create_refresh_token_has_refresh_type(self):
        token = create_refresh_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_access_and_refresh_tokens_differ(self):
        access = create_access_token({"sub": "user-123"})
        refresh = create_refresh_token({"sub": "user-123"})
        assert access != refresh

    def test_decode_garbage_token_returns_none(self):
        assert decode_token("not.a.valid.jwt") is None

    def test_decode_empty_string_returns_none(self):
        assert decode_token("") is None

    def test_decode_expired_token_returns_none(self):
        token = create_access_token(
            {"sub": "user-123"}, expires_delta=timedelta(seconds=-1)
        )
        assert decode_token(token) is None

    def test_token_preserves_custom_claims(self):
        token = create_access_token({"sub": "user-123", "custom": "value"})
        payload = decode_token(token)
        assert payload["custom"] == "value"


class TestWebAuthnChallengeHelpers:
    def test_generate_challenge_returns_32_bytes(self):
        challenge = generate_webauthn_challenge()
        assert isinstance(challenge, bytes)
        assert len(challenge) == 32

    def test_generate_challenge_is_unique(self):
        c1 = generate_webauthn_challenge()
        c2 = generate_webauthn_challenge()
        assert c1 != c2

    def test_encode_decode_roundtrip(self):
        challenge = generate_webauthn_challenge()
        encoded = encode_webauthn_challenge(challenge)
        decoded = decode_webauthn_challenge(encoded)
        assert decoded == challenge

    def test_encoded_challenge_is_string(self):
        challenge = generate_webauthn_challenge()
        encoded = encode_webauthn_challenge(challenge)
        assert isinstance(encoded, str)
