from __future__ import annotations

import time

import httpx

from studio.config import StudioError

RETRY_STATUS = {429, 500, 502, 503, 504}


def send(client: httpx.Client, method: str, url: str, *, retries: int = 3, **kwargs) -> httpx.Response:
    """One request with backoff on transport errors, 429 and 5xx. Returns the final response."""
    for attempt in range(retries + 1):
        try:
            resp = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            if attempt == retries:
                raise StudioError(f"{method} {url} failed: {exc.__class__.__name__}") from exc
        else:
            if resp.status_code not in RETRY_STATUS or attempt == retries:
                return resp
        time.sleep(min(2**attempt, 8))
    raise AssertionError("unreachable")


def json_or_raise(resp: httpx.Response, what: str) -> dict:
    """Parse a JSON body, or raise a StudioError carrying the status and a body excerpt."""
    if resp.status_code >= 400:
        raise StudioError(f"{what} failed: HTTP {resp.status_code} {resp.text[:300]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise StudioError(f"{what}: response was not JSON: {resp.text[:200]}") from exc
