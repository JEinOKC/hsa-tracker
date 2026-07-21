"""SimpleFIN Bridge implementation of BankProvider.

Sign convention:
  SimpleFIN uses the same convention as this app:
    - negative amounts = expenses/debits
    - positive amounts = credits/deposits
  No sign inversion is needed (unlike the old Sophtron integration).

Dates:
  SimpleFIN returns Unix timestamps for balance-date and transaction
  posted/transacted_at fields.  We convert them to date objects here.
"""

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from app.providers.base import (
    BankProvider,
    ExternalAccount,
    ExternalBalance,
    ExternalTransaction,
)
from app.providers.simplefin.client import SimpleFINClient


class SimpleFINProvider(BankProvider):
    PROVIDER_NAME = "simplefin"

    def __init__(self, client: SimpleFINClient):
        self._client = client

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    # ------------------------------------------------------------------
    # Bulk fetch — one API call for all accounts
    # ------------------------------------------------------------------

    def fetch_all(self, start_date: Optional[date] = None) -> dict:
        """Single API call returning the raw SimpleFIN response for all accounts."""
        return self._client.get_accounts(start_date=start_date)

    def parse_accounts(self, data: dict) -> list[ExternalAccount]:
        """Parse accounts from a pre-fetched API response."""
        return [self._parse_account(a) for a in data.get("accounts", [])]

    def parse_balance(self, data: dict, account_id: str) -> ExternalBalance:
        """Extract one account's balance from a pre-fetched API response."""
        for acct in data.get("accounts", []):
            if acct.get("id") == account_id:
                ledger = Decimal(str(acct.get("balance") or 0))
                avail_raw = acct.get("available-balance")
                available = Decimal(str(avail_raw)) if avail_raw is not None else None
                return ExternalBalance(
                    account_id=account_id,
                    ledger=ledger,
                    currency=acct.get("currency", "USD"),
                    available=available,
                )
        raise ValueError(f"Account {account_id} not found.")

    def parse_transactions(
        self,
        data: dict,
        account_id: str,
        count: int = 100,
    ) -> list[ExternalTransaction]:
        """Extract one account's transactions from a pre-fetched API response."""
        for acct in data.get("accounts", []):
            if acct.get("id") == account_id:
                raw_txns = acct.get("transactions", [])
                txns = [self._parse_transaction(t, account_id) for t in raw_txns]
                txns.sort(key=lambda t: t.date, reverse=True)
                return txns[:count]
        return []

    # ------------------------------------------------------------------
    # BankProvider interface — single-account convenience methods
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[ExternalAccount]:
        """Return all accounts accessible via this Access URL."""
        return self.parse_accounts(self.fetch_all())

    def get_account(self, account_id: str) -> ExternalAccount:
        for a in self.list_accounts():
            if a.id == account_id:
                return a
        raise ValueError(f"Account {account_id} not found in SimpleFIN response.")

    def get_balance(self, account_id: str) -> ExternalBalance:
        return self.parse_balance(self.fetch_all(), account_id)

    def list_transactions(
        self,
        account_id: str,
        from_date: Optional[date] = None,
        count: int = 100,
    ) -> list[ExternalTransaction]:
        """Fetch transactions for a single account.

        SimpleFIN returns all accounts + their transactions in one response,
        so we request everything and filter to the relevant account here.
        """
        return self.parse_transactions(
            self.fetch_all(start_date=from_date), account_id, count
        )

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    def _parse_account(self, data: dict) -> ExternalAccount:
        org = data.get("org") or {}
        institution_name = org.get("name") or org.get("domain") or ""

        # SimpleFIN account IDs are URLs; we store them as-is.
        acct_id = str(data.get("id") or "")
        name = data.get("name") or "Account"

        # Parse last4 from account names like "My Credit Card (4321)"
        last_four_match = re.search(r'\((\d{3,4})\)\s*$', name)
        last_four = last_four_match.group(1).zfill(4) if last_four_match else None

        return ExternalAccount(
            id=acct_id,
            name=name,
            type="depository",
            subtype="checking",
            currency=data.get("currency", "USD"),
            institution_name=institution_name,
            provider=self.PROVIDER_NAME,
            last_four=last_four,
        )

    def _parse_transaction(self, data: dict, account_id: str) -> ExternalTransaction:
        txn_id = str(data.get("id") or "")

        # Prefer transacted_at (merchant time) over posted (settlement time)
        ts = data.get("transacted_at") or data.get("posted") or 0
        try:
            txn_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        except (ValueError, TypeError, OSError):
            txn_date = date.today()

        # SimpleFIN sign convention matches ours: negative = expense, positive = credit.
        amount = Decimal(str(data.get("amount") or 0))

        description = data.get("description") or data.get("memo") or ""
        payee = data.get("payee") or ""
        memo = data.get("memo") or ""

        details: dict = {}
        if payee:
            details["counterparty"] = {"name": payee}
        if memo and memo != description:
            details["memo"] = memo

        status = "pending" if data.get("pending") else "posted"

        return ExternalTransaction(
            id=txn_id,
            account_id=account_id,
            date=txn_date,
            description=description,
            amount=amount,
            type="",
            status=status,
            provider=self.PROVIDER_NAME,
            details=details,
        )
