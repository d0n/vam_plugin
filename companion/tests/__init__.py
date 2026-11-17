"""Test package. Safety net: tests never open network connections except to this machine
(fake servers on 127.0.0.1), so a test that accidentally builds a real engine cannot reach
api.x.ai or ElevenLabs with a fake key."""
import socket

_create_connection = socket.create_connection


def _local_only(address, *args, **kwargs):
    host = address[0]
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise OSError(f"tests must not connect to {host} (network blocked in tests)")
    return _create_connection(address, *args, **kwargs)


socket.create_connection = _local_only
