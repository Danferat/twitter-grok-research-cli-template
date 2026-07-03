from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GrokApiError(RuntimeError):
    """Raised when xAI rejects or fails a request."""


Transport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]

GROK_MODEL = "grok-4.3"


class GrokClient:
    base_url = "https://api.x.ai/v1"

    def __init__(
        self,
        api_key: str | None,
        model: str = GROK_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: int = 120,
        transport: Transport | None = None,
    ):
        if not api_key:
            raise GrokApiError("Missing XAI_API_KEY. Add it to .env or export it in the shell.")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._transport = transport or _post_json

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        search_parameters: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        if search_parameters is not None:
            payload["search_parameters"] = search_parameters
        response = self._transport(
            f"{self.base_url}/chat/completions",
            payload,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "twitter-research-cli/0.1",
            },
            self.timeout,
        )
        return _extract_chat_text(response)

    def search(self, question: str, max_search_results: int = 20) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a Grok X/Twitter-only research assistant. "
                        "Use only x_search to inspect public X/Twitter posts. "
                        "Do not use general internet search, websites, news pages, or local Twitter API results. "
                        f"Use up to {max_search_results} relevant X/Twitter sources. Answer in Russian."
                    ),
                },
                {"role": "user", "content": question},
            ],
            "tools": [{"type": "x_search"}],
        }
        response = self._transport(
            f"{self.base_url}/responses",
            payload,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "twitter-research-cli/0.1",
            },
            self.timeout,
        )
        _validate_x_only_response(response)
        return {
            "answer": _extract_response_text(response),
            "citations": response.get("citations", []),
            "usage": response.get("usage", {}),
            "raw_response": response,
        }

    def analyze_run(self, run: dict[str, Any], max_tweets: int = 20) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You analyze X/Twitter search results for research. "
                    "Separate observed tweet narratives from inference. "
                    "Answer in Russian, concise but specific."
                ),
            },
            {"role": "user", "content": build_run_analysis_prompt(run, max_tweets=max_tweets)},
        ]
        return self.chat(messages)


def build_run_analysis_prompt(run: dict[str, Any], max_tweets: int = 20) -> str:
    tweets = run.get("api_data", {}).get("data", [])
    users = {
        user.get("id"): user
        for user in run.get("api_data", {}).get("includes", {}).get("users", [])
    }

    lines = [
        "Analyze this saved X/Twitter research run.",
        f"Query: {run.get('query')}",
        f"Mode: {run.get('mode')} | Days: {run.get('requested_days')} | Fetched: {run.get('fetched')}",
        "",
        "Tweets:",
    ]
    for index, tweet in enumerate(tweets[:max_tweets], start=1):
        user = users.get(tweet.get("author_id"), {})
        username = user.get("username")
        author = f"@{username}" if username else f"author:{tweet.get('author_id', 'unknown')}"
        created_at = tweet.get("created_at", "unknown-time")
        text = " ".join(tweet.get("text", "").split())
        lines.append(f"{index}. {author} | {created_at} | {text}")

    if not tweets:
        lines.append("No tweets were returned.")

    lines.extend(
        [
            "",
            "Return:",
            "- main repeated narratives",
            "- what is evidence from tweets vs inference",
            "- uncertainty and data limits",
        ]
    )
    return "\n".join(lines)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        exc.close()
        raise GrokApiError(f"xAI API returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise GrokApiError(f"Could not reach xAI API: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise GrokApiError("xAI API returned a non-JSON response.") from exc


def _extract_chat_text(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GrokApiError(f"Unexpected xAI API response: {response}") from exc
    if not isinstance(content, str):
        raise GrokApiError(f"Unexpected xAI message content: {content}")
    return content


def _extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text

    try:
        output = response["output"]
    except KeyError as exc:
        raise GrokApiError(f"Unexpected xAI API response: {response}") from exc

    parts: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict):
                    text = content.get("text")
                    if isinstance(text, str):
                        parts.append(text)
    if parts:
        return "\n".join(parts)
    raise GrokApiError(f"Unexpected xAI API response: {response}")


def _validate_x_only_response(response: dict[str, Any]) -> None:
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        raise GrokApiError("Grok response did not include verifiable x_search usage details.")

    details = usage.get("server_side_tool_usage_details")
    if not isinstance(details, dict):
        raise GrokApiError("Grok response did not include verifiable x_search usage details.")

    web_search_calls = details.get("web_search_calls", 0) or 0
    if web_search_calls:
        raise GrokApiError("Grok response used web_search, but Grok search is restricted to x_search only.")

    x_search_calls = details.get("x_search_calls")
    if not x_search_calls:
        raise GrokApiError("Grok response did not use x_search, so no X/Twitter-only result was accepted.")
