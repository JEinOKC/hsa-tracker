"""Rate limiting utilities — shared limiter instance used across the app."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_client_ip(request: Request) -> str:
    """Return the real client IP.

    Behind API Gateway (Lambda) or any reverse proxy the true IP arrives in
    X-Forwarded-For.  Fall back to the direct connection address so that local
    development and bare-server deployments continue to work unchanged.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the leftmost is the client.
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_ip)
