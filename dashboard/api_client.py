"""
dashboard/api_client.py

Small helper for talking to the FastAPI backend. Every function returns
(data, error): `data` is the parsed JSON (or None on failure) and `error`
is a readable message (or None on success), so the dashboard never crashes
when the API is down.
"""

import requests

TIMEOUT_SECONDS = 3


def _get(base_url: str, path: str, params: dict = None):
    try:
        resp = requests.get(f"{base_url.rstrip('/')}{path}", params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as exc:
        return None, str(exc)


def get_health(base_url: str):
    return _get(base_url, "/health")


def get_metrics(base_url: str):
    return _get(base_url, "/metrics")


def get_events(base_url: str, limit: int = 200):
    return _get(base_url, "/events", {"limit": limit})
