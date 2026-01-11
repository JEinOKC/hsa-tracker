"""Passkey-only authentication endpoints - WebAuthn implementation"""

import uuid
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserPasskey
from app.schemas.auth import (
    PasskeyRegisterStartRequest,
    PasskeyRegisterCompleteRequest,
    PasskeyLoginStartRequest,
    PasskeyLoginCompleteRequest,
    TokenResponse,
)
from app.schemas.user import User as UserSchema
from app.utils.security import create_access_token, create_refresh_token
from app.utils.webauthn import (
    generate_challenge,
    create_registration_options,
    verify_registration_credential,
    create_authentication_options,
    verify_authentication_credential,
    bytes_to_base64url,
    base64url_to_bytes,
)
from app.config import settings

router = APIRouter()

# In-memory challenge storage (in production, use Redis or database)
# Format: {username: {challenge: bytes, expires_at: datetime}}
_challenges = {}


@router.post("/register/start", status_code=200)
async def passkey_register_start(
    request: PasskeyRegisterStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start passkey registration - Step 1 of 2

    This endpoint:
    1. Checks if username is available
    2. Generates WebAuthn registration options
    3. Returns challenge and options for browser to create passkey

    No email or password required!
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Generate a temporary user ID for registration
    temp_user_id = uuid.uuid4().bytes

    # Generate WebAuthn registration options
    challenge = generate_challenge()
    options = create_registration_options(
        username=request.username,
        display_name=request.display_name,
        user_id=temp_user_id
    )

    # Store challenge temporarily (with temp_user_id for verification)
    _challenges[request.username] = {
        "challenge": challenge,
        "type": "registration",
        "temp_user_id": temp_user_id,
        "display_name": request.display_name,
        "created_at": datetime.utcnow()
    }

    # Update options with our challenge (base64url encoded)
    options["challenge"] = bytes_to_base64url(challenge)

    return {
        "options": options,
        "username": request.username
    }


@router.post("/register/complete", status_code=201, response_model=UserSchema)
async def passkey_register_complete(
    request: PasskeyRegisterCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Complete passkey registration - Step 2 of 2

    This endpoint:
    1. Verifies the passkey credential from the browser
    2. Creates the user account (NO password stored!)
    3. Stores the passkey credential
    4. Returns the created user

    After this, user can login with just their passkey!
    """
    # Get stored challenge
    challenge_data = _challenges.get(request.username)
    if not challenge_data or challenge_data.get("type") != "registration":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired registration session"
        )

    # Verify the credential
    try:
        verified = verify_registration_credential(
            credential=request.credential,
            expected_challenge=challenge_data["challenge"],
            expected_origin=settings.WEBAUTHN_ORIGIN
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Passkey verification failed: {str(e)}"
        )

    # Create user account (NO PASSWORD!)
    user = User(
        username=request.username,
        display_name=challenge_data["display_name"],
        email=None,  # No email required for passkey-only
        hashed_password=None,  # No password!
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    db.flush()  # Get user.id before creating passkey

    # Store passkey credential
    passkey = UserPasskey(
        user_id=user.id,
        credential_id=verified["credential_id"],
        public_key=verified["public_key"],
        sign_count=verified["sign_count"],
        aaguid=verified.get("aaguid"),
        device_name=request.device_name or "Primary Device",
        created_at=datetime.utcnow(),
    )

    db.add(passkey)
    db.commit()
    db.refresh(user)

    # Clean up challenge
    _challenges.pop(request.username, None)

    return user


@router.post("/login/start", status_code=200)
async def passkey_login_start(
    request: PasskeyLoginStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start passkey login - Step 1 of 2

    This endpoint:
    1. Looks up user by username
    2. Gets their registered passkeys
    3. Generates authentication challenge
    4. Returns options for browser to authenticate with passkey
    """
    # Find user
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Get user's passkeys
    passkeys = db.query(UserPasskey).filter(UserPasskey.user_id == user.id).all()
    if not passkeys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No passkeys registered for this account"
        )

    # Convert passkeys to dict format for webauthn utility
    credentials = [
        {
            "credential_id": pk.credential_id,
            "transports": pk.transports
        }
        for pk in passkeys
    ]

    # Generate authentication challenge
    challenge = generate_challenge()
    options = create_authentication_options(
        user_credentials=credentials,
        user_verification="required"
    )

    # Store challenge
    _challenges[request.username] = {
        "challenge": challenge,
        "type": "authentication",
        "user_id": str(user.id),
        "created_at": datetime.utcnow()
    }

    # Update options with our challenge
    options["challenge"] = bytes_to_base64url(challenge)

    return {
        "options": options,
        "username": request.username
    }


@router.post("/login/complete", status_code=200, response_model=TokenResponse)
async def passkey_login_complete(
    request: PasskeyLoginCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Complete passkey login - Step 2 of 2

    This endpoint:
    1. Verifies the passkey authentication from browser
    2. Issues JWT tokens
    3. Updates passkey usage timestamp

    User is now logged in!
    """
    # Get stored challenge
    challenge_data = _challenges.get(request.username)
    if not challenge_data or challenge_data.get("type") != "authentication":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired login session"
        )

    # Get user
    user_id = uuid.UUID(challenge_data["user_id"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Extract credential ID from response
    credential_response = request.credential
    raw_id = credential_response.get("rawId") or credential_response.get("id")

    # Find the passkey in database
    passkey = db.query(UserPasskey).filter(
        UserPasskey.user_id == user.id,
        UserPasskey.credential_id == raw_id
    ).first()

    if not passkey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passkey not found for this user"
        )

    # Verify the authentication
    try:
        verified = verify_authentication_credential(
            credential=request.credential,
            expected_challenge=challenge_data["challenge"],
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey verification failed: {str(e)}"
        )

    # Update passkey usage
    passkey.sign_count = verified["new_sign_count"]
    passkey.last_used_at = datetime.utcnow()
    db.commit()

    # Clean up challenge
    _challenges.pop(request.username, None)

    # Create tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
