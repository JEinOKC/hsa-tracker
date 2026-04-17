"""Tests for TellerProvider.list_transactions cursor pagination."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.providers.teller.provider import TellerProvider


def _make_raw_txn(txn_id: str, txn_date: str) -> dict:
    return {
        "id": txn_id,
        "date": txn_date,
        "description": f"Txn {txn_id}",
        "amount": "10.00",
        "type": "card_payment",
        "status": "posted",
        "details": {"category": "health"},
    }


def _make_provider() -> tuple[TellerProvider, MagicMock]:
    mock_client = MagicMock()
    provider = TellerProvider(client=mock_client)
    return provider, mock_client


class TestListTransactionsPagination:
    def test_single_page_no_cursor(self):
        """Short first page → one request, no from_id cursor used."""
        provider, mock_client = _make_provider()
        page = [_make_raw_txn(f"t{i}", "2026-01-01") for i in range(3)]
        mock_client.get.return_value = page

        result = provider.list_transactions("acct_1", count=500)

        mock_client.get.assert_called_once()
        call_params = mock_client.get.call_args[1]["params"]
        assert "from_id" not in call_params
        assert len(result) == 3

    def test_paginates_multiple_pages(self):
        """Two full pages + one short page → three requests, cursors used correctly."""
        provider, mock_client = _make_provider()
        page_size = 3
        page1 = [_make_raw_txn(f"t{i}", "2026-03-01") for i in range(page_size)]
        page2 = [_make_raw_txn(f"t{i}", "2026-02-01") for i in range(page_size, page_size * 2)]
        page3 = [_make_raw_txn(f"t{i}", "2026-01-01") for i in range(page_size * 2, page_size * 2 + 1)]
        mock_client.get.side_effect = [page1, page2, page3]

        result = provider.list_transactions("acct_1", count=page_size)

        assert mock_client.get.call_count == 3
        # Second call uses last id of page1 as cursor
        second_call_params = mock_client.get.call_args_list[1][1]["params"]
        assert second_call_params["from_id"] == page1[-1]["id"]
        # Third call uses last id of page2 as cursor
        third_call_params = mock_client.get.call_args_list[2][1]["params"]
        assert third_call_params["from_id"] == page2[-1]["id"]
        assert len(result) == page_size * 2 + 1

    def test_stops_at_from_date(self):
        """Page spanning from_date → only transactions on/after from_date returned, loop exits."""
        provider, mock_client = _make_provider()
        cutoff = date(2026, 2, 1)
        page = [
            _make_raw_txn("t1", "2026-03-01"),
            _make_raw_txn("t2", "2026-02-01"),
            _make_raw_txn("t3", "2026-01-15"),  # before cutoff — should stop here
            _make_raw_txn("t4", "2025-12-01"),
        ]
        mock_client.get.return_value = page

        result = provider.list_transactions("acct_1", from_date=cutoff, count=500)

        mock_client.get.assert_called_once()
        assert len(result) == 2
        assert all(r.date >= cutoff for r in result)

    def test_empty_first_response(self):
        """Teller returns empty list → returns empty, no cursor loop."""
        provider, mock_client = _make_provider()
        mock_client.get.return_value = []

        result = provider.list_transactions("acct_1")

        mock_client.get.assert_called_once()
        assert result == []

    def test_from_date_entire_page_qualifies(self):
        """All transactions in page are after from_date → full page kept, loop continues."""
        provider, mock_client = _make_provider()
        cutoff = date(2025, 1, 1)
        page1 = [_make_raw_txn(f"t{i}", "2026-01-01") for i in range(3)]
        page2 = [_make_raw_txn(f"t{i}", "2025-06-01") for i in range(3, 5)]  # short page
        mock_client.get.side_effect = [page1, page2]

        result = provider.list_transactions("acct_1", from_date=cutoff, count=3)

        assert mock_client.get.call_count == 2
        assert len(result) == 5
