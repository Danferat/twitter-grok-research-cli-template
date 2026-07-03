from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when required local configuration is missing."""


@dataclass(frozen=True)
class Config:
    xai_api_key: str | None = None
    socialdata_api_key: str | None = None
    nansen_api_key: str | None = None
    surf_api_key: str | None = None


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'").strip('"')
        values[key.strip()] = value
    return values


def load_config(
    env_path: Path | str = ".env",
    environ: dict[str, str] | None = None,
) -> Config:
    import os

    env = dict(os.environ if environ is None else environ)
    file_values = _parse_env_file(Path(env_path))
    xai_api_key = env.get("XAI_API_KEY") or file_values.get("XAI_API_KEY")
    socialdata_api_key = env.get("SOCIALDATA_API_KEY") or file_values.get("SOCIALDATA_API_KEY")
    nansen_api_key = env.get("NANSEN_API_KEY") or file_values.get("NANSEN_API_KEY")
    surf_api_key = env.get("SURF_API_KEY") or file_values.get("SURF_API_KEY")

    return Config(
        xai_api_key=xai_api_key,
        socialdata_api_key=socialdata_api_key,
        nansen_api_key=nansen_api_key,
        surf_api_key=surf_api_key,
    )
