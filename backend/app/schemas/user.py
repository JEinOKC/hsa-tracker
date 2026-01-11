"""User Pydantic schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, UUID4


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    display_name: str


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: str


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
