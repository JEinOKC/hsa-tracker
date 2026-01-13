"""User Pydantic schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, UUID4


class UserBase(BaseModel):
    """Base user schema - passkey-first design"""

    username: str  # Primary identifier (required for passkey-only)
    display_name: str
    email: Optional[EmailStr] = None  # Optional - not required for passkey-only auth


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: Optional[str] = None  # Optional for passkey-only users


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    display_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserInDB(UserBase):
    """User schema as stored in database"""

    id: UUID4
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class User(UserInDB):
    """User schema for API responses"""

    pass
