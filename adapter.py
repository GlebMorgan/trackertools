from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from api import BackendData
from tools import AppError


class ParseError(AppError):
    pass


class GenericEntry(NamedTuple):
    id: int
    task: int
    start: datetime
    end: datetime
    description: str


class GenericTask(NamedTuple):
    id: int
    parent: int | None
    title: str
    jira: str | None
    spec: str | None


class BackendAdapter:
    @classmethod
    def parse_task(cls, raw_task: BackendData) -> GenericTask:
        raise NotImplementedError

    @classmethod
    def parse_entry(cls, raw_entry: BackendData) -> GenericEntry:
        raise NotImplementedError
