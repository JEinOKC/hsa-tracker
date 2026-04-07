"""Tests for DB-backed passkey challenge storage.

These tests cover the _save_challenge / _consume_challenge helpers that
replaced the in-memory _challenges dict, ensuring that:
  - Challenges are persisted and retrievable across separate calls (simulating
    separate Lambda invocations / containers).
  - Expired challenges are rejected.
  - Consuming a challenge deletes it (one-time use).
  - Saving a new challenge for the same username replaces the old one.
"""

from datetime import datetime, timedelta

import pytest

from app.api.v1.endpoints.passkey import _save_challenge, _consume_challenge
from app.models.user import PasskeyChallenge
from fastapi import HTTPException


_FAKE_CHALLENGE = b"\x01\x02\x03\x04\x05\x06\x07\x08"


class TestSaveChallenge:
    def test_persists_challenge_to_db(self, db_session):
        _save_challenge(db_session, "alice", _FAKE_CHALLENGE, "registration", {"display_name": "Alice"})
        db_session.commit()

        row = db_session.query(PasskeyChallenge).filter_by(username="alice").first()
        assert row is not None
        assert row.challenge_type == "registration"

    def test_replaces_existing_challenge_for_same_username(self, db_session):
        _save_challenge(db_session, "alice", _FAKE_CHALLENGE, "registration", {"display_name": "Alice"})
        db_session.commit()

        new_challenge = b"\x0a\x0b\x0c\x0d"
        _save_challenge(db_session, "alice", new_challenge, "registration", {"display_name": "Alice"})
        db_session.commit()

        rows = db_session.query(PasskeyChallenge).filter_by(username="alice").all()
        assert len(rows) == 1

    def test_stores_metadata_as_json(self, db_session):
        meta = {"display_name": "Alice", "invite_token": None, "invite_type": None}
        _save_challenge(db_session, "alice", _FAKE_CHALLENGE, "registration", meta)
        db_session.commit()

        row = db_session.query(PasskeyChallenge).filter_by(username="alice").first()
        assert "display_name" in row.metadata_json
        assert "Alice" in row.metadata_json

    def test_sets_expiry_in_future(self, db_session):
        _save_challenge(db_session, "alice", _FAKE_CHALLENGE, "registration", {})
        db_session.commit()

        row = db_session.query(PasskeyChallenge).filter_by(username="alice").first()
        assert row.expires_at > datetime.utcnow()


class TestConsumeChallenge:
    def test_returns_challenge_bytes_and_metadata(self, db_session):
        meta = {"display_name": "Bob", "invite_token": None}
        _save_challenge(db_session, "bob", _FAKE_CHALLENGE, "registration", meta)
        db_session.commit()

        result = _consume_challenge(db_session, "bob", "registration")

        assert result["challenge"] == _FAKE_CHALLENGE
        assert result["display_name"] == "Bob"

    def test_deletes_row_after_consumption(self, db_session):
        _save_challenge(db_session, "bob", _FAKE_CHALLENGE, "registration", {})
        db_session.commit()

        _consume_challenge(db_session, "bob", "registration")
        db_session.commit()

        row = db_session.query(PasskeyChallenge).filter_by(username="bob").first()
        assert row is None

    def test_raises_if_no_challenge_exists(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            _consume_challenge(db_session, "nobody", "registration")
        assert exc_info.value.status_code == 400

    def test_raises_if_wrong_challenge_type(self, db_session):
        _save_challenge(db_session, "carol", _FAKE_CHALLENGE, "registration", {})
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            _consume_challenge(db_session, "carol", "authentication")
        assert exc_info.value.status_code == 400

    def test_raises_and_cleans_up_if_expired(self, db_session):
        _save_challenge(db_session, "dave", _FAKE_CHALLENGE, "registration", {})
        db_session.commit()

        # Force expiry
        row = db_session.query(PasskeyChallenge).filter_by(username="dave").first()
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            _consume_challenge(db_session, "dave", "registration")
        assert exc_info.value.status_code == 400

        # Expired row should have been deleted
        db_session.commit()
        assert db_session.query(PasskeyChallenge).filter_by(username="dave").first() is None

    def test_challenge_is_one_time_use(self, db_session):
        _save_challenge(db_session, "eve", _FAKE_CHALLENGE, "authentication", {"user_id": "abc"})
        db_session.commit()

        _consume_challenge(db_session, "eve", "authentication")
        db_session.commit()

        with pytest.raises(HTTPException):
            _consume_challenge(db_session, "eve", "authentication")
