"""Authentication Pydantic schemas"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr


# Registration & Login
class RegisterRequest(BaseModel):
    """User registration request"""

    email: EmailStr
    password: str
    display_name: str


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
