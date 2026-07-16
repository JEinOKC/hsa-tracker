"""Bank provider factory — SimpleFIN Bridge."""


def is_simplefin_configured() -> bool:
    """SimpleFIN requires no server-side API keys — the feature is always available."""
    return True


def claim_simplefin_setup_token(setup_token: str) -> str:
    """Decode and claim a SimpleFIN Setup Token, returning the long-lived Access URL."""
    from app.providers.simplefin.client import SimpleFINClient
    return SimpleFINClient.claim_setup_token(setup_token)


def get_simplefin_provider(access_url: str):
    """Return a SimpleFINProvider bound to the given Access URL."""
    from app.providers.simplefin.client import SimpleFINClient
    from app.providers.simplefin.provider import SimpleFINProvider
    return SimpleFINProvider(client=SimpleFINClient(access_url))
