from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SURF_API_BASE_URL = "https://api.asksurf.ai/gateway/v1"


class SurfError(RuntimeError):
    """Raised when Surf CLI is unavailable or returns an error."""


class SurfClient:
    def __init__(self, binary_path: str | None = None):
        self.binary_path = binary_path or _default_surf_binary()

    def search_social_posts(self, query: str, limit: int = 20) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        command = [
            self.binary_path,
            "search-social-posts",
            "--q",
            query,
            "--limit",
            str(limit),
            "--json",
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise SurfError(
                "Surf CLI is not installed or not available. Install it with the Surf installer first."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SurfError("Surf search timed out.") from exc

        stdout = completed.stdout.strip()
        if completed.returncode != 0:
            raise SurfError(_format_surf_error(stdout, completed.stderr))

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise SurfError("Surf returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise SurfError("Surf returned an unexpected JSON object.")

        if "error" in payload:
            raise SurfError(_format_surf_error(stdout, ""))
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise SurfError("Surf returned an unexpected data field.")
        return payload

    def list_operations(self, category: str | None = None) -> dict[str, Any]:
        command = [self.binary_path, "list-operations"]
        if category:
            command.extend(["--category", category])
        return {"text": self._run_text_command(command)}

    def call_operation(
        self,
        operation: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not operation:
            raise ValueError("operation is required")

        command = [self.binary_path, operation]
        for key, value in (params or {}).items():
            if value is None or value is False:
                continue
            flag = f"--{key.replace('_', '-')}"
            if value is True:
                command.append(flag)
                continue
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            command.extend([flag, str(value)])
        command.append("--json")

        stdin = json.dumps(body, ensure_ascii=False) if body is not None else None
        return self._run_json_command(command, stdin=stdin)

    def _run_json_command(self, command: list[str], stdin: str | None = None) -> dict[str, Any]:
        stdout = self._run_text_command(command, stdin=stdin)
        return _parse_surf_payload(stdout)

    def _run_text_command(self, command: list[str], stdin: str | None = None) -> str:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                input=stdin,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise SurfError(
                "Surf CLI is not installed or not available. Install it with the Surf installer first."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SurfError("Surf command timed out.") from exc

        stdout = completed.stdout.strip()
        if completed.returncode != 0:
            raise SurfError(_format_surf_error(stdout, completed.stderr))
        return stdout


class SurfApiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = SURF_API_BASE_URL,
        opener=urlopen,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.opener = opener

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_endpoint = _normalize_api_endpoint(endpoint)
        url = f"{self.base_url}/{normalized_endpoint}"
        query = _encode_query_params(params or {})
        if query:
            url = f"{url}?{query}"

        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            exc.close()
            raise SurfError(_format_api_error(raw, exc.reason)) from exc
        except URLError as exc:
            raise SurfError(f"Surf API request failed: {exc.reason}") from exc

        return _parse_surf_payload(raw)

    def chat_response(
        self,
        question: str,
        model: str = "surf-2.0",
        effort: str = "medium",
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "responses",
            body={
                "model": model,
                "input": question,
                "reasoning": {"effort": effort},
            },
        )


def _default_surf_binary() -> str:
    found = shutil.which("surf")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / "surf")


def _format_surf_error(stdout: str, stderr: str) -> str:
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict):
                error = payload.get("error", {})
                if isinstance(error, dict):
                    message = error.get("message")
                else:
                    message = str(error) if error else ""
                if message:
                    return f"Surf search failed: {message}"
    detail = stderr.strip() or stdout.strip() or "unknown Surf error"
    return f"Surf search failed: {detail}"


def _parse_surf_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SurfError("Surf returned a non-JSON response.") from exc

    if not isinstance(payload, dict):
        raise SurfError("Surf returned an unexpected JSON object.")
    if "error" in payload:
        raise SurfError(_format_surf_error(raw, ""))
    return payload


def _normalize_api_endpoint(endpoint: str) -> str:
    value = endpoint.strip().strip("/")
    if not value:
        raise ValueError("endpoint is required")
    value = value.removeprefix("https://api.asksurf.ai/")
    value = value.removeprefix("gateway/v1/")
    return value.strip("/")


def _encode_query_params(params: dict[str, Any]) -> str:
    normalized: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            normalized[key] = "true" if value else "false"
        elif isinstance(value, list):
            normalized[key] = ",".join(str(item) for item in value)
        elif isinstance(value, dict):
            normalized[key] = json.dumps(value, ensure_ascii=False)
        else:
            normalized[key] = str(value)
    return urlencode(normalized)


def _format_api_error(raw: str, fallback: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return f"Surf API request failed: {raw.strip() or fallback}"

    if isinstance(payload, dict):
        error = payload.get("error", {})
        if isinstance(error, dict) and error.get("message"):
            return f"Surf API request failed: {error['message']}"
        if error:
            return f"Surf API request failed: {error}"
    return f"Surf API request failed: {fallback}"
