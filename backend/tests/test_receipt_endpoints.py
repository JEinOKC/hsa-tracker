"""Integration tests for retailer import endpoints.

Uses SQLite in-memory DB (via conftest fixtures) and no external services.
"""

import io
import textwrap
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.bank import (
    BankConnection,
    BankTransaction,
    PharmacyFill,
    PharmacyImportBatch,
    ReceiptLineItem,
)
from app.models.user import User
from app.utils.security import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_transaction(db_session, connection_id, user_id=None, txn_date=date(2026, 3, 27), amount="-10.00", description="CVS Pharmacy"):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        user_id=user_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=txn_date,
        description=description,
        amount=amount,
        transaction_type="card_payment",
        status="posted",
    )
    db_session.add(txn)
    db_session.flush()
    return txn


def _make_manual_transaction(db_session, user_id, txn_date=date(2026, 3, 27), amount="-10.00"):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=None,
        user_id=user_id,
        source="manual",
        provider=None,
        provider_transaction_id=None,
        transaction_date=txn_date,
        description="Manual CVS charge",
        amount=amount,
        transaction_type="card_payment",
        status="posted",
    )
    db_session.add(txn)
    db_session.flush()
    return txn


def _make_other_user(db_session):
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


def _auth(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# A minimal CVS Financial Summary CSV with 2 fills
_CVS_CSV_2_ROWS = textwrap.dedent("""\
    Title,Date,Total Rx Spend
    Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$20.00

    Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00
    JAMES age 39,LISINOPRIL 10MG,9999999,2026-03-15,CVS Pharmacy®,$10.00,$0.00

    This report may not reflect all medicines dispensed.
""").encode("utf-8")

_CVS_CSV_UNMATCHED = textwrap.dedent("""\
    Title,Date,Total Rx Spend
    Financial Summary,"Jan 1, 2026 - Feb 1, 2026",$50.00

    Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
    JAMES age 39,SOME DRUG,1111111,2025-01-01,CVS Pharmacy®,$50.00,$0.00

    This report may not reflect all medicines dispensed.
""").encode("utf-8")


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


class TestReceiptAuthGuards:
    def test_cvs_import_requires_auth(self, client):
        resp = client.post("/api/v1/bank/imports/cvs-pharmacy", files={"file": ("f.csv", b"x", "text/csv")})
        assert resp.status_code == 403

    def test_list_fills_requires_auth(self, client):
        resp = client.get("/api/v1/bank/pharmacy-fills")
        assert resp.status_code == 403

    def test_list_line_items_requires_auth(self, client):
        resp = client.get(f"/api/v1/bank/transactions/{uuid.uuid4()}/line-items")
        assert resp.status_code == 403

    def test_import_line_items_csv_requires_auth(self, client):
        resp = client.post(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/line-items/import-csv",
            files={"file": ("f.csv", b"description,amount\nItem,5.00", "text/csv")},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CVS pharmacy import — happy path
# ---------------------------------------------------------------------------


class TestCvsPharmacyImport:
    def test_import_creates_fills_and_batch(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 27), amount="-10.00")
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15), amount="-10.00")
        db_session.commit()

        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("financial-summary.csv", _CVS_CSV_2_ROWS, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["row_count"] == 2
        assert data["matched"] == 2
        assert data["unmatched"] == 0
        assert len(data["fills"]) == 2
        assert all(f["matched"] for f in data["fills"])

    def test_import_sets_hsa_eligible_on_matched_transaction(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 27), amount="-10.00")
        db_session.commit()

        csv_one_row = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("financial-summary.csv", csv_one_row, "text/csv")},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.is_hsa_eligible is True
        assert txn.hsa_category == "prescription"
        assert txn.eligible_amount == Decimal("10.00")

    def test_import_appends_drug_name_to_notes(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 27), amount="-10.00")
        db_session.commit()

        csv_bytes = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert "WIXELA 250-50 INHUB" in txn.notes

    def test_import_does_not_overwrite_existing_eligible_amount(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 27), amount="-10.00")
        txn.eligible_amount = Decimal("7.50")  # manually set
        db_session.commit()

        csv_bytes = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount == Decimal("7.50")

    def test_unmatched_fill_stored_with_null_transaction_id(self, client, db_session, test_user):
        # No transactions in the DB at all
        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", _CVS_CSV_UNMATCHED, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["unmatched"] == 1
        assert data["matched"] == 0
        fill = data["fills"][0]
        assert fill["matched"] is False
        assert fill["transaction_id"] is None

    def test_import_matches_within_3_day_tolerance(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        # Transaction is 2 days after the fill date
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 29), amount="-10.00")
        db_session.commit()

        csv_bytes = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        data = resp.json()
        assert data["matched"] == 1

    def test_import_does_not_match_when_amount_too_different(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        # Transaction amount is $50 but fill is $10 — more than 2% difference
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 27), amount="-50.00")
        db_session.commit()

        csv_bytes = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        data = resp.json()
        assert data["matched"] == 0

    def test_import_wrong_file_returns_422(self, client, db_session, test_user):
        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("wrong.csv", b"name,email\njohn,john@example.com", "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 422

    def test_import_empty_file_returns_422(self, client, db_session, test_user):
        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("empty.csv", b"", "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 422

    def test_import_matches_manual_transaction(self, client, db_session, test_user):
        """Manual transactions (no connection_id) should also be matched."""
        txn = _make_manual_transaction(db_session, test_user.id, txn_date=date(2026, 3, 27), amount="-10.00")
        db_session.commit()

        csv_bytes = textwrap.dedent("""\
            Title,Date,Total Rx Spend
            Financial Summary,"Mar 1, 2026 - Apr 1, 2026",$10.00

            Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid
            JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00

            This report may not reflect all medicines dispensed.
        """).encode("utf-8")

        resp = client.post(
            "/api/v1/bank/imports/cvs-pharmacy",
            files={"file": ("f.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.json()["matched"] == 1


# ---------------------------------------------------------------------------
# Link / unlink fills
# ---------------------------------------------------------------------------


class TestFillLinking:
    def _create_unmatched_fill(self, db_session, user_id, batch_id):
        fill = PharmacyFill(
            id=uuid.uuid4(),
            user_id=user_id,
            import_batch_id=batch_id,
            transaction_id=None,
            drug_name="LISINOPRIL 10MG",
            rx_number="9999999",
            fill_date=date(2026, 3, 15),
            amount_paid=Decimal("10.00"),
            pharmacy="CVS Pharmacy",
            source="cvs_financial_summary",
        )
        db_session.add(fill)
        db_session.flush()
        return fill

    def _create_batch(self, db_session, user_id):
        batch = PharmacyImportBatch(
            id=uuid.uuid4(),
            user_id=user_id,
            filename="test.csv",
            source="cvs_financial_summary",
            row_count=1,
            matched=0,
            unmatched=1,
        )
        db_session.add(batch)
        db_session.flush()
        return batch

    def test_link_fill_applies_hsa_annotations(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        batch = self._create_batch(db_session, test_user.id)
        fill = self._create_unmatched_fill(db_session, test_user.id, batch.id)
        db_session.commit()

        resp = client.post(
            f"/api/v1/bank/pharmacy-fills/{fill.id}/link",
            json={"transaction_id": str(txn.id)},
            headers=_auth(test_user),
        )
        assert resp.status_code == 200

        db_session.refresh(txn)
        db_session.refresh(fill)
        assert fill.transaction_id == txn.id
        assert txn.is_hsa_eligible is True
        assert txn.hsa_category == "prescription"

    def test_unlink_fill_clears_transaction_id_only(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        txn.is_hsa_eligible = True
        txn.hsa_category = "prescription"
        batch = self._create_batch(db_session, test_user.id)
        fill = self._create_unmatched_fill(db_session, test_user.id, batch.id)
        fill.transaction_id = txn.id
        db_session.commit()

        resp = client.delete(
            f"/api/v1/bank/pharmacy-fills/{fill.id}/link",
            headers=_auth(test_user),
        )
        assert resp.status_code == 204

        db_session.refresh(fill)
        db_session.refresh(txn)
        assert fill.transaction_id is None
        # Annotations left untouched
        assert txn.is_hsa_eligible is True
        assert txn.hsa_category == "prescription"

    def test_link_wrong_user_returns_404(self, client, db_session, test_user):
        other = _make_other_user(db_session)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        batch = self._create_batch(db_session, other.id)
        fill = self._create_unmatched_fill(db_session, other.id, batch.id)
        db_session.commit()

        # test_user tries to link other's fill
        resp = client.post(
            f"/api/v1/bank/pharmacy-fills/{fill.id}/link",
            json={"transaction_id": str(txn.id)},
            headers=_auth(test_user),
        )
        assert resp.status_code == 404

    def test_list_unmatched_fills(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        batch = self._create_batch(db_session, test_user.id)
        fill_matched = self._create_unmatched_fill(db_session, test_user.id, batch.id)
        fill_matched.transaction_id = txn.id
        fill_unmatched = self._create_unmatched_fill(db_session, test_user.id, batch.id)
        db_session.commit()

        resp = client.get("/api/v1/bank/pharmacy-fills?unmatched=true", headers=_auth(test_user))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert str(fill_unmatched.id) in ids
        assert str(fill_matched.id) not in ids


# ---------------------------------------------------------------------------
# Generic line item CSV import
# ---------------------------------------------------------------------------


class TestLineItemCsvImport:
    def test_import_happy_path(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-20.00")
        db_session.commit()

        csv_bytes = b"description,amount,quantity,is_hsa_eligible,hsa_category\nBANDAGE,4.99,1,true,medical\nSHAMPOO,6.99,1,false,\n"

        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["item_count"] == 2
        assert data["eligible_total"] == "4.99"
        assert len(data["line_items"]) == 2

    def test_import_sets_eligible_amount_on_transaction(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-20.00")
        db_session.commit()

        csv_bytes = b"description,amount,is_hsa_eligible\nIBUPROFEN,8.49,true\nCHIPS,3.99,false\n"

        client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount == Decimal("8.49")

    def test_import_no_eligible_items_sets_eligible_amount_null(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-20.00")
        db_session.commit()

        csv_bytes = b"description,amount,is_hsa_eligible\nSHAMPOO,6.99,false\n"

        client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount is None

    def test_import_missing_description_column_returns_422(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        csv_bytes = b"name,amount\nItem,5.00\n"
        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 422
        assert "description" in resp.json()["detail"].lower()

    def test_import_missing_amount_column_returns_422(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        db_session.commit()

        csv_bytes = b"description,price\nItem,5.00\n"
        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 422
        assert "amount" in resp.json()["detail"].lower()

    def test_import_wrong_transaction_returns_404(self, client, db_session, test_user):
        csv_bytes = b"description,amount\nItem,5.00\n"
        resp = client.post(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 404

    def test_import_blank_is_hsa_eligible_stored_as_null(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        csv_bytes = b"description,amount,is_hsa_eligible\nMYSTERY ITEM,9.99,\n"
        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items/import-csv",
            files={"file": ("items.csv", csv_bytes, "text/csv")},
            headers=_auth(test_user),
        )
        assert resp.status_code == 201
        item = resp.json()["line_items"][0]
        assert item["is_hsa_eligible"] is None


# ---------------------------------------------------------------------------
# Line item CRUD
# ---------------------------------------------------------------------------


class TestLineItemCrud:
    def test_create_line_item(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "BANDAGE", "amount": "4.99", "is_hsa_eligible": True, "hsa_category": "medical"},
            headers=_auth(test_user),
        )
        assert resp.status_code == 201
        item = resp.json()
        assert item["description"] == "BANDAGE"
        assert item["source"] == "manual"

    def test_create_line_item_updates_eligible_amount(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "IBUPROFEN", "amount": "8.49", "is_hsa_eligible": True},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount == Decimal("8.49")

    def test_list_line_items(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "ITEM A", "amount": "3.00"},
            headers=_auth(test_user),
        )
        client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "ITEM B", "amount": "5.00"},
            headers=_auth(test_user),
        )

        resp = client.get(f"/api/v1/bank/transactions/{txn.id}/line-items", headers=_auth(test_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_line_item_recomputes_eligible_amount(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        create_resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "ITEM", "amount": "5.00", "is_hsa_eligible": False},
            headers=_auth(test_user),
        )
        item_id = create_resp.json()["id"]

        db_session.refresh(txn)
        assert txn.eligible_amount is None  # nothing eligible yet

        client.patch(
            f"/api/v1/bank/transactions/{txn.id}/line-items/{item_id}",
            json={"is_hsa_eligible": True},
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount == Decimal("5.00")

    def test_delete_last_eligible_item_resets_eligible_amount_to_null(self, client, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        create_resp = client.post(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            json={"description": "BANDAGE", "amount": "4.99", "is_hsa_eligible": True},
            headers=_auth(test_user),
        )
        item_id = create_resp.json()["id"]

        db_session.refresh(txn)
        assert txn.eligible_amount == Decimal("4.99")

        client.delete(
            f"/api/v1/bank/transactions/{txn.id}/line-items/{item_id}",
            headers=_auth(test_user),
        )
        db_session.refresh(txn)
        assert txn.eligible_amount is None

    def test_delete_wrong_transaction_returns_404(self, client, db_session, test_user):
        resp = client.delete(
            f"/api/v1/bank/transactions/{uuid.uuid4()}/line-items/{uuid.uuid4()}",
            headers=_auth(test_user),
        )
        assert resp.status_code == 404

    def test_other_user_cannot_access_line_items(self, client, db_session, test_user):
        other = _make_other_user(db_session)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, amount="-10.00")
        db_session.commit()

        resp = client.get(
            f"/api/v1/bank/transactions/{txn.id}/line-items",
            headers=_auth(other),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CSV template download
# ---------------------------------------------------------------------------


class TestCsvTemplate:
    def test_download_template(self, client):
        resp = client.get("/api/v1/bank/imports/line-items-template.csv")
        assert resp.status_code == 200
        assert "description" in resp.text
        assert "amount" in resp.text
        assert "is_hsa_eligible" in resp.text
