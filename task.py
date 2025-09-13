from __future__ import annotations

from enum import Enum
import sys
from dataclasses import dataclass
from typing import ClassVar, Dict, NewType, Sequence

from adapter import BackendDataError, GenericTask
from api import BackendData
from cache import CacheManager
from config import CONFIG, trace
from jira_client import Jira, TimeEstimate


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
JiraId = NewType("JiraId", str)
Spec = NewType("Spec", str)


class TaskType(Enum):
    TICKET = 'ticket'
    GENERAL = 'general'
    PERSONAL = 'personal'


@dataclass
class Task:
    id: TaskId
    name: str
    parent: Task | None
    type: TaskType
    jira: JiraId | None
    spec: Spec | None

    all: ClassVar[Dict[TaskId, Task]] = {}

    @property
    def timetracking(self) -> TimeEstimate | None:
        if self.jira is None:
            return None
        return Jira.get_timetracking(self.jira)

    @classmethod
    def gen(cls, generic_task: GenericTask) -> Task:
        task_id = TaskId(generic_task.id)
        if task_id in cls.all:
            raise RuntimeError(f"Task '{task_id}': already exists: {cls.all[task_id]}")

        name = generic_task.title
        parent = cls._parse_parent_(generic_task)
        ttype = cls._parse_type_(generic_task)
        jira = cls._parse_jira_(generic_task)
        spec = cls._parse_spec_(generic_task)

        return cls(task_id, name, parent, ttype, jira, spec)

    @classmethod
    def fetch(cls, validate: bool = True):
        """Download tasks from server, store them to cache and load into application"""
        trace("Fetching tasks...")
        raw_tasks: Sequence[BackendData] = Server.get_tasks()
        CacheManager.save(raw_tasks)
        cls._reload_(raw_tasks, check_health=validate)

    @classmethod
    def load(cls, validate: bool = True):
        """Load tasks from cache into application"""
        raw_tasks: Sequence[BackendData] = CacheManager.load_tasks()
        cls._reload_(raw_tasks, check_health=validate)

    @classmethod
    def _reload_(cls, raw_tasks: Sequence[BackendData], *, check_health: bool):
        cls.all.clear()
        for raw_task in raw_tasks:
            generic_task: GenericTask = Adapter.parse_task(raw_task)
            task: Task = cls.gen(generic_task)
            if check_health is True:
                task._check_health_()

    def _check_health_(self) -> bool:
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
    def _parse_type_(cls, task: GenericTask) -> TaskType:
        task_type: str | None = task.properties.get('type')
        if task_type is None:
            return TaskType.TICKET

        if any(task_type == item.value for item in TaskType) is False:
            raise BackendDataError(f"Task '{task.title}': invalid type '{task_type}'")

        return TaskType(task_type)

    @classmethod
    def _parse_spec_(cls, task: GenericTask) -> Spec | None:
        spec: str | None = task.properties.get('spec')
        if spec is None:
            return None

        if spec not in CONFIG.specs:
            raise BackendDataError(f"Task '{task.title}': invalid spec '{spec}'")

        return Spec(CONFIG.specs[spec])

    @classmethod
    def _parse_jira_(cls, task: GenericTask) -> JiraId | None:
        jira: str | None = task.properties.get('jira')
        return JiraId(jira) if jira else None

    @classmethod
    def _parse_parent_(cls, task: GenericTask) -> Task | None:
        if not task.parent:
            return None

        if task.parent not in cls.all:
            raise BackendDataError(
                f"Task '{task.title}': Parent id '{task.parent}' not in the list"
            )

        return cls.all[TaskId(task.parent)]


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
