"""Bank provider factory."""

import json
from functools import lru_cache
from typing import Optional, Tuple

from app.providers.base import BankProvider


@lru_cache(maxsize=1)
def _fetch_teller_creds_from_secret(secret_arn: str) -> Tuple[str, str]:
    """Fetch Teller credentials from AWS Secrets Manager (cached per container)."""
    import boto3
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    data = json.loads(response["SecretString"])
    return data["teller_cert_b64"], data["teller_private_key_b64"]


def _get_teller_creds() -> Tuple[Optional[str], Optional[str]]:
    from app.config import settings
    if settings.teller_secret_arn:
        return _fetch_teller_creds_from_secret(settings.teller_secret_arn)
    return settings.teller_cert_b64, settings.teller_private_key_b64


def is_teller_configured() -> bool:
    cert, key = _get_teller_creds()
    return bool(cert and key)


def get_teller_provider(access_token: Optional[str] = None) -> BankProvider:
    cert, key = _get_teller_creds()
    if not cert or not key:
        raise ValueError(
            "Teller credentials not configured. "
            "Set TELLER_SECRET_ARN (production) or "
            "TELLER_CERT_B64 + TELLER_PRIVATE_KEY_B64 (local dev)."
        )
    from app.providers.teller.client import TellerClient
    from app.providers.teller.provider import TellerProvider
    return TellerProvider(TellerClient(cert, key, access_token))
