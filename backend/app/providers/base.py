"""Abstract bank provider interface.

New providers (Plaid, OFX import, CSV, etc.) implement BankProvider.
The rest of the app only talks to BankProvider — never to a specific provider directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class ExternalAccount:
    id: str
    name: str
    type: str            # "depository", "credit"
    subtype: str         # "checking", "savings", "hsa", "credit_card", etc.
    currency: str
    institution_name: str
    provider: str
    last_four: Optional[str] = None


@dataclass
class ExternalBalance:
    account_id: str
    ledger: Decimal
    currency: str
    available: Optional[Decimal] = None


@dataclass
class ExternalTransaction:
    id: str
    account_id: str
    date: date
    description: str
    amount: Decimal      # negative = debit (expense), positive = credit/refund
    type: str
    status: str          # "posted" or "pending"
    provider: str
    details: dict = field(default_factory=dict)


class BankProvider(ABC):
    """Interface all bank data providers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string, e.g. 'teller'."""
        ...

    @abstractmethod
    def list_accounts(self) -> list[ExternalAccount]:
        ...

    @abstractmethod
    def get_account(self, account_id: str) -> ExternalAccount:
        ...

    @abstractmethod
    def get_balance(self, account_id: str) -> ExternalBalance:
        ...

    @abstractmethod
    def list_transactions(
        self,
        account_id: str,
        from_date: Optional[date] = None,
        count: int = 100,
    ) -> list[ExternalTransaction]:
        ...
