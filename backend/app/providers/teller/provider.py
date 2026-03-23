"""Teller.io implementation of BankProvider."""

from datetime import date
from decimal import Decimal
from typing import Optional

from app.providers.base import (
    BankProvider,
    ExternalAccount,
    ExternalBalance,
    ExternalTransaction,
)
from app.providers.teller.client import TellerClient


class TellerProvider(BankProvider):
    PROVIDER_NAME = "teller"

    def __init__(self, client: TellerClient):
        self._client = client

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    def list_accounts(self) -> list[ExternalAccount]:
        data = self._client.get("/accounts")
        return [self._parse_account(a) for a in data]

    def get_account(self, account_id: str) -> ExternalAccount:
        data = self._client.get(f"/accounts/{account_id}")
        return self._parse_account(data)

    def get_balance(self, account_id: str) -> ExternalBalance:
        data = self._client.get(f"/accounts/{account_id}/balances")
        return ExternalBalance(
            account_id=account_id,
            ledger=Decimal(str(data["ledger"])),
            currency=data.get("currency", "USD"),
            available=Decimal(str(data["available"])) if data.get("available") else None,
        )

    def list_transactions(
        self,
        account_id: str,
        from_date: Optional[date] = None,
        count: int = 100,
    ) -> list[ExternalTransaction]:
        # Teller paginates via cursor; count caps the request size
        data = self._client.get(
            f"/accounts/{account_id}/transactions",
            params={"count": min(count, 500)},
        )
        transactions = [self._parse_transaction(t, account_id) for t in data]

        # Filter client-side if a start date is requested
        if from_date:
            transactions = [t for t in transactions if t.date >= from_date]

        return transactions

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    def _parse_account(self, data: dict) -> ExternalAccount:
        return ExternalAccount(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            subtype=data["subtype"],
            currency=data.get("currency", "USD"),
            institution_name=data["institution"]["name"],
            provider=self.PROVIDER_NAME,
            last_four=data.get("last_four"),
        )

    def _parse_transaction(self, data: dict, account_id: str) -> ExternalTransaction:
        return ExternalTransaction(
            id=data["id"],
            account_id=account_id,
            date=date.fromisoformat(data["date"]),
            description=data.get("description", ""),
            amount=Decimal(str(data["amount"])),
            type=data.get("type", ""),
            status=data["status"],
            provider=self.PROVIDER_NAME,
            details=data.get("details", {}),
        )
