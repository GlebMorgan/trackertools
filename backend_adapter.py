from datetime import datetime
from typing import List, NamedTuple

from api import Json
from tools import AppError


Jira = str | None
Spec = str | None


class ParseError(AppError):
    pass


class TEntry(NamedTuple):
    id: int
    task: int
    start: datetime
    end: datetime
    description: str


class TTask(NamedTuple):
    id: int
    parent: int | None
    title: str
    jira: Jira
    spec: Spec


class BackendAdapter:
    @classmethod
    def parse_tasks(cls, raw_tasks: Json) -> List[TTask]:
        raise NotImplementedError

    @classmethod
    def parse_entries(cls, raw_entries: Json) -> List[TEntry]:
        raise NotImplementedError
