"""Bank provider factory."""

from typing import Optional

from app.providers.base import BankProvider


def is_teller_configured() -> bool:
    from app.config import settings
    return bool(settings.teller_cert_b64 and settings.teller_private_key_b64)


def get_teller_provider(access_token: Optional[str] = None) -> BankProvider:
    from app.config import settings
    if not is_teller_configured():
        raise ValueError(
            "Teller credentials not configured. "
            "Set TELLER_CERT_B64 and TELLER_PRIVATE_KEY_B64 in Doppler."
        )
    from app.providers.teller.client import TellerClient
    from app.providers.teller.provider import TellerProvider
    return TellerProvider(TellerClient(settings.teller_cert_b64, settings.teller_private_key_b64, access_token))
