"""Passkey-only authentication endpoints - WebAuthn implementation"""

import uuid
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, status
from coolname import generate_slug
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.family import FamilyMember
from app.models.household import Household, HouseholdMembership, HouseholdRole
from app.models.user import User, UserPasskey, RegistrationToken, FamilyInvite, PasskeyChallenge
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
from webauthn.helpers.structs import UserVerificationRequirement
from app.config import settings
from app.utils.rate_limit import limiter

router = APIRouter()

_CHALLENGE_TTL_MINUTES = 10


def _save_challenge(db: Session, username: str, challenge: bytes, challenge_type: str, metadata: dict) -> None:
    """Persist a WebAuthn challenge to the database, replacing any existing one for this username."""
    db.query(PasskeyChallenge).filter(PasskeyChallenge.username == username).delete()
    db.add(PasskeyChallenge(
        username=username,
        challenge_b64=bytes_to_base64url(challenge),
        challenge_type=challenge_type,
        metadata_json=json.dumps(metadata),
        expires_at=datetime.utcnow() + timedelta(minutes=_CHALLENGE_TTL_MINUTES),
    ))
    db.flush()


def _consume_challenge(db: Session, username: str, challenge_type: str) -> dict:
    """Retrieve and delete a challenge row. Raises HTTPException if missing or expired."""
    row = (
        db.query(PasskeyChallenge)
        .filter(PasskeyChallenge.username == username, PasskeyChallenge.challenge_type == challenge_type)
        .first()
    )
    if not row or row.is_expired:
        db.query(PasskeyChallenge).filter(PasskeyChallenge.username == username).delete()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired session — please start again",
        )
    metadata = json.loads(row.metadata_json)
    metadata["challenge"] = base64url_to_bytes(row.challenge_b64)
    db.delete(row)
    db.flush()
    return metadata


def _resolve_invite_token(invite_token: str | None, family_pin: str | None, db: Session, strict: bool = True):
    """
    Resolve an invite_token string to whichever table it belongs to and validate it.
    Returns (invite_type, record) where invite_type is "registration_token" or "family_invite".
    Raises HTTPException on any validation failure.

    When strict=False (open registration mode), an unrecognised token is silently ignored
    rather than rejected, so that spurious tokens don't block open sign-up.
    """
    if not invite_token:
        return None, None

    # 1. Check RegistrationToken (CLI-generated, no expiry, no PIN)
    reg_token = db.query(RegistrationToken).filter(RegistrationToken.token == invite_token).first()
    if reg_token:
        if reg_token.is_used:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invite token has already been used"
            )
        return "registration_token", reg_token

    # 2. Check FamilyInvite (in-app, TTL + optional PIN)
    family_invite = db.query(FamilyInvite).filter(FamilyInvite.token == invite_token).first()
    if family_invite:
        if family_invite.is_used:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invite token has already been used"
            )
        if family_invite.is_expired:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invite link has expired"
            )
        if family_invite.require_pin:
            if not family_pin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="A family PIN is required to use this invite link"
                )
            creator = db.query(User).filter(User.id == family_invite.created_by_user_id).first()
            if not creator or creator.family_pin != family_pin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Incorrect family PIN"
                )
        return "family_invite", family_invite

    # Token not found in either table
    if strict:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite token"
        )
    return None, None


@router.post("/register/start", status_code=200)
@limiter.limit("5/minute")
async def passkey_register_start(
    request: Request,
    body: PasskeyRegisterStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start passkey registration - Step 1 of 2

    This endpoint:
    1. Checks if username is available
    2. Validates invite token (if REQUIRE_INVITE=true or a family invite is supplied)
    3. Generates WebAuthn registration options
    4. Returns challenge and options for browser to create passkey

    No email or password required!
    """
    # Gate: require some token when REQUIRE_INVITE is set
    if settings.require_invite and not body.invite_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An invite token is required to register"
        )

    # Resolve + validate the token (works for both RegistrationToken and FamilyInvite)
    # strict=True means an unrecognised token is rejected; in open mode, unknown tokens are ignored
    invite_type, _ = _resolve_invite_token(
        body.invite_token, body.family_pin, db, strict=settings.require_invite
    )

    # Check if username already exists
    existing_user = db.query(User).filter(User.username == body.username).first()
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
        username=body.username,
        display_name=body.display_name,
        user_id=temp_user_id
    )

    # Persist challenge to DB so multi-container deployments share state
    _save_challenge(db, body.username, challenge, "registration", {
        "temp_user_id": bytes_to_base64url(temp_user_id),
        "display_name": body.display_name,
        "invite_token": body.invite_token,
        "invite_type": invite_type,
    })
    db.commit()

    # Update options with our challenge (base64url encoded)
    options["challenge"] = bytes_to_base64url(challenge)

    return {
        "options": options,
        "username": body.username
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
    4. Burns the invite token (if any)
    5. Auto-generates a family PIN for the new user
    6. Returns the created user

    After this, user can login with just their passkey!
    """
    challenge_data = _consume_challenge(db, request.username, "registration")

    # Verify the credential
    try:
        verified = verify_registration_credential(
            credential=request.credential,
            expected_challenge=challenge_data["challenge"],
            expected_origin=settings.webauthn_origin
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Passkey verification failed: {str(e)}"
        )

    # Create user account (NO PASSWORD!) with auto-generated family PIN
    user = User(
        username=request.username,
        display_name=challenge_data["display_name"],
        email=None,
        hashed_password=None,
        family_pin=generate_slug(2),  # e.g. "silent-falcon"
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

    # ── Household placement ──────────────────────────────────────────────────
    # Family invite → join the existing household; the FamilyMember record
    # was already created by the admin, so just link it to this user account.
    # Any other invite (system token) or open registration → create a new
    # household for this user.

    invite_token = challenge_data.get("invite_token")
    invite_type = challenge_data.get("invite_type")
    household_id = None
    linked_existing_member = False  # True when we linked an existing FamilyMember

    if invite_token and invite_type:
        if invite_type == "registration_token":
            record = db.query(RegistrationToken).filter(RegistrationToken.token == invite_token).first()
        else:
            record = db.query(FamilyInvite).filter(FamilyInvite.token == invite_token).first()
        if record:
            record.used_at = datetime.utcnow()
            record.used_by_username = request.username

            if invite_type == "family_invite" and record.household_id and record.household_role_id:
                # Join the existing household — no new household created
                household_id = record.household_id
                db.add(HouseholdMembership(
                    household_id=household_id,
                    user_id=user.id,
                    role_id=record.household_role_id,
                    is_admin=False,
                    joined_at=datetime.utcnow(),
                ))
                db.flush()

                if record.family_member_id:
                    # The admin pre-created a FamilyMember for this person.
                    # Just set their user account link — no new record needed.
                    pre_existing = db.query(FamilyMember).filter(
                        FamilyMember.id == record.family_member_id,
                    ).first()
                    if pre_existing:
                        pre_existing.linked_user_id = user.id
                        linked_existing_member = True

    if household_id is None:
        # System invite or open registration — create a fresh household
        household = Household(
            name=f"{challenge_data['display_name']}'s Family",
            created_by_id=user.id,
            created_at=datetime.utcnow(),
        )
        db.add(household)
        db.flush()

        admin_role = HouseholdRole(
            household_id=household.id,
            name="Member",
            can_read_transactions=True,
            can_write_transactions=True,
            can_delete_transactions=True,
            can_read_bank_accounts=True,
            can_write_bank_accounts=True,
            can_delete_bank_accounts=True,
            can_read_documents=True,
            can_write_documents=True,
            can_delete_documents=True,
            can_read_family_members=True,
            can_write_family_members=True,
            can_delete_family_members=True,
            created_at=datetime.utcnow(),
        )
        db.add(admin_role)
        db.flush()

        db.add(HouseholdMembership(
            household_id=household.id,
            user_id=user.id,
            role_id=admin_role.id,
            is_admin=True,
            joined_at=datetime.utcnow(),
        ))
        household_id = household.id

    if not linked_existing_member:
        # Create a self-member in the household for this user
        db.add(FamilyMember(
            household_id=household_id,
            name=challenge_data["display_name"],
            member_relationship="self",
            linked_user_id=user.id,
            is_active=True,
        ))

    db.commit()
    db.refresh(user)

    return user


@router.post("/login/start", status_code=200)
@limiter.limit("10/minute")
async def passkey_login_start(
    request: Request,
    body: PasskeyLoginStartRequest,
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
    user = db.query(User).filter(User.username == body.username).first()
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
        user_verification=UserVerificationRequirement.REQUIRED
    )

    _save_challenge(db, body.username, challenge, "authentication", {
        "user_id": str(user.id),
    })
    db.commit()

    # Update options with our challenge
    options["challenge"] = bytes_to_base64url(challenge)

    return {
        "options": options,
        "username": body.username
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
    challenge_data = _consume_challenge(db, request.username, "authentication")

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
            expected_origin=settings.webauthn_origin,
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

    # Create tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
