"""De-duplication: grow-only SQLite store keyed on native job ids."""

from .store import SeenStore

__all__ = ["SeenStore"]
