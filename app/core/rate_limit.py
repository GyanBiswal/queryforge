from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_api_key_identity(request: Request) -> str:
    """
    Rate-limit by API key, not IP — multiple legitimate clients could share
    an IP (corporate NAT, VPN), and a single bad actor could rotate IPs.
    Key identity is the correct unit of rate limiting for an authenticated API.
    Falls back to IP only for unauthenticated requests (shouldn't normally
    happen given our auth dependency runs first, but fails safe either way).
    """
    api_key = request.headers.get("X-API-Key")
    return api_key if api_key else get_remote_address(request)


limiter = Limiter(key_func=get_api_key_identity)