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
        # Teller paginates via cursor; loop until from_date reached or last page
        all_transactions: list[ExternalTransaction] = []
        page_size = min(count, 500)
        from_id: Optional[str] = None

        while True:
            params: dict = {"count": page_size}
            if from_id:
                params["from_id"] = from_id

            data = self._client.get(
                f"/accounts/{account_id}/transactions",
                params=params,
            )
            if not data:
                break

            page_txns = [self._parse_transaction(t, account_id) for t in data]

            if from_date:
                for t in page_txns:
                    if t.date >= from_date:
                        all_transactions.append(t)
                    else:
                        return all_transactions  # Past the cutoff — done
            else:
                all_transactions.extend(page_txns)

            if len(data) < page_size:
                break  # Short page = end of history

            from_id = data[-1]["id"]  # Cursor for next page

        return all_transactions

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
