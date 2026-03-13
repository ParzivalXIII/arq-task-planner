"""Database layer package.

Exports engine and session helper for dependency injection.
"""

from .session import engine, get_session

__all__ = ["engine", "get_session"]

