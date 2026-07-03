from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NansenError(RuntimeError):
    """Raised when Nansen rejects or fails a request."""


class NansenClient:
    base_url = "https://api.nansen.ai/api/v1"

    def __init__(self, api_key: str, opener: Callable | None = None):
        self.api_key = api_key
        self.opener = opener or urlopen

    def post_json(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ValueError("Nansen request body must be a JSON object.")

        payload = json.dumps(body).encode("utf-8")
        request = self._request(endpoint, payload=payload, accept="application/json")

        try:
            with self.opener(request, timeout=60) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            exc.close()
            raise NansenError(_format_nansen_error(body_text, exc.code)) from exc
        except URLError as exc:
            raise NansenError(f"Could not reach Nansen API: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise NansenError("Nansen returned a non-JSON response.") from exc

        if not isinstance(parsed, dict):
            raise NansenError("Nansen returned an unexpected JSON object.")

        return parsed

    def agent_research(
        self,
        text: str,
        mode: str = "fast",
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        if mode not in {"fast", "expert"}:
            raise ValueError("Nansen agent mode must be fast or expert.")

        body: dict[str, Any] = {"text": text}
        if conversation_id:
            body["conversation_id"] = conversation_id

        request = self._request(
            f"agent/{mode}",
            payload=json.dumps(body).encode("utf-8"),
            accept="text/event-stream",
        )

        try:
            with self.opener(request, timeout=120) as response:
                stream_text = response.read().decode("utf-8")
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            exc.close()
            raise NansenError(_format_nansen_error(body_text, exc.code)) from exc
        except URLError as exc:
            raise NansenError(f"Could not reach Nansen API: {exc.reason}") from exc

        return _parse_agent_stream(stream_text)

    def _request(self, endpoint: str, payload: bytes, accept: str) -> Request:
        normalized_endpoint = endpoint.strip().lstrip("/")
        if normalized_endpoint.startswith("api/v1/"):
            normalized_endpoint = normalized_endpoint.removeprefix("api/v1/")

        return Request(
            f"{self.base_url}/{normalized_endpoint}",
            data=payload,
            headers={
                "apikey": self.api_key,
                "Content-Type": "application/json",
                "Accept": accept,
                "User-Agent": "twitter-research-cli/0.1",
            },
            method="POST",
        )


def _parse_agent_stream(stream_text: str) -> dict[str, Any]:
    answer_parts: list[str] = []
    events: list[dict[str, Any]] = []
    conversation_id: str | None = None
    tool_calls: list[Any] = []

    for raw_line in stream_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue

        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break

        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise NansenError(f"Nansen agent returned malformed SSE JSON: {data}") from exc

        if not isinstance(event, dict):
            raise NansenError("Nansen agent returned an unexpected SSE event.")

        events.append(event)
        event_type = event.get("type")
        if event_type == "delta":
            answer_parts.append(str(event.get("text", "")))
        elif event_type == "tool_call":
            name = event.get("name")
            if name and name not in tool_calls:
                tool_calls.append(name)
        elif event_type == "finish":
            conversation_id = event.get("conversation_id") or conversation_id
            final_tool_calls = event.get("tool_calls")
            if isinstance(final_tool_calls, list):
                tool_calls = final_tool_calls
        elif event_type == "error":
            message = event.get("error") or "unknown Nansen agent error"
            raise NansenError(f"Nansen agent failed: {message}")

    return {
        "answer": "".join(answer_parts),
        "conversation_id": conversation_id,
        "tool_calls": tool_calls,
        "events": events,
    }


def _format_nansen_error(body: str, status_code: int) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"Nansen API returned HTTP {status_code}: {body}"

    if not isinstance(payload, dict):
        return f"Nansen API returned HTTP {status_code}: {body}"

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("code")
    else:
        message = payload.get("message") or payload.get("error")

    return f"Nansen API returned HTTP {status_code}: {message or body}"
