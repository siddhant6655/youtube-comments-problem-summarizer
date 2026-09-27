"""Some networks (notably behind certain corporate security agents) blackhole IPv6
while IPv4 works fine. httplib2 (used by google-api-python-client for the YouTube
source) doesn't fall back from IPv6 to IPv4 like curl/httpx do, so it just hangs.
Importing this module once, before any network clients are built, forces IPv4-only
DNS resolution for the whole process so those calls connect instead of hanging."""

import socket

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo
