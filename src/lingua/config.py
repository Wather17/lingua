from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


DEFAULT_CANDIDATES = (
    "tencent/hy-mt2-30b-a3b",
    "tencent/hy-mt2-1.8b",
    "google/gemma-3-12b-it",
)


@dataclass(slots=True)
class Config:
    model: str = "tencent/hy-mt2-30b-a3b"
    candidates: list[str] = field(default_factory=lambda: list(DEFAULT_CANDIDATES))
    deck: str = "English::Kindle"
    notetype: str = "Lingua Kindle"
    base_url: str = "https://openrouter.ai/api/v1"
    data_collection: str = "deny"
    batch_size: int = 8
    daily_limit: int = 5


def config_path(workspace: Path) -> Path:
    return workspace / "config.toml"


def load_config(workspace: Path) -> Config:
    path = config_path(workspace)
    if not path.exists():
        return Config()
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    config = Config(**data)
    if config.data_collection not in {"allow", "deny"}:
        raise ValueError("data_collection deve ser 'allow' ou 'deny'")
    if config.batch_size < 1 or config.batch_size > 25:
        raise ValueError("batch_size deve estar entre 1 e 25")
    if config.daily_limit < 0:
        raise ValueError("daily_limit não pode ser negativo")
    return config


def save_config(workspace: Path, config: Config) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    candidates = ",\n  ".join(_quote(item) for item in config.candidates)
    content = (
        f"model = {_quote(config.model)}\n"
        f"candidates = [\n  {candidates},\n]\n"
        f"deck = {_quote(config.deck)}\n"
        f"notetype = {_quote(config.notetype)}\n"
        f"base_url = {_quote(config.base_url)}\n"
        f"data_collection = {_quote(config.data_collection)}\n"
        f"batch_size = {config.batch_size}\n"
        f"daily_limit = {config.daily_limit}\n"
    )
    path = config_path(workspace)
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

