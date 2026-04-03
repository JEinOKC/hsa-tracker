"""User database models"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RegistrationToken(Base):
    """Single-use invite tokens for gated registration"""

    __tablename__ = "registration_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(255), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)  # e.g. "for alice"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_username = Column(String(255), nullable=True)

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def __repr__(self):
        return f"<RegistrationToken(token={self.token}, used={self.is_used})>"


class FamilyInvite(Base):
    """Short-lived invite links generated in-app for family member registration"""

    __tablename__ = "family_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(255), unique=True, nullable=False, index=True)  # 3-word coolname slug
    label = Column(String(255), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # default: now + 72 hours, set at creation
    used_at = Column(DateTime, nullable=True)
    used_by_username = Column(String(255), nullable=True)
    require_pin = Column(Boolean, default=True, nullable=False)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="SET NULL"), nullable=True)
    household_role_id = Column(UUID(as_uuid=True), ForeignKey("household_roles.id", ondelete="SET NULL"), nullable=True)
    family_member_id = Column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True)

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired

    def __repr__(self):
        return f"<FamilyInvite(token={self.token}, valid={self.is_valid})>"


class User(Base):
    """User account model - supports passkey-only authentication"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)  # Primary identifier for passkey auth
    email = Column(String(255), unique=True, nullable=True, index=True)  # Optional - not required for passkey-only
    hashed_password = Column(String(255), nullable=True)  # Nullable for passkey-only users
    display_name = Column(String(255), nullable=False)
    family_pin = Column(String(50), nullable=True)  # Plaintext 2-word phrase shared with family for invite verification
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    passkeys = relationship("UserPasskey", back_populates="user", cascade="all, delete-orphan")
    totp = relationship("UserTOTP", back_populates="user", uselist=False, cascade="all, delete-orphan")
    backup_codes = relationship("UserBackupCode", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class UserPasskey(Base):
    """WebAuthn passkey credentials"""

    __tablename__ = "user_passkeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # WebAuthn credential data
    credential_id = Column(String(1024), unique=True, nullable=False, index=True)  # Base64url encoded
    public_key = Column(Text, nullable=False)  # COSE-encoded public key
    sign_count = Column(Integer, default=0, nullable=False)  # Signature counter for security

    # Additional WebAuthn data
    aaguid = Column(String(255), nullable=True)  # Authenticator AAGUID
    transports = Column(String(255), nullable=True)  # JSON array of transport types (usb, nfc, ble, internal)

    # User-friendly metadata
    device_name = Column(String(255), nullable=True)  # User-assigned name (e.g., "iPhone", "YubiKey")

    # Timestamps
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
