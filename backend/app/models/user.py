"""User database models"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User account model"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for passkey-only users
    display_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    passkeys = relationship("UserPasskey", back_populates="user", cascade="all, delete-orphan")
    totp = relationship("UserTOTP", back_populates="user", uselist=False, cascade="all, delete-orphan")
    backup_codes = relationship("UserBackupCode", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class UserPasskey(Base):
    """WebAuthn passkey credentials"""

    __tablename__ = "user_passkeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    credential_id = Column(String(1024), unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0, nullable=False)
    device_name = Column(String(255), nullable=True)  # User-friendly name (e.g., "iPhone", "YubiKey")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="passkeys")

    def __repr__(self):
        return f"<UserPasskey(id={self.id}, user_id={self.user_id}, device={self.device_name})>"


class UserTOTP(Base):
    """TOTP (Time-based One-Time Password) 2FA configuration"""

    __tablename__ = "user_totp"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    secret = Column(String(255), nullable=False)  # Encrypted TOTP secret
    is_verified = Column(Boolean, default=False, nullable=False)  # True after first successful verification
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="totp")

    def __repr__(self):
        return f"<UserTOTP(id={self.id}, user_id={self.user_id}, verified={self.is_verified})>"


class UserBackupCode(Base):
    """Backup codes for account recovery"""

    __tablename__ = "user_backup_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String(255), nullable=False)  # Hashed backup code
    used_at = Column(DateTime, nullable=True)  # NULL if unused
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="backup_codes")

    def __repr__(self):
        return f"<UserBackupCode(id={self.id}, used={'yes' if self.used_at else 'no'})>"
