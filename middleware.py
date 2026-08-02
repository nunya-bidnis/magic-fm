"""
Magic.fm - Request-level helpers.

get_client_ip() must not blindly trust X-Forwarded-For - it's fully
attacker-controlled input. uvicorn binds only to 127.0.0.1:8000 (see
magic-fm.service), so the only process that can ever be the direct TCP peer
is nginx running on the same box. Only when the direct peer IS loopback do
we read X-Forwarded-For/X-Real-IP - and only because nginx.conf is
configured to overwrite those headers with $remote_addr (not append to
whatever the client sent), so nothing the client puts in those headers
survives to reach this code.
"""
from fastapi import Request

TRUSTED_PROXY_IPS = {"127.0.0.1", "::1"}


async def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else None

    if peer in TRUSTED_PROXY_IPS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return peer or "unknown"
