"""Validated, secret-bearing Vobiz callback URL construction."""

import ipaddress
import re
from urllib.parse import quote, urlsplit, urlunsplit


def public_https_origin(raw: str) -> str:
    """Return one public HTTPS origin, without paths or trailing slashes."""
    if not isinstance(raw, str) or not raw or any(char.isspace() for char in raw):
        raise ValueError("Public origin must be a public HTTPS hostname")
    try:
        parsed = urlsplit(raw.rstrip("/"))
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError("Public origin must be a public HTTPS hostname") from exc
    if (
        parsed.scheme != "https" or not parsed.netloc or not host
        or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
        or port == 0 or not re.fullmatch(r"[A-Za-z0-9.-]+", host)
        or any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
               for label in host.split("."))
        or host.lower() == "localhost" or host.lower().endswith(".localhost")
    ):
        raise ValueError("Public origin must be a public HTTPS hostname")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("Public origin must be a public HTTPS hostname")
    return urlunsplit(("https", parsed.netloc.lower(), "", "", ""))


def vobiz_answer_url(public_base_url: str, line_id: str, stream_secret: str) -> str:
    """Construct the canonical protected Answer URL without exposing it in errors."""
    origin = public_https_origin(public_base_url)
    for segment in (line_id, stream_secret):
        if (
            not isinstance(segment, str) or not segment or any(char.isspace() for char in segment)
            or any(marker in segment.lower() for marker in ("•", "***", "<redacted>", "<masked>"))
        ):
            raise ValueError("Vobiz route identifier or secret is missing or masked")
    origin_parts = urlsplit(origin)
    path = "/webhooks/vobiz/" + quote(line_id, safe="") + "/" + quote(stream_secret, safe="")
    return urlunsplit((origin_parts.scheme, origin_parts.netloc, path, "", ""))
