"""Authentication endpoints - Complete implementation with email/password, passkeys, and TOTP"""

from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
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

router = APIRouter()


# ===== Basic Email/Password Authentication =====

@router.post("/register", status_code=201, response_model=UserSchema)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with email and password"""
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user = User(
        email=request.email,
        display_name=request.display_name,
        hashed_password=hash_password(request.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.hashed_password or not verify_password(request.password, user.hashed_password):
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
async def totp_login(
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

    if not verify_totp_code(totp.secret, totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code"
        )

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
async def backup_code_verify(
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid backup code"
        )

    matched_code.used_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


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
