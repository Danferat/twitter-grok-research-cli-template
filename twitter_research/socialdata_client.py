from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SocialDataError(RuntimeError):
    """Raised when SocialData rejects or fails a request."""


class SocialDataClient:
    base_url = "https://api.socialdata.tools/twitter/search"

    def __init__(self, api_key: str, opener: Callable | None = None):
        self.api_key = api_key
        self.opener = opener or urlopen

    def search(self, query: str, search_type: str = "Latest") -> dict[str, Any]:
        if search_type not in {"Latest", "Top"}:
            raise ValueError("search_type must be Latest or Top")

        url = f"{self.base_url}?{urlencode({'query': query, 'type': search_type})}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "twitter-research-cli/0.1",
            },
        )

        try:
            with self.opener(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            exc.close()
            raise SocialDataError(_format_socialdata_error(body, exc.code)) from exc
        except URLError as exc:
            raise SocialDataError(f"Could not reach SocialData API: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SocialDataError("SocialData returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise SocialDataError("SocialData returned an unexpected JSON object.")

        if payload.get("status") == "error":
            message = payload.get("message") or "unknown SocialData error"
            raise SocialDataError(f"SocialData search failed: {message}")

        tweets = payload.get("tweets", [])
        if not isinstance(tweets, list):
            raise SocialDataError("SocialData returned an unexpected tweets field.")

        return payload


def _format_socialdata_error(body: str, status_code: int) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"SocialData API returned HTTP {status_code}: {body}"

    if not isinstance(payload, dict):
        return f"SocialData API returned HTTP {status_code}: {body}"

    message = payload.get("message") or payload.get("error") or body
    return f"SocialData search failed: {message}"
