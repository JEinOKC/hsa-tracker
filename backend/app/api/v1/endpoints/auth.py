"""Authentication endpoints - Complete implementation with email/password, passkeys, and TOTP"""

import re
import uuid as uuid_mod
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from coolname import generate_slug
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserPasskey, UserTOTP, UserBackupCode
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    ChangePasswordRequest,
    AccountSecurityInfo,
)
from app.schemas.user import User as UserSchema
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    generate_totp_qr_code,
    verify_totp_code,
    generate_backup_codes,
    hash_backup_code,
    verify_backup_code,
)
from app.config import settings
from app.utils.rate_limit import limiter

router = APIRouter()

# Number of consecutive failures before account is locked
_MAX_LOGIN_ATTEMPTS = 5
# How long the lockout lasts
_LOCKOUT_MINUTES = 15


def _check_and_enforce_lockout(user: "User") -> None:
    """Raise 403 if the account is currently locked."""
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to too many failed login attempts. Try again later.",
        )


def _record_failed_login(user: "User", db: "Session") -> None:
    """Increment failure counter; lock the account if the threshold is reached."""
    from datetime import timedelta
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= _MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=_LOCKOUT_MINUTES)
    db.commit()


def _reset_failed_login(user: "User", db: "Session") -> None:
    """Clear failure state after a successful login."""
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()


# ===== Basic Email/Password Authentication =====

@router.post("/register", status_code=201, response_model=UserSchema)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with email and password"""
    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Derive a unique username from the email address (legacy endpoint has no passkey)
    email_prefix = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", body.email.split("@")[0])[:40]
    username = email_prefix
    while db.query(User).filter(User.username == username).first():
        username = f"{email_prefix}_{uuid_mod.uuid4().hex[:6]}"

    user = User(
        username=username,
        email=body.email,
        display_name=body.display_name,
        hashed_password=hash_password(body.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    _check_and_enforce_lockout(user)

    if not user.hashed_password or not verify_password(body.password, user.hashed_password):
        _record_failed_login(user, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if TOTP is required
    totp = db.query(UserTOTP).filter(
        UserTOTP.user_id == user.id,
        UserTOTP.is_verified == True
    ).first()

    if totp:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP verification required",
            headers={"X-TOTP-Required": "true"},
        )

    _reset_failed_login(user, db)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserSchema)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(data={"sub": str(user.id)}),
        refresh_token=create_refresh_token(data={"sub": str(user.id)}),
        token_type="bearer",
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout current user"""
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    if not current_user.hashed_password or not verify_password(
        request.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    current_user.hashed_password = hash_password(request.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


# ===== TOTP (2FA) Authentication =====

@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set up TOTP (2FA) for the current user"""
    existing_totp = db.query(UserTOTP).filter(UserTOTP.user_id == current_user.id).first()
    if existing_totp and existing_totp.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP already set up. Disable it first to set up again."
        )

    secret = generate_totp_secret()
    qr_code_url = generate_totp_qr_code(secret, current_user.email, settings.app_name)
    backup_codes = generate_backup_codes(10)

    if existing_totp:
        existing_totp.secret = secret
        existing_totp.is_verified = False
        existing_totp.verified_at = None
    else:
        totp = UserTOTP(
            user_id=current_user.id,
            secret=secret,
            is_verified=False,
        )
        db.add(totp)

    db.query(UserBackupCode).filter(UserBackupCode.user_id == current_user.id).delete()

    for code in backup_codes:
        backup_code = UserBackupCode(
            user_id=current_user.id,
            code_hash=hash_backup_code(code),
        )
        db.add(backup_code)

    db.commit()

    return TOTPSetupResponse(
        secret=secret,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes,
    )


@router.post("/totp/verify")
async def totp_verify(
    request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify TOTP setup and activate 2FA"""
    totp = db.query(UserTOTP).filter(UserTOTP.user_id == current_user.id).first()
    if not totp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not set up. Call /totp/setup first."
        )

    if not verify_totp_code(totp.secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code"
        )

    totp.is_verified = True
    totp.verified_at = datetime.utcnow()
    db.commit()

    return {"message": "TOTP verified and activated successfully"}


@router.post("/totp/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def totp_login(
    request: Request,
    email: str,
    password: str,
    totp_code: str,
    db: Session = Depends(get_db)
):
    """Login with email, password, and TOTP code"""
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    totp = db.query(UserTOTP).filter(
        UserTOTP.user_id == user.id,
        UserTOTP.is_verified == True
    ).first()

    if not totp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not enabled for this account"
        )

    _check_and_enforce_lockout(user)

    # Replay prevention: reject a code that was already used in this window
    if totp.last_used_code == totp_code and totp.last_used_at:
        from datetime import timedelta
        if datetime.utcnow() - totp.last_used_at < timedelta(seconds=30):
            _record_failed_login(user, db)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TOTP code has already been used",
            )

    if not verify_totp_code(totp.secret, totp_code):
        _record_failed_login(user, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code"
        )

    totp.last_used_code = totp_code
    totp.last_used_at = datetime.utcnow()
    _reset_failed_login(user, db)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/totp/disable")
async def totp_disable(
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable TOTP (2FA) for the current user"""
    if not current_user.hashed_password or not verify_password(password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )

    db.query(UserTOTP).filter(UserTOTP.user_id == current_user.id).delete()
    db.query(UserBackupCode).filter(UserBackupCode.user_id == current_user.id).delete()
    db.commit()

    return {"message": "TOTP disabled successfully"}


@router.post("/backup-code/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
async def backup_code_verify(
    request: Request,
    email: str,
    password: str,
    backup_code: str,
    db: Session = Depends(get_db)
):
    """Login using a backup code when TOTP is unavailable"""
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    _check_and_enforce_lockout(user)

    backup_codes = db.query(UserBackupCode).filter(
        UserBackupCode.user_id == user.id,
        UserBackupCode.used_at == None
    ).all()

    if not backup_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No backup codes available"
        )

    matched_code = None
    for bc in backup_codes:
        if verify_backup_code(backup_code, bc.code_hash):
            matched_code = bc
            break

    if not matched_code:
        _record_failed_login(user, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid backup code"
        )

    matched_code.used_at = datetime.utcnow()
    _reset_failed_login(user, db)
    db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


class FamilyPinResponse(BaseModel):
    pin: str


@router.get("/family-pin", response_model=FamilyPinResponse)
async def get_family_pin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's family PIN (plaintext, shareable household code).
    Auto-generates one on first access for accounts created before this feature."""
    if not current_user.family_pin:
        current_user.family_pin = generate_slug(2)
        db.commit()
    return FamilyPinResponse(pin=current_user.family_pin)


@router.post("/family-pin/reset", response_model=FamilyPinResponse)
async def reset_family_pin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new 2-word family PIN and save it. Returns the new PIN."""
    new_pin = generate_slug(2)
    current_user.family_pin = new_pin
    db.commit()
    return FamilyPinResponse(pin=new_pin)


@router.get("/security-info", response_model=AccountSecurityInfo)
async def get_security_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's security settings"""
    totp = db.query(UserTOTP).filter(UserTOTP.user_id == current_user.id).first()
    passkey_count = db.query(UserPasskey).filter(UserPasskey.user_id == current_user.id).count()
    backup_codes_remaining = db.query(UserBackupCode).filter(
        UserBackupCode.user_id == current_user.id,
        UserBackupCode.used_at == None
    ).count()

    return AccountSecurityInfo(
        has_password=bool(current_user.hashed_password),
        has_totp=bool(totp),
        totp_verified=totp.is_verified if totp else False,
        passkey_count=passkey_count,
        backup_codes_remaining=backup_codes_remaining,
    )
