"""Tiny HTTP client on the standard library (urllib), used by the cloud engines.

Network access exists ONLY in this companion app; the VaM plugin never talks to the network.
The opener is injectable so the tests run against a fake server (no real keys, no network).
API keys travel only in request headers and are never logged.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from typing import Any

Opener = Callable[[urllib.request.Request, float], Any]


class ApiError(Exception):
    """A failed request. status 0 = no answer (network, timeout)."""

    def __init__(self, service: str, status: int, message: str):
        super().__init__(f"{service}: HTTP {status}: {message}" if status else f"{service}: {message}")
        self.service = service
        self.status = status
        self.message = message


def is_key_rejection(status: int, message: str) -> bool:
    """True if the server refused the API key. xAI answers a wrong key with HTTP 400 and
    "Incorrect API key provided" (seen on /v1/tts, /v1/stt and the realtime handshake, 17.11.2026),
    other services with 401 / 403."""
    return status in (401, 403) or (status == 400 and "api key" in str(message).lower())


def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 (https URLs from config)


def _error_text(body: bytes) -> str:
    text = body.decode("utf-8", "replace").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if isinstance(data, dict):
        for key in ("error", "detail", "message"):
            value = data.get(key)
            if isinstance(value, dict):
                value = value.get("message") or value.get("status") or json.dumps(value)
            if value:
                return str(value)[:300]
    return text[:300]


class HttpClient:
    def __init__(self, opener: Opener | None = None):
        self._open = opener or _default_opener

    def open(self, service: str, method: str, url: str, headers: dict[str, str], body: bytes | None,
             timeout: float) -> Any:
        """Sends the request and returns the open response (a context manager)."""
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            return self._open(request, timeout)
        except urllib.error.HTTPError as e:
            try:
                detail = _error_text(e.read())
            except Exception:  # noqa: BLE001 - best effort only
                detail = str(e.reason)
            raise ApiError(service, e.code, detail) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise ApiError(service, 0, f"no connection ({reason})") from None

    def post_json(self, service: str, url: str, headers: dict[str, str], payload: dict[str, Any],
                  timeout: float) -> tuple[bytes, str]:
        """POSTs JSON; returns (body, content type)."""
        h = {**headers, "Content-Type": "application/json"}
        with self.open(service, "POST", url, h, json.dumps(payload).encode("utf-8"), timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "") if resp.headers else ""

    def post_multipart(self, service: str, url: str, headers: dict[str, str], fields: list[tuple[str, str]],
                       file_field: str, file_name: str, file_type: str, file_data: bytes,
                       timeout: float) -> bytes:
        """POSTs multipart/form-data; the file is the LAST part (xAI STT requires that)."""
        boundary = "aibody" + uuid.uuid4().hex
        parts: list[bytes] = []
        for name, value in fields:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                         .encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                     f'filename="{file_name}"\r\nContent-Type: {file_type}\r\n\r\n'.encode())
        parts.append(file_data)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        h = {**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"}
        with self.open(service, "POST", url, h, b"".join(parts), timeout) as resp:
            return resp.read()


def iter_sse(lines: Iterator[bytes]) -> Iterator[tuple[str, str]]:
    """Parses a Server-Sent-Events stream into (event name, data) pairs. "data: [DONE]" ends it."""
    event, data = "", []
    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data:
                payload = "\n".join(data)
                if payload.strip() == "[DONE]":
                    return
                yield event, payload
            event, data = "", []
            continue
        if line.startswith(":"):
            continue  # comment / keep-alive
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if data and "\n".join(data).strip() != "[DONE]":
        yield event, "\n".join(data)
