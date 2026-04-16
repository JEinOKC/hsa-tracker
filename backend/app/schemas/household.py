"""Pydantic schemas for household endpoints."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class HouseholdRoleCreate(BaseModel):
    name: str
    can_read_transactions: bool = True
    can_write_transactions: bool = False
    can_delete_transactions: bool = False
    can_read_bank_accounts: bool = True
    can_write_bank_accounts: bool = False
    can_delete_bank_accounts: bool = False
    can_read_documents: bool = True
    can_write_documents: bool = False
    can_delete_documents: bool = False
    can_read_family_members: bool = True
    can_write_family_members: bool = False
    can_delete_family_members: bool = False


class HouseholdRoleUpdate(BaseModel):
    name: Optional[str] = None
    can_read_transactions: Optional[bool] = None
    can_write_transactions: Optional[bool] = None
    can_delete_transactions: Optional[bool] = None
    can_read_bank_accounts: Optional[bool] = None
    can_write_bank_accounts: Optional[bool] = None
    can_delete_bank_accounts: Optional[bool] = None
    can_read_documents: Optional[bool] = None
    can_write_documents: Optional[bool] = None
    can_delete_documents: Optional[bool] = None
    can_read_family_members: Optional[bool] = None
    can_write_family_members: Optional[bool] = None
    can_delete_family_members: Optional[bool] = None


class HouseholdRoleOut(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    can_read_transactions: bool
    can_write_transactions: bool
    can_delete_transactions: bool
    can_read_bank_accounts: bool
    can_write_bank_accounts: bool
    can_delete_bank_accounts: bool
    can_read_documents: bool
    can_write_documents: bool
    can_delete_documents: bool
    can_read_family_members: bool
    can_write_family_members: bool
    can_delete_family_members: bool
    created_at: datetime

    class Config:
        from_attributes = True


class HouseholdMemberOut(BaseModel):
    id: UUID
    household_id: UUID
    user_id: UUID
    username: str
    display_name: str
    role: HouseholdRoleOut
    is_admin: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class HouseholdOut(BaseModel):
    id: UUID
    name: str
    created_by_id: UUID
    created_at: datetime
    strict_eligibility: bool = True

    class Config:
        from_attributes = True


class HouseholdSettingsUpdate(BaseModel):
    strict_eligibility: bool


class HouseholdDetailOut(BaseModel):
    household: HouseholdOut
    roles: List[HouseholdRoleOut]
    members: List[HouseholdMemberOut]
    is_admin: bool = False


class CreateHouseholdRequest(BaseModel):
    name: str


class TransferAdminRequest(BaseModel):
    stay_as_role_id: Optional[UUID] = None
