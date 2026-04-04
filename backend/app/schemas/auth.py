"""Authentication Pydantic schemas"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


def _validate_password_strength(password: str) -> str:
    """
    Enforce minimum password strength.

    Rules:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not any(c in r"!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        raise ValueError("Password must contain at least one special character")
    return password


# Passkey-Only Registration & Login
class PasskeyRegisterStartRequest(BaseModel):
    """Start passkey-only registration (no email, no password)"""

    username: str  # Unique username identifier
    display_name: str  # Full name for display
    invite_token: Optional[str] = None  # Required when REQUIRE_INVITE=true or using a family invite link
    family_pin: Optional[str] = None  # Required when invite is a FamilyInvite with require_pin=True

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Username must be 50 characters or fewer")
        import re
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError("Username may only contain letters, digits, hyphens, underscores, and dots")
        return v

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Display name must not be empty")
        if len(v) > 100:
            raise ValueError("Display name must be 100 characters or fewer")
        return v


class PasskeyRegisterCompleteRequest(BaseModel):
    """Complete passkey registration"""

    username: str
    credential: dict  # WebAuthn credential from browser
    device_name: Optional[str] = None  # Optional friendly name


class PasskeyLoginStartRequest(BaseModel):
    """Start passkey login"""

    username: str  # Username to authenticate


class PasskeyLoginCompleteRequest(BaseModel):
    """Complete passkey login"""

    username: str
    credential: dict  # WebAuthn assertion from browser


# Legacy Email/Password Registration & Login (deprecated in favor of passkey-only)
class RegisterRequest(BaseModel):
    """User registration request (legacy - use passkey instead)"""

    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Display name must not be empty")
        if len(v) > 100:
            raise ValueError("Display name must be 100 characters or fewer")
        return v


class LoginRequest(BaseModel):
    """Email/password login request"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str


# WebAuthn / Passkey
class PasskeyRegistrationOptions(BaseModel):
    """WebAuthn registration options"""

    challenge: str
    rp: dict
    user: dict
    pubKeyCredParams: List[dict]
    timeout: int
    attestation: str


class PasskeyRegistrationVerification(BaseModel):
    """WebAuthn registration verification request"""

    credential: dict
    device_name: Optional[str] = None


class PasskeyAuthenticationOptions(BaseModel):
    """WebAuthn authentication options"""

    challenge: str
    rpId: str
    timeout: int
    userVerification: str
    allowCredentials: List[dict]


class PasskeyAuthenticationVerification(BaseModel):
    """WebAuthn authentication verification request"""

    credential: dict


# TOTP (2FA)
class TOTPSetupResponse(BaseModel):
    """TOTP setup response with QR code"""

    secret: str
    qr_code_url: str
    backup_codes: List[str]


class TOTPVerifyRequest(BaseModel):
    """TOTP verification request"""

    code: str


class TOTPLoginRequest(BaseModel):
    """Login with TOTP after password"""

    email: EmailStr
    password: str
    totp_code: str


class BackupCodeVerifyRequest(BaseModel):
    """Backup code verification request"""

    code: str


# Password Management
class ChangePasswordRequest(BaseModel):
    """Change password request"""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ResetPasswordRequest(BaseModel):
    """Reset password request (future feature)"""

    email: EmailStr


# Account Info
class AccountSecurityInfo(BaseModel):
    """User's security settings info"""

    has_password: bool
    has_totp: bool
    totp_verified: bool
    passkey_count: int
    backup_codes_remaining: int
