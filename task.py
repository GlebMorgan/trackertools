from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import ClassVar, Dict, NewType, Sequence

from adapter import BackendDataError, GenericTask
from api import BackendData
from cache import CacheManager
from config import CONFIG, trace


match CONFIG.backend:
    case 'timecamp':
        from timecamp_adapter import TimecampAdapter as Adapter
        from timecamp_api import Timecamp as Server
    case 'timeular':
        from timeular_adapter import TimeularAdapter as Adapter
        from timeular_api import Timeular as Server
    case unsupported:
        raise ImportError(f"Invalid backend config: '{unsupported}'")


TaskId = NewType("TaskId", int)
Jira = NewType("Jira", str)
Spec = NewType("Spec", str)


@dataclass(frozen=True, slots=True)
class Task:
    id: TaskId
    parent: Task | None
    name: str
    jira: Jira | None
    spec: Spec | None

    all: ClassVar[Dict[int, Task]] = {}

    @classmethod
    def gen(cls, generic_task: GenericTask) -> Task:
        task_id = TaskId(generic_task.id)
        if task_id in cls.all:
            raise RuntimeError(f"Task '{task_id}': already exists: {cls.all[task_id]}")

        name = generic_task.title.strip()
        parent = cls._parse_parent_(generic_task)
        jira = cls._parse_jira_(generic_task)
        spec = cls._parse_spec_(generic_task)

        return cls(task_id, parent, name, jira, spec)

    @classmethod
    def fetch(cls, validate: bool = True):
        """Download tasks from server, store them to cache and load into application"""

        trace("Fetching tasks...")
        raw_tasks: Sequence[BackendData] = Server.get_tasks()
        CacheManager.save(raw_tasks)

        cls.all.clear()
        for raw_task in raw_tasks:
            generic_task: GenericTask = Adapter.parse_task(raw_task)
            task: Task = cls.gen(generic_task)
            if validate is True:
                task.check_health()

    @classmethod
    def load(cls, validate: bool = True):
        """Load tasks from cache into application"""
        raw_tasks: Sequence[BackendData] = CacheManager.load_tasks()

        cls.all.clear()
        for raw_task in raw_tasks:
            generic_task: GenericTask = Adapter.parse_task(raw_task)
            task: Task = cls.gen(generic_task)
            if validate is True:
                task.check_health()

    def check_health(self) -> bool:
        healthy: bool = True

        if not self.name:
            print(f"[WARNING] Task '{self}': Empty title '{self.name}'")
            healthy = False

        return healthy

    def __post_init__(self):
        self.__class__.all[self.id] = self

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and self.id == other.id

    def __str__(self):
        name = self.name
        if self.spec:
            name = f"({self.spec}) {name}"
        if self.jira:
            name = f"[{self.jira}] {name}"
        return name

    @classmethod
    def _parse_spec_(cls, task: GenericTask) -> Spec | None:
        if task.spec is None:
            return None

        if task.spec in CONFIG.specs:
            return Spec(CONFIG.specs[task.spec])

        if task.spec in CONFIG.specs.values():
            return Spec(task.spec)

        raise BackendDataError(f"Task '{task.id}': invalid spec '{task.spec}'")

    @classmethod
    def _parse_jira_(cls, task: GenericTask) -> Jira | None:
        if task.jira:
            return Jira(task.jira)

        name = task.title.strip()
        if name in CONFIG.tasks:
            jira_id = CONFIG.tasks[name]
            return Jira(jira_id) if jira_id else None

        raise BackendDataError(
            f"Task '{task.id}': Invalid general task name '{task.title}'"
        )

    @classmethod
    def _parse_parent_(cls, task: GenericTask) -> Task | None:
        if not task.parent:
            return None

        if task.parent in cls.all:
            return cls.all[task.parent]

        raise BackendDataError(
            f"Task '{task.id}': Parent id '{task.parent}' not in the list"
        )


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['fetch']:
            credentials = CONFIG.credentials.timecamp
            Server.login(credentials)
            Task.fetch()
            Server.logout()
            print(*Task.all.values(), sep='\n')

        case ['load']:
            print(NotImplemented)

        case _:
            pass
