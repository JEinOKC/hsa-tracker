"""WebAuthn / Passkey utility functions"""

import secrets
import base64
import json
from typing import Dict, Any, Optional
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    AttestationConveyancePreference,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from app.config import settings


def generate_challenge() -> bytes:
    """Generate a random challenge for WebAuthn"""
    return secrets.token_bytes(32)


def base64url_to_bytes(val: str) -> bytes:
    """Convert base64url string to bytes"""
    # Add padding if needed
    padding = 4 - (len(val) % 4)
    if padding and padding != 4:
        val += '=' * padding
    # Replace URL-safe characters
    val = val.replace('-', '+').replace('_', '/')
    return base64.b64decode(val)


def bytes_to_base64url(val: bytes) -> str:
    """Convert bytes to base64url string"""
    return base64.urlsafe_b64encode(val).decode('utf-8').rstrip('=')


def create_registration_options(
    username: str,
    display_name: str,
    user_id: bytes
) -> Dict[str, Any]:
    """
    Generate WebAuthn registration options for passkey creation

    Args:
        username: User's unique username
        display_name: User's display name
        user_id: User's unique ID (as bytes)

    Returns:
        Registration options dict for frontend
    """
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id,
        user_name=username,
        user_display_name=display_name,
        attestation=AttestationConveyancePreference.NONE,  # No attestation needed for most use cases
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,  # Require discoverable credentials
            user_verification=UserVerificationRequirement.REQUIRED,  # Require biometric/PIN
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,  # ES256 - most widely supported
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,  # RS256
        ],
        timeout=60000,  # 60 seconds
    )

    return json.loads(options_to_json(options))


def verify_registration_credential(
    credential: Dict[str, Any],
    expected_challenge: bytes,
    expected_origin: str
) -> Dict[str, Any]:
    """
    Verify WebAuthn registration credential from browser

    Args:
        credential: Credential object from browser
        expected_challenge: Challenge we sent to browser
        expected_origin: Expected origin (e.g., https://localhost:3001)

    Returns:
        Verified credential data including credential_id, public_key, etc.
    """
    verification = verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=expected_origin,
        expected_rp_id=settings.webauthn_rp_id,
    )

    return {
        "credential_id": bytes_to_base64url(verification.credential_id),
        "public_key": bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "aaguid": str(verification.aaguid) if verification.aaguid else None,
    }


def create_authentication_options(
    user_credentials: list,
    user_verification: UserVerificationRequirement = UserVerificationRequirement.REQUIRED
) -> Dict[str, Any]:
    """
    Generate WebAuthn authentication options for passkey login

    Args:
        user_credentials: List of user's passkey credentials
        user_verification: Level of user verification (enum)

    Returns:
        Authentication options dict for frontend
    """
    # Convert stored credentials to PublicKeyCredentialDescriptor format
    allow_credentials = []
    for cred in user_credentials:
        credential_id_bytes = base64url_to_bytes(cred["credential_id"])

        transports = []
        if cred.get("transports"):
            try:
                transports = json.loads(cred["transports"])
            except:
                pass

        allow_credentials.append(
            PublicKeyCredentialDescriptor(
                id=credential_id_bytes,
                transports=transports if transports else None,
            )
        )

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        timeout=60000,  # 60 seconds
        allow_credentials=allow_credentials,
        user_verification=user_verification,
    )

    return json.loads(options_to_json(options))


def verify_authentication_credential(
    credential: Dict[str, Any],
    expected_challenge: bytes,
    expected_origin: str,
    credential_public_key: bytes,
    credential_current_sign_count: int
) -> Dict[str, Any]:
    """
    Verify WebAuthn authentication credential from browser

    Args:
        credential: Assertion credential from browser
        expected_challenge: Challenge we sent to browser
        expected_origin: Expected origin
        credential_public_key: Stored public key for this credential
        credential_current_sign_count: Current sign count from database

    Returns:
        Verified authentication data including new sign_count
    """
    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=expected_origin,
        expected_rp_id=settings.webauthn_rp_id,
        credential_public_key=credential_public_key,
        credential_current_sign_count=credential_current_sign_count,
    )

    return {
        "verified": True,
        "new_sign_count": verification.new_sign_count,
        "credential_id": bytes_to_base64url(verification.credential_id),
    }
