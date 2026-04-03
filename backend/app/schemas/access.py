"""Pydantic schemas for role-based account access"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class AccountRoleCreate(BaseModel):
    name: str
    # Transactions
    can_read_transactions: bool = True
    can_write_transactions: bool = False
    can_delete_transactions: bool = False
    # Bank accounts
    can_read_bank_accounts: bool = True
    can_write_bank_accounts: bool = False
    can_delete_bank_accounts: bool = False
    # Documents
    can_read_documents: bool = True
    can_write_documents: bool = False
    can_delete_documents: bool = False
    # Family members
    can_read_family_members: bool = True
    can_write_family_members: bool = False
    can_delete_family_members: bool = False


class AccountRoleUpdate(AccountRoleCreate):
    pass


class AccountRoleResponse(AccountRoleCreate):
    id: UUID
    owner_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AccessGrantRequest(BaseModel):
    username: str
    role_id: UUID


class AccessResponse(BaseModel):
    id: UUID
    sub_user_id: UUID
    sub_username: str
    sub_display_name: str
    role: AccountRoleResponse
    granted_at: datetime

    model_config = {"from_attributes": True}


class MyAccessResponse(BaseModel):
    owner_user_id: UUID
    owner_username: str
    owner_display_name: str
    role: AccountRoleResponse
    granted_at: datetime

    model_config = {"from_attributes": True}
