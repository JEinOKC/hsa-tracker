"""Tests for SimpleFINProvider — account parsing, transaction parsing, sign convention."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.providers.base import ExternalAccount, ExternalBalance
from app.providers.simplefin.provider import SimpleFINProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider():
    client = MagicMock()
    return SimpleFINProvider(client=client), client


def _raw_account(**overrides):
    base = {
        "id": "https://bridge.simplefin.org/simplefin/accounts/acct001",
        "org": {"name": "First National Bank", "domain": "firstnational.com"},
        "name": "HSA Checking",
        "currency": "USD",
        "balance": "1000.00",
        "available-balance": "950.00",
        "balance-date": 1751000000,
        "transactions": [],
    }
    base.update(overrides)
    return base


def _raw_txn(**overrides):
    base = {
        "id": "txn_001",
        "posted": 1751000000,  # Unix timestamp
        "amount": "-25.50",
        "description": "CVS Pharmacy",
        "payee": "CVS",
    }
    base.update(overrides)
    return base


def _ts(d: date) -> int:
    """Convert a date to midnight UTC Unix timestamp."""
    return int(datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# Account parsing
# ---------------------------------------------------------------------------


class TestParseAccount:
    def test_basic_fields(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {"accounts": [_raw_account()], "errors": []}

        accounts = provider.list_accounts()

        assert len(accounts) == 1
        a = accounts[0]
        assert isinstance(a, ExternalAccount)
        assert a.id == "https://bridge.simplefin.org/simplefin/accounts/acct001"
        assert a.name == "HSA Checking"
        assert a.provider == "simplefin"

    def test_institution_name_from_org(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(org={"name": "My Bank", "domain": "mybank.com"})],
            "errors": [],
        }

        accounts = provider.list_accounts()
        assert accounts[0].institution_name == "My Bank"

    def test_institution_name_falls_back_to_domain(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(org={"domain": "fallback.com"})],
            "errors": [],
        }

        accounts = provider.list_accounts()
        assert accounts[0].institution_name == "fallback.com"

    def test_currency_from_account(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(currency="EUR")],
            "errors": [],
        }

        accounts = provider.list_accounts()
        assert accounts[0].currency == "EUR"

    def test_type_is_depository(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {"accounts": [_raw_account()], "errors": []}

        accounts = provider.list_accounts()
        assert accounts[0].type == "depository"

    def test_last_four_parsed_from_parenthesized_digits(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(name="Rewards Credit Card (4321)")],
            "errors": [],
        }
        accounts = provider.list_accounts()
        assert accounts[0].last_four == "4321"

    def test_last_four_zero_padded_for_three_digits(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(name="Savings Account (789)")],
            "errors": [],
        }
        accounts = provider.list_accounts()
        assert accounts[0].last_four == "0789"

    def test_last_four_none_when_no_parenthesized_digits(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(name="HSA Checking")],
            "errors": [],
        }
        accounts = provider.list_accounts()
        assert accounts[0].last_four is None

    def test_last_four_from_hyphenated_name(self):
        """Some providers embed last4 twice: 'Cash Back Card-5678 (5678)' format."""
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(name="Cash Back Card-5678 (5678)")],
            "errors": [],
        }
        accounts = provider.list_accounts()
        assert accounts[0].last_four == "5678"

    def test_empty_accounts_list(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {"accounts": [], "errors": []}

        assert provider.list_accounts() == []


# ---------------------------------------------------------------------------
# Transaction parsing — sign convention
# ---------------------------------------------------------------------------


class TestParseTransaction:
    def _get_txns(self, provider, client, raw_acct):
        acct_id = raw_acct["id"]
        client.get_accounts.return_value = {"accounts": [raw_acct], "errors": []}
        return provider.list_transactions(acct_id)

    def test_negative_amount_preserved_as_expense(self):
        """SimpleFIN negative = expense; matches our convention — no inversion needed."""
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(amount="-50.00")])
        txns = self._get_txns(provider, client, acct)

        assert len(txns) == 1
        assert txns[0].amount == Decimal("-50.00")

    def test_positive_amount_preserved_as_credit(self):
        """SimpleFIN positive = credit/deposit; matches our convention."""
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(amount="100.00")])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].amount == Decimal("100.00")

    def test_date_from_posted_timestamp(self):
        provider, client = _make_provider()
        ts = _ts(date(2026, 3, 15))
        acct = _raw_account(transactions=[_raw_txn(posted=ts)])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].date == date(2026, 3, 15)

    def test_transacted_at_preferred_over_posted(self):
        """transacted_at (merchant time) takes priority over posted (settlement time)."""
        provider, client = _make_provider()
        ts_transacted = _ts(date(2026, 3, 10))
        ts_posted = _ts(date(2026, 3, 12))
        acct = _raw_account(transactions=[_raw_txn(transacted_at=ts_transacted, posted=ts_posted)])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].date == date(2026, 3, 10)

    def test_payee_stored_as_counterparty(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(payee="CVS Pharmacy")])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].details["counterparty"]["name"] == "CVS Pharmacy"

    def test_no_counterparty_when_payee_absent(self):
        provider, client = _make_provider()
        raw = _raw_txn()
        raw.pop("payee", None)
        acct = _raw_account(transactions=[raw])
        txns = self._get_txns(provider, client, acct)

        assert "counterparty" not in txns[0].details

    def test_description_used_as_description(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(description="Amazon.com")])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].description == "Amazon.com"

    def test_memo_stored_in_details_when_different_from_description(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(description="POS PURCHASE", memo="Starbucks #1234")])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].details.get("memo") == "Starbucks #1234"

    def test_memo_not_duplicated_when_same_as_description(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(description="Starbucks", memo="Starbucks")])
        txns = self._get_txns(provider, client, acct)

        assert "memo" not in txns[0].details

    def test_provider_name_set_on_transaction(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn()])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].provider == "simplefin"

    def test_status_is_posted_when_pending_absent(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn()])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].status == "posted"

    def test_status_is_posted_when_pending_false(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(pending=False)])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].status == "posted"

    def test_status_is_pending_when_pending_true(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[_raw_txn(pending=True, posted=0)])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].status == "pending"

    def test_transactions_sorted_newest_first(self):
        provider, client = _make_provider()
        acct = _raw_account(transactions=[
            _raw_txn(id="t1", posted=_ts(date(2026, 1, 1))),
            _raw_txn(id="t3", posted=_ts(date(2026, 3, 1))),
            _raw_txn(id="t2", posted=_ts(date(2026, 2, 1))),
        ])
        txns = self._get_txns(provider, client, acct)

        assert txns[0].id == "t3"
        assert txns[1].id == "t2"
        assert txns[2].id == "t1"

    def test_count_limits_returned_transactions(self):
        provider, client = _make_provider()
        raw_txns = [_raw_txn(id=f"t{i}", posted=_ts(date(2026, 1, i + 1))) for i in range(10)]
        acct = _raw_account(transactions=raw_txns)
        acct_id = acct["id"]
        client.get_accounts.return_value = {"accounts": [acct], "errors": []}

        txns = provider.list_transactions(acct_id, count=3)
        assert len(txns) == 3

    def test_unknown_account_returns_empty_list(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {"accounts": [_raw_account()], "errors": []}

        txns = provider.list_transactions("https://bridge.simplefin.org/unknown")
        assert txns == []


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------


class TestGetBalance:
    def test_returns_ledger_and_available_balance(self):
        provider, client = _make_provider()
        acct_id = "https://bridge.simplefin.org/simplefin/accounts/acct001"
        client.get_accounts.return_value = {
            "accounts": [_raw_account(id=acct_id, balance="1000.00", **{"available-balance": "900.00"})],
            "errors": [],
        }

        balance = provider.get_balance(acct_id)

        assert isinstance(balance, ExternalBalance)
        assert balance.ledger == Decimal("1000.00")
        assert balance.available == Decimal("900.00")
        assert balance.currency == "USD"

    def test_missing_available_balance_is_none(self):
        provider, client = _make_provider()
        acct_id = "https://bridge.simplefin.org/simplefin/accounts/acct001"
        raw = _raw_account(id=acct_id)
        raw.pop("available-balance", None)
        client.get_accounts.return_value = {"accounts": [raw], "errors": []}

        balance = provider.get_balance(acct_id)
        assert balance.available is None

    def test_not_found_raises_value_error(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {
            "accounts": [_raw_account(id="https://bridge.simplefin.org/other")],
            "errors": [],
        }

        with pytest.raises(ValueError, match="not found"):
            provider.get_balance("https://bridge.simplefin.org/missing")


# ---------------------------------------------------------------------------
# Bulk methods — fetch_all / parse_*
# ---------------------------------------------------------------------------


class TestBulkMethods:
    def test_fetch_all_returns_raw_response(self):
        provider, client = _make_provider()
        payload = {"accounts": [_raw_account()], "errors": []}
        client.get_accounts.return_value = payload

        result = provider.fetch_all()

        assert result is payload
        client.get_accounts.assert_called_once_with(start_date=None)

    def test_fetch_all_passes_start_date(self):
        provider, client = _make_provider()
        client.get_accounts.return_value = {"accounts": [], "errors": []}

        provider.fetch_all(start_date=date(2026, 6, 1))

        client.get_accounts.assert_called_once_with(start_date=date(2026, 6, 1))

    def test_parse_accounts_from_prefetched_data(self):
        provider, client = _make_provider()
        data = {
            "accounts": [
                _raw_account(id="acct1", name="Checking (1234)"),
                _raw_account(id="acct2", name="Savings (5678)"),
            ],
            "errors": [],
        }

        accounts = provider.parse_accounts(data)

        assert len(accounts) == 2
        assert accounts[0].id == "acct1"
        assert accounts[1].id == "acct2"
        client.get_accounts.assert_not_called()

    def test_parse_balance_from_prefetched_data(self):
        provider, client = _make_provider()
        data = {
            "accounts": [
                _raw_account(id="acct1", balance="500.00", **{"available-balance": "450.00"}),
                _raw_account(id="acct2", balance="1000.00"),
            ],
            "errors": [],
        }

        bal = provider.parse_balance(data, "acct1")

        assert bal.ledger == Decimal("500.00")
        assert bal.available == Decimal("450.00")
        client.get_accounts.assert_not_called()

    def test_parse_transactions_from_prefetched_data(self):
        provider, client = _make_provider()
        data = {
            "accounts": [
                _raw_account(
                    id="acct1",
                    transactions=[
                        _raw_txn(id="t1", posted=_ts(date(2026, 7, 10))),
                        _raw_txn(id="t2", posted=_ts(date(2026, 7, 12))),
                    ],
                ),
                _raw_account(
                    id="acct2",
                    transactions=[_raw_txn(id="t3", posted=_ts(date(2026, 7, 11)))],
                ),
            ],
            "errors": [],
        }

        txns = provider.parse_transactions(data, "acct1")

        assert len(txns) == 2
        assert txns[0].id == "t2"  # newest first
        assert txns[1].id == "t1"
        client.get_accounts.assert_not_called()

    def test_parse_transactions_unknown_account_returns_empty(self):
        provider, client = _make_provider()
        data = {"accounts": [_raw_account(id="acct1")], "errors": []}

        assert provider.parse_transactions(data, "missing") == []

    def test_parse_transactions_respects_count(self):
        provider, client = _make_provider()
        raw_txns = [_raw_txn(id=f"t{i}", posted=_ts(date(2026, 1, i + 1))) for i in range(10)]
        data = {"accounts": [_raw_account(id="acct1", transactions=raw_txns)], "errors": []}

        txns = provider.parse_transactions(data, "acct1", count=3)
        assert len(txns) == 3

    def test_parse_transactions_includes_pending(self):
        provider, client = _make_provider()
        data = {
            "accounts": [
                _raw_account(
                    id="acct1",
                    transactions=[
                        _raw_txn(id="t1", posted=_ts(date(2026, 7, 10))),
                        _raw_txn(id="t2", pending=True, posted=0, transacted_at=_ts(date(2026, 7, 12))),
                    ],
                ),
            ],
            "errors": [],
        }

        txns = provider.parse_transactions(data, "acct1")

        assert len(txns) == 2
        posted = next(t for t in txns if t.id == "t1")
        pending = next(t for t in txns if t.id == "t2")
        assert posted.status == "posted"
        assert pending.status == "pending"
