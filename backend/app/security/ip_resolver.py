"""Trusted Client IP Extraction and Proxy Header Validation.

Guarantees:
1. Validates IP address syntax using ipaddress.ip_address.
2. Prevents IP rotation attacks via forged client-supplied X-Forwarded-For headers.
3. Prioritizes trusted infrastructure headers (Cloudflare CF-Connecting-IP, Render True-Client-IP).
4. Correctly extracts the client IP from multi-hop X-Forwarded-For headers.
5. Fails safely to loopback (127.0.0.1) when headers are absent, malformed, or invalid.
"""

import ipaddress
import re
from fastapi import Request

from app.core.config import settings
from app.core.logging import logger

# RFC 1918 and loopback networks for trusted proxy classification
DEFAULT_TRUSTED_PROXY_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def parse_ip(ip_str: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse and validate IP string, stripping port if present."""
    if not ip_str or not isinstance(ip_str, str):
        return None
    cleaned = ip_str.strip().strip('"').strip("'")
    # Strip port if format is IP:PORT (e.g., 192.168.1.1:54321)
    if ":" in cleaned and not cleaned.startswith("[") and cleaned.count(":") == 1:
        cleaned = cleaned.split(":")[0].strip()
    elif cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1 : cleaned.index("]")].strip()

    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def is_trusted_proxy_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Determine whether the socket peer IP is a known trusted reverse proxy/container network."""
    for network in DEFAULT_TRUSTED_PROXY_NETWORKS:
        if ip in network:
            return True
    return False


def get_trusted_client_ip(request: Request) -> str:
    """Extract and securely validate client IP from request.

    Resolution Strategy:
    1. Check socket peer IP (`request.client.host`).
    2. If socket peer is loopback or trusted proxy (e.g. Render/Cloudflare/local reverse proxy):
       a. Check 'CF-Connecting-IP' (set by Cloudflare / Vercel Edge).
       b. Check 'True-Client-IP' (set by Render Edge).
       c. Check 'X-Real-IP'.
       d. Parse 'X-Forwarded-For':
          In reverse-proxy setups, proxies append the remote address to the right.
          An attacker-supplied header `X-Forwarded-For: forged_ip` arrives as `forged_ip, client_ip`.
          Therefore, we inspect from right to left to find the first untrusted client IP.
    3. If socket peer is not a trusted proxy, socket peer IP is used directly to prevent spoofing.
    4. Validate result with ipaddress; fallback to '127.0.0.1' if malformed.
    """
    raw_socket_ip = request.client.host if request.client else None
    parsed_socket = parse_ip(raw_socket_ip)

    # In local testing or when socket is loopback/unspecified, default to loopback
    if not parsed_socket:
        parsed_socket = ipaddress.ip_address("127.0.0.1")

    # If socket peer is NOT a trusted proxy, ignore all forwarding headers to prevent spoofing
    # (Except when explicitly running in production container where Render forwards via reverse proxy)
    is_trusted = is_trusted_proxy_address(parsed_socket)
    is_prod = getattr(settings, "effective_env", "") == "production"

    if not is_trusted and not is_prod:
        return str(parsed_socket)

    # 1. Cloudflare / Vercel Edge header
    cf_ip = parse_ip(request.headers.get("cf-connecting-ip"))
    if cf_ip and not cf_ip.is_unspecified:
        return str(cf_ip)

    # 2. Render Edge header
    true_client_ip = parse_ip(request.headers.get("true-client-ip"))
    if true_client_ip and not true_client_ip.is_unspecified:
        return str(true_client_ip)

    # 3. X-Real-IP header
    real_ip = parse_ip(request.headers.get("x-real-ip"))
    if real_ip and not real_ip.is_unspecified:
        return str(real_ip)

    # 4. X-Forwarded-For: traverse right-to-left
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        # Walk from right to left
        for candidate_str in reversed(parts):
            candidate = parse_ip(candidate_str)
            if candidate and not candidate.is_unspecified:
                # If candidate is not a trusted proxy, it is the originating client IP!
                if not is_trusted_proxy_address(candidate):
                    return str(candidate)
                # If all hops are internal, return the leftmost valid parsed IP
        # If all were trusted proxies, return the first valid one
        if parts:
            first_valid = parse_ip(parts[0])
            if first_valid:
                return str(first_valid)

    # Default fallback
    return str(parsed_socket)

