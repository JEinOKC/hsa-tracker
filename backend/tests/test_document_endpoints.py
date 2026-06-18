"""Integration tests for receipt/document endpoints.

S3 is mocked via unittest.mock — we test our HTTP layer, DB operations,
auth guards, and ownership enforcement, not real AWS.
"""

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.models.bank import BankConnection, BankTransaction, TransactionDocument
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection(db_session, user_id, active=True):
    conn = BankConnection(
        id=uuid.uuid4(),
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:8]}",
        account_name="HSA Checking",
        account_type="depository",
        account_subtype="hsa",
        institution_name="First National Bank",
        last_four="1234",
        currency="USD",
        enrollment_token="tok_test",
        is_active=active,
        user_id=user_id,
    )
    db_session.add(conn)
    db_session.flush()
    return conn


def _make_transaction(db_session, connection_id):
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
    )
    db_session.add(txn)
    db_session.flush()
    return txn


def _make_other_user(db_session):
    """Create a second user for ownership-isolation tests."""
    user = User(
        id=uuid.uuid4(),
        username=f"other_{uuid.uuid4().hex[:8]}",
        display_name="Other User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_document(db_session, transaction_id, user_id, status="confirmed"):
    doc = TransactionDocument(
        id=uuid.uuid4(),
        transaction_id=transaction_id,
        user_id=user_id,
        s3_key=f"development/{user_id}/{transaction_id}/{uuid.uuid4()}-receipt.jpg",
        original_filename="receipt.jpg",
        content_type="image/jpeg",
        file_size_bytes=102400,
        status=status,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _mock_s3():
    """Return a MagicMock for s3_service with sensible defaults."""
    m = MagicMock()
    m.generate_presigned_put_url.return_value = "https://s3.example.com/put-url"
    m.generate_presigned_get_url.return_value = "https://s3.example.com/get-url"
    m.object_exists.return_value = True
    return m


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestDocumentAuthRequired:
    def test_presign_requires_auth(self, client):
        resp = client.post(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/documents/presign",
            json={"filename": "r.jpg", "content_type": "image/jpeg", "file_size_bytes": 1000},
        )
        assert resp.status_code == 403

    def test_confirm_requires_auth(self, client):
        resp = client.post(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/documents/{uuid.uuid4()}/confirm"
        )
        assert resp.status_code == 403

    def test_list_requires_auth(self, client):
        resp = client.get(f"/api/v1/bank/transactions/{uuid.uuid4()}/documents")
        assert resp.status_code == 403

    def test_delete_requires_auth(self, client):
        resp = client.delete(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/documents/{uuid.uuid4()}"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Presign
# ---------------------------------------------------------------------------

class TestPresign:
    def test_presign_creates_pending_document(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/presign",
                json={"filename": "receipt.jpg", "content_type": "image/jpeg", "file_size_bytes": 50000},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "document_id" in data
        assert data["upload_url"] == "https://s3.example.com/put-url"
        assert "s3_key" in data

        doc = db_session.query(TransactionDocument).filter(
            TransactionDocument.id == data["document_id"]
        ).first()
        assert doc is not None
        assert doc.status == "pending"
        assert doc.original_filename == "receipt.jpg"

    def test_presign_rejects_unsupported_mime_type(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/documents/presign",
            json={"filename": "script.js", "content_type": "text/javascript", "file_size_bytes": 1000},
            headers=auth_headers,
        )
        assert resp.status_code == 415

    def test_presign_rejects_oversized_file(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        oversized = 11 * 1024 * 1024  # 11 MB, over the 10 MB limit
        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/documents/presign",
            json={"filename": "big.jpg", "content_type": "image/jpeg", "file_size_bytes": oversized},
            headers=auth_headers,
        )
        assert resp.status_code == 413

    def test_presign_rejects_other_users_transaction(self, client, auth_headers, db_session):
        # Transaction belongs to a different user (no connection for test_user)
        other_user = _make_other_user(db_session)
        conn = _make_connection(db_session, other_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/presign",
                json={"filename": "r.jpg", "content_type": "image/jpeg", "file_size_bytes": 1000},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_presign_accepts_pdf(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/presign",
                json={"filename": "eob.pdf", "content_type": "application/pdf", "file_size_bytes": 500000},
                headers=auth_headers,
            )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

class TestConfirm:
    def test_confirm_marks_document_confirmed(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        doc = _make_document(db_session, txn.id, test_user.id, status="pending")
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.documents.s3_service", mock_s3):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/{doc.id}/confirm",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(doc.id)
        assert data["url"] == "https://s3.example.com/get-url"

        db_session.refresh(doc)
        assert doc.status == "confirmed"

    def test_confirm_returns_422_when_object_not_in_s3(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        doc = _make_document(db_session, txn.id, test_user.id, status="pending")
        db_session.commit()

        mock_s3 = _mock_s3()
        mock_s3.object_exists.return_value = False
        with patch("app.api.v1.endpoints.documents.s3_service", mock_s3):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/{doc.id}/confirm",
                headers=auth_headers,
            )
        assert resp.status_code == 422

    def test_confirm_rejects_other_users_document(self, client, auth_headers, db_session):
        other_user = _make_other_user(db_session)
        conn = _make_connection(db_session, other_user.id)
        txn = _make_transaction(db_session, conn.id)
        doc = _make_document(db_session, txn.id, other_user.id, status="pending")
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.documents.s3_service", mock_s3):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/{doc.id}/confirm",
                headers=auth_headers,
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_list_returns_confirmed_documents(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        _make_document(db_session, txn.id, test_user.id, status="confirmed")
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.get(
                f"/api/v1/bank/transactions/{txn.id}/documents",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["original_filename"] == "receipt.jpg"
        assert docs[0]["url"] == "https://s3.example.com/get-url"

    def test_list_excludes_pending_documents(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        _make_document(db_session, txn.id, test_user.id, status="pending")
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.get(
                f"/api/v1/bank/transactions/{txn.id}/documents",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_empty_when_no_documents(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.get(
                f"/api/v1/bank/transactions/{txn.id}/documents",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_delete_removes_db_row_and_calls_s3_delete(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        doc = _make_document(db_session, txn.id, test_user.id)
        doc_id = doc.id
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.documents.s3_service", mock_s3):
            resp = client.delete(
                f"/api/v1/bank/transactions/{txn.id}/documents/{doc_id}",
                headers=auth_headers,
            )

        assert resp.status_code == 204
        mock_s3.delete.assert_called_once()
        remaining = db_session.query(TransactionDocument).filter(
            TransactionDocument.id == doc_id
        ).first()
        assert remaining is None

    def test_delete_rejects_other_users_document(self, client, auth_headers, db_session):
        other_user = _make_other_user(db_session)
        conn = _make_connection(db_session, other_user.id)
        txn = _make_transaction(db_session, conn.id)
        doc = _make_document(db_session, txn.id, other_user.id)
        db_session.commit()

        mock_s3 = _mock_s3()
        with patch("app.api.v1.endpoints.documents.s3_service", mock_s3):
            resp = client.delete(
                f"/api/v1/bank/transactions/{txn.id}/documents/{doc.id}",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        mock_s3.delete.assert_not_called()


# ---------------------------------------------------------------------------
# document_count in transaction list
# ---------------------------------------------------------------------------

class TestDocumentCountInTransactionList:
    def test_document_count_is_zero_when_no_documents(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id)
        db_session.commit()

        resp = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert resp.status_code == 200
        txns = resp.json()
        assert len(txns) == 1
        assert txns[0]["document_count"] == 0

    def test_document_count_reflects_confirmed_documents(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        _make_document(db_session, txn.id, test_user.id, status="confirmed")
        _make_document(db_session, txn.id, test_user.id, status="confirmed")
        db_session.commit()

        resp = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert resp.status_code == 200
        txns = resp.json()
        assert txns[0]["document_count"] == 2

    def test_pending_documents_not_counted(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        _make_document(db_session, txn.id, test_user.id, status="pending")
        db_session.commit()

        resp = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert resp.status_code == 200
        txns = resp.json()
        assert txns[0]["document_count"] == 0


# ---------------------------------------------------------------------------
# reimbursed_at auto-set
# ---------------------------------------------------------------------------

class TestReimbursedAt:
    def test_reimbursed_at_auto_set_when_marking_reimbursed(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"reimbursement_status": "reimbursed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reimbursement_status"] == "reimbursed"
        assert data["reimbursed_at"] is not None

    def test_reimbursed_at_cleared_when_status_removed(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        txn.reimbursement_status = "reimbursed"
        txn.reimbursed_at = datetime(2026, 3, 15)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"reimbursement_status": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reimbursed_at"] is None

    def test_explicit_reimbursed_at_is_respected(self, client, auth_headers, test_user, db_session):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        explicit_date = "2026-01-15T00:00:00"
        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"reimbursement_status": "reimbursed", "reimbursed_at": explicit_date},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "2026-01-15" in data["reimbursed_at"]


# ---------------------------------------------------------------------------
# Regression: document endpoints must work for manual transactions
# ---------------------------------------------------------------------------

def _make_manual_transaction(db_session, user_id):
    import uuid as _uuid
    from decimal import Decimal

    from app.models.bank import BankTransaction
    txn = BankTransaction(
        id=_uuid.uuid4(),
        connection_id=None,
        user_id=user_id,
        source="manual",
        provider="manual",
        provider_transaction_id=f"manual_{_uuid.uuid4().hex[:8]}",
        transaction_date=date(2026, 6, 2),
        description="Pulmonologist co-pay",
        amount=Decimal("-60.00"),
        transaction_type="manual",
        status="posted",
        details={"counterparty": {"name": "Baptist Pulmonary Medical"}},
        is_hsa_eligible=True,
    )
    db_session.add(txn)
    db_session.flush()
    return txn


class TestManualTransactionDocuments:
    """Presign and list endpoints must work for manual (connection_id=NULL) transactions."""

    def test_presign_works_for_manual_transaction(self, client, auth_headers, test_user, db_session):
        txn = _make_manual_transaction(db_session, test_user.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/presign",
                json={"filename": "receipt.jpg", "content_type": "image/jpeg", "file_size_bytes": 1024},
                headers=auth_headers,
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "upload_url" in data
        assert "document_id" in data

    def test_presign_returns_404_for_other_users_manual_transaction(self, client, auth_headers, db_session):
        other_user = User(
            id=uuid.uuid4(), username="other_doc_manual_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        txn = _make_manual_transaction(db_session, other_user.id)
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.post(
                f"/api/v1/bank/transactions/{txn.id}/documents/presign",
                json={"filename": "receipt.jpg", "content_type": "image/jpeg", "file_size_bytes": 1024},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_list_documents_works_for_manual_transaction(self, client, auth_headers, test_user, db_session):
        txn = _make_manual_transaction(db_session, test_user.id)
        _make_document(db_session, txn.id, test_user.id, status="confirmed")
        db_session.commit()

        with patch("app.api.v1.endpoints.documents.s3_service", _mock_s3()):
            resp = client.get(
                f"/api/v1/bank/transactions/{txn.id}/documents",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
