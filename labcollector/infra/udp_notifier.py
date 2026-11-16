"""Sends a short JSON message over UDP to a remote computer.

UDP is "fire and forget": there is no connection and no reply, so "sent" means the
message left this computer, not that it arrived. tools/udp_listener.py shows what
the other side receives.
"""

import json
import socket


def send(host: str, port: int, payload: dict, timeout: float = 2.0) -> str | None:
    """Send ``payload`` as one UTF-8 JSON datagram. Returns None if sent, else the error."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(data, (host, port))
    except OSError as error:  # includes unknown host names (socket.gaierror)
        return f"couldn't send to {host}:{port}: {error.strerror or error}"
    return None
