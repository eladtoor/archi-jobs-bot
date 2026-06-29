"""Source scrapers + registry.

`build_sources(http)` reads config/sources.yaml and instantiates the enabled
sources with their query URLs and geo flags.
"""

from __future__ import annotations

import logging

from ... import config
from ..base import BaseSource
from .alljobs import AllJobsSource
from .drushim import DrushimSource
from .jobkarov import JobKarovSource
from .jobmaster import JobMasterSource

log = logging.getLogger(__name__)

REGISTRY: dict[str, type[BaseSource]] = {
    "alljobs": AllJobsSource,
    "drushim": DrushimSource,
    "jobmaster": JobMasterSource,
    "jobkarov": JobKarovSource,
}


def build_sources(http) -> list[BaseSource]:
    cfg = config.sources()
    default_poll = int(cfg.get("poll_minutes_default", 12))
    sources: list[BaseSource] = []
    for entry in cfg.get("sources", []):
        if not entry.get("enabled", True):
            continue
        key = entry.get("key")
        cls = REGISTRY.get(key)
        if cls is None:
            log.warning("Unknown source key %r in sources.yaml — skipping", key)
            continue
        sources.append(
            cls(
                http,
                queries=list(entry.get("queries", [])),
                arch_only=bool(entry.get("arch_only", False)),
                geo_trusted=bool(entry.get("geo_trusted", False)),
                poll_minutes=int(entry.get("poll_minutes", default_poll)),
            )
        )
    return sources


__all__ = ["build_sources", "REGISTRY", "BaseSource"]
