"""Integration tests for LMN (Letter of Medical Necessity) endpoints.

S3 is mocked via unittest.mock — we test our HTTP layer, DB operations,
auth guards, and household-scoped access.
"""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from app.models.bank import BankConnection, BankTransaction
from app.models.family import FamilyMember
from app.models.lmn import LmnDocument

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_member(db_session, household_id, name="Test Member"):
    member = FamilyMember(
        id=uuid.uuid4(),
        household_id=household_id,
        name=name,
        member_relationship="spouse",
        is_tax_dependent=False,
    )
    db_session.add(member)
    db_session.flush()
    return member


def _make_lmn(db_session, family_member_id, user_id, status="confirmed", label=None):
    doc = LmnDocument(
        id=uuid.uuid4(),
        family_member_id=family_member_id,
        user_id=user_id,
        s3_key=f"development/{user_id}/lmn/{family_member_id}/{uuid.uuid4()}-letter.pdf",
        original_filename="letter.pdf",
        content_type="application/pdf",
        file_size_bytes=50000,
        status=status,
        label=label,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _make_connection(db_session, user_id):
    conn = BankConnection(
        id=uuid.uuid4(),
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:8]}",
        account_name="HSA Checking",
        account_type="depository",
        account_subtype="hsa",
        institution_name="Test Bank",
        last_four="1234",
        currency="USD",
        enrollment_token="tok_test",
        is_active=True,
        user_id=user_id,
    )
    db_session.add(conn)
    db_session.flush()
    return conn


def _make_transaction(db_session, connection_id, lmn_document_id=None):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=date(2026, 3, 1),
        description="CVS Pharmacy",
        amount="-42.00",
        transaction_type="card_payment",
        status="posted",
        is_hsa_eligible=True,
        lmn_document_id=lmn_document_id,
    )
    db_session.add(txn)
    db_session.flush()
    return txn


def _mock_s3():
    m = MagicMock()
    m.generate_presigned_put_url.return_value = "https://s3.example.com/put-url"
    m.generate_presigned_get_url.return_value = "https://s3.example.com/get-url"
    m.object_exists.return_value = True
    return m


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestLmnAuthRequired:
    def test_presign_requires_auth(self, client):
        resp = client.post(
            f"/api/v1/families/{uuid.uuid4()}/lmn/presign",
            json={"filename": "l.pdf", "content_type": "application/pdf", "file_size_bytes": 1000},
        )
        assert resp.status_code == 401

    def test_list_requires_auth(self, client):
        resp = client.get(f"/api/v1/families/{uuid.uuid4()}/lmn")
        assert resp.status_code == 401

    def test_list_all_requires_auth(self, client):
        resp = client.get("/api/v1/families/lmn")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Presign
# ---------------------------------------------------------------------------

class TestLmnPresign:
    def test_presign_creates_pending_lmn(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/families/{member.id}/lmn/presign",
                json={
                    "filename": "letter.pdf",
                    "content_type": "application/pdf",
                    "file_size_bytes": 50000,
                    "label": "Orthodontic LMN",
                    "provider_name": "Dr. Smith",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "lmn_id" in data
        assert data["upload_url"] == "https://s3.example.com/put-url"

        doc = db_session.query(LmnDocument).filter(LmnDocument.id == data["lmn_id"]).first()
        assert doc is not None
        assert doc.status == "pending"
        assert doc.label == "Orthodontic LMN"
        assert doc.provider_name == "Dr. Smith"

    def test_presign_rejects_unsupported_mime(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        db_session.commit()

        resp = client.post(
            f"/api/v1/families/{member.id}/lmn/presign",
            json={"filename": "script.js", "content_type": "text/javascript", "file_size_bytes": 1000},
            headers=auth_headers,
        )
        assert resp.status_code == 415

    def test_presign_rejects_oversized_file(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        db_session.commit()

        resp = client.post(
            f"/api/v1/families/{member.id}/lmn/presign",
            json={"filename": "big.pdf", "content_type": "application/pdf", "file_size_bytes": 11 * 1024 * 1024},
            headers=auth_headers,
        )
        assert resp.status_code == 413

    def test_presign_rejects_nonexistent_member(self, client, auth_headers, test_user, db_session, test_user_household):
        db_session.commit()

        resp = client.post(
            f"/api/v1/families/{uuid.uuid4()}/lmn/presign",
            json={"filename": "l.pdf", "content_type": "application/pdf", "file_size_bytes": 1000},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

class TestLmnConfirm:
    def test_confirm_marks_lmn_confirmed(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        doc = _make_lmn(db_session, member.id, test_user.id, status="pending")
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/families/{member.id}/lmn/{doc.id}/confirm",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(doc.id)
        assert data["url"] == "https://s3.example.com/get-url"

        db_session.refresh(doc)
        assert doc.status == "confirmed"

    def test_confirm_returns_422_when_s3_missing(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        doc = _make_lmn(db_session, member.id, test_user.id, status="pending")
        db_session.commit()

        mock_s3 = _mock_s3()
        mock_s3.object_exists.return_value = False
        with patch("app.api.v1.endpoints.lmn.s3_service", mock_s3):
            resp = client.post(
                f"/api/v1/families/{member.id}/lmn/{doc.id}/confirm",
                headers=auth_headers,
            )
        assert resp.status_code == 422

    def test_confirm_rejects_already_confirmed(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        doc = _make_lmn(db_session, member.id, test_user.id, status="confirmed")
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/families/{member.id}/lmn/{doc.id}/confirm",
                headers=auth_headers,
            )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestLmnList:
    def test_list_returns_confirmed_lmns_for_member(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        _make_lmn(db_session, member.id, test_user.id, status="confirmed", label="LMN 1")
        _make_lmn(db_session, member.id, test_user.id, status="pending")
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.get(f"/api/v1/families/{member.id}/lmn", headers=auth_headers)

        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["label"] == "LMN 1"
        assert docs[0]["family_member_name"] == "Test Member"

    def test_list_all_returns_lmns_across_members(self, client, auth_headers, test_user, db_session, test_user_household):
        member1 = _make_member(db_session, test_user_household.id, name="Member 1")
        member2 = _make_member(db_session, test_user_household.id, name="Member 2")
        _make_lmn(db_session, member1.id, test_user.id, label="LMN A")
        _make_lmn(db_session, member2.id, test_user.id, label="LMN B")
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.get("/api/v1/families/lmn", headers=auth_headers)

        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 2


# ---------------------------------------------------------------------------
# Update metadata
# ---------------------------------------------------------------------------

class TestLmnUpdate:
    def test_update_metadata(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        doc = _make_lmn(db_session, member.id, test_user.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.lmn.s3_service", _mock_s3()):
            resp = client.patch(
                f"/api/v1/families/{member.id}/lmn/{doc.id}",
                json={"label": "Updated Label", "provider_name": "Dr. Jones", "issue_date": "2026-01-15"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "Updated Label"
        assert data["provider_name"] == "Dr. Jones"
        assert data["issue_date"] == "2026-01-15"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestLmnDelete:
    def test_delete_removes_lmn_and_clears_transaction_fk(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        doc = _make_lmn(db_session, member.id, test_user.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, lmn_document_id=doc.id)
        doc_id = doc.id
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.lmn.s3_service", mock_s3):
            resp = client.delete(
                f"/api/v1/families/{member.id}/lmn/{doc_id}",
                headers=auth_headers,
            )

        assert resp.status_code == 204
        mock_s3.delete.assert_called_once()

        # LMN row removed
        assert db_session.query(LmnDocument).filter(LmnDocument.id == doc_id).first() is None
        # Transaction FK cleared
        db_session.refresh(txn)
        assert txn.lmn_document_id is None

    def test_delete_returns_404_for_wrong_member(self, client, auth_headers, test_user, db_session, test_user_household):
        member1 = _make_member(db_session, test_user_household.id, name="M1")
        member2 = _make_member(db_session, test_user_household.id, name="M2")
        doc = _make_lmn(db_session, member1.id, test_user.id)
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.lmn.s3_service", mock_s3):
            resp = client.delete(
                f"/api/v1/families/{member2.id}/lmn/{doc.id}",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        mock_s3.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Transaction annotation with lmn_document_id
# ---------------------------------------------------------------------------

class TestTransactionLmnAnnotation:
    def test_annotate_transaction_with_lmn(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        lmn = _make_lmn(db_session, member.id, test_user.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"lmn_document_id": str(lmn.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["lmn_document_id"] == str(lmn.id)

    def test_annotate_transaction_clear_lmn(self, client, auth_headers, test_user, db_session, test_user_household):
        member = _make_member(db_session, test_user_household.id)
        lmn = _make_lmn(db_session, member.id, test_user.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, lmn_document_id=lmn.id)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"lmn_document_id": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["lmn_document_id"] is None

    def test_annotate_transaction_rejects_invalid_lmn(self, client, auth_headers, test_user, db_session, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"lmn_document_id": str(uuid.uuid4())},
            headers=auth_headers,
        )
        assert resp.status_code == 422
