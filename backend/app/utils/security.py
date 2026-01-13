"""Security utilities for authentication"""

import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import jwt, JWTError
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO

from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


# JWT Tokens
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token (typically {"sub": user_id})
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Data to encode in the token (typically {"sub": user_id})

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


# TOTP (Time-based One-Time Password)
def generate_totp_secret() -> str:
    """Generate a random TOTP secret"""
    return pyotp.random_base32()


def generate_totp_qr_code(secret: str, email: str, issuer: str = None) -> str:
    """
    Generate a TOTP QR code as a data URL.

    Args:
        secret: TOTP secret
        email: User's email
        issuer: Issuer name (app name)

    Returns:
        QR code as SVG data URL
    """
    if issuer is None:
        issuer = settings.app_name

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name=issuer)

    # Generate QR code as SVG
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(uri, image_factory=factory)

    # Convert to string
    buffer = BytesIO()
    img.save(buffer)
    svg_str = buffer.getvalue().decode('utf-8')

    # Create data URL
    svg_b64 = base64.b64encode(svg_str.encode('utf-8')).decode('utf-8')
    data_url = f"data:image/svg+xml;base64,{svg_b64}"

    return data_url


def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify a TOTP code.

    Args:
        secret: TOTP secret
        code: Code to verify (6 digits)
        window: Number of time windows to check (default 1 = ±30 seconds)

    Returns:
        True if code is valid
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=window)


# Backup Codes
def generate_backup_codes(count: int = 10) -> list[str]:
    """
    Generate backup codes for account recovery.

    Args:
        count: Number of backup codes to generate

    Returns:
        List of backup codes (e.g., "XXXX-XXXX-XXXX")
    """
    codes = []
    for _ in range(count):
        # Generate 12 character code with dashes
        code = secrets.token_hex(6).upper()  # 12 hex chars
        formatted = f"{code[0:4]}-{code[4:8]}-{code[8:12]}"
        codes.append(formatted)
    return codes


def hash_backup_code(code: str) -> str:
    """Hash a backup code (same as password hashing)"""
    return hash_password(code)


def verify_backup_code(plain_code: str, hashed_code: str) -> bool:
    """Verify a backup code against a hash"""
    return verify_password(plain_code, hashed_code)


# WebAuthn Challenge Generation
def generate_webauthn_challenge() -> bytes:
    """Generate a random challenge for WebAuthn"""
    return secrets.token_bytes(32)


def encode_webauthn_challenge(challenge: bytes) -> str:
    """Encode WebAuthn challenge as base64"""
    return base64.urlsafe_b64encode(challenge).decode('utf-8').rstrip('=')


def decode_webauthn_challenge(challenge_str: str) -> bytes:
    """Decode WebAuthn challenge from base64"""
    # Add padding if necessary
    padding = 4 - (len(challenge_str) % 4)
    if padding != 4:
        challenge_str += '=' * padding
    return base64.urlsafe_b64decode(challenge_str)
