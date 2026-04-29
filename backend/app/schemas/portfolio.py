"""Pydantic schemas for portfolio endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


# ─── Holdings ────────────────────────────────────────────────────────────────

class HsaHoldingCreate(BaseModel):
    ticker: str
    shares: Decimal


class HsaHoldingUpdate(BaseModel):
    ticker: Optional[str] = None
    shares: Optional[Decimal] = None
    last_known_price: Optional[Decimal] = None


class HsaHoldingOut(BaseModel):
    id: UUID
    account_id: UUID
    ticker: str
    shares: Decimal
    last_known_price: Optional[Decimal] = None
    last_price_fetched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Accounts ────────────────────────────────────────────────────────────────

AccountType = Literal["contribution", "investment", "both"]


class HsaAccountCreate(BaseModel):
    institution_name: str
    nickname: Optional[str] = None
    account_type: AccountType = "both"
    cash_balance: Optional[Decimal] = None


class HsaAccountUpdate(BaseModel):
    institution_name: Optional[str] = None
    nickname: Optional[str] = None
    account_type: Optional[AccountType] = None
    is_active: Optional[bool] = None
    cash_balance: Optional[Decimal] = None


class HsaAccountOut(BaseModel):
    id: UUID
    user_id: UUID
    institution_name: str
    nickname: Optional[str] = None
    account_type: str
    is_active: bool
    cash_balance: Optional[Decimal] = None
    cash_balance_updated_at: Optional[datetime] = None
    last_checkin_at: Optional[datetime] = None
    holdings: List[HsaHoldingOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Summary ─────────────────────────────────────────────────────────────────

class AccountSummary(BaseModel):
    account_id: UUID
    institution_name: str
    nickname: Optional[str] = None
    cash_balance: Optional[Decimal] = None
    invested_value: Optional[Decimal] = None  # sum(shares * last_known_price)
    total_value: Optional[Decimal] = None     # cash_balance + invested_value
    holdings_count: int
    last_checkin_at: Optional[datetime] = None


class PortfolioSummaryOut(BaseModel):
    accounts: List[AccountSummary]
    total_value: Optional[Decimal] = None


# ─── Holding snapshots / history ─────────────────────────────────────────────

class HoldingSnapshotOut(BaseModel):
    id: UUID
    holding_id: Optional[UUID] = None
    account_id: UUID
    ticker: str
    shares: Decimal
    price: Decimal
    value: Decimal
    snapshotted_at: datetime

    class Config:
        from_attributes = True


class PortfolioHistoryPoint(BaseModel):
    date: str          # "YYYY-MM-DD"
    total_value: Decimal


class PortfolioHistoryOut(BaseModel):
    points: List[PortfolioHistoryPoint]


# ─── Projection ──────────────────────────────────────────────────────────────

class ProjectionPoint(BaseModel):
    year: int
    value: Decimal


class ProjectionOut(BaseModel):
    starting_value: Decimal
    annual_return: float
    points: List[ProjectionPoint]
