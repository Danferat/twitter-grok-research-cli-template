from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUNS_DIR = Path("data/runs")


def _safe_timestamp(timestamp: str) -> str:
    return timestamp.replace(":", "").replace("-", "").replace("+", "").replace(".", "")


def save_run(
    payload: dict[str, Any],
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
    timestamp: str | None = None,
) -> Path:
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    generated_at = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {"generated_at": generated_at, **payload}
    filename = f"{_safe_timestamp(generated_at)}-{_slug(payload.get('query', 'run'))}.json"
    path = runs_path / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_run_path(runs_dir: Path | str = DEFAULT_RUNS_DIR) -> Path | None:
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        return None
    files = sorted(runs_path.glob("*.json"))
    return files[-1] if files else None


def load_run(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _slug(value: object) -> str:
    text = str(value).lower()
    chars = [char if char.isalnum() else "-" for char in text]
    slug = "-".join("".join(chars).split("-"))
    return slug[:60] or "run"
