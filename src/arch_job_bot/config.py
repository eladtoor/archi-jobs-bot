"""Configuration loading: YAML keyword/geo/source configs and .env secrets.

Config files live in the project ``config/`` directory by default; override with the
``ARCH_BOT_CONFIG_DIR`` environment variable (useful in tests / CI).
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

# project root = .../src/arch_job_bot/config.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    override = os.environ.get("ARCH_BOT_CONFIG_DIR")
    return Path(override) if override else PROJECT_ROOT / "config"


def _load_yaml(name: str) -> dict[str, Any]:
    path = config_dir() / name
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


@functools.lru_cache(maxsize=None)
def keywords() -> dict[str, Any]:
    return _load_yaml("keywords.yaml")


@functools.lru_cache(maxsize=None)
def geo() -> dict[str, Any]:
    return _load_yaml("geo.yaml")


@functools.lru_cache(maxsize=None)
def sources() -> dict[str, Any]:
    return _load_yaml("sources.yaml")


def reload() -> None:
    """Clear caches (call after editing config at runtime or between tests)."""
    keywords.cache_clear()
    geo.cache_clear()
    sources.cache_clear()


# ── runtime settings (env-driven) ────────────────────────────────────────────

def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def data_dir() -> Path:
    """Where the SQLite dedup DB and logs live."""
    override = os.environ.get("ARCH_BOT_DATA_DIR")
    d = Path(override) if override else PROJECT_ROOT / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
