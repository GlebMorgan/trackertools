from __future__ import annotations

from datetime import date
from typing import ClassVar, Sequence

from api import BackendData
from config import CONFIG
from tools import AppError


class CacheMissError(AppError):
    pass


class CacheManager:
    entry_cache_template: ClassVar[str] = CONFIG.backend + '-entries-[{start}]-[{end}].json'
    task_cache_template: ClassVar[str] = CONFIG.backend + '-tasks-[{start}]-[{end}].json'

    @classmethod
    def load_entries(cls, since: date, until: date) -> Sequence[BackendData]:
        raise CacheMissError

    @classmethod
    def load_tasks(cls) -> Sequence[BackendData]:
        # Sort by level
        raise CacheMissError

    @classmethod
    def save(cls, data: Sequence[BackendData]) -> bool:
        # If cache with identical dates exists, replace existing file
        return False

    @classmethod
    def clear(cls) -> int:
        # Clear all cache and return number of deleted files
        return 0
