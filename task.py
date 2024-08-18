from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, NewType, Self, Sequence

from adapter import BackendDataError, GenericTask
from api import BackendData
from cache import CacheManager
from config import CONFIG, ConfigError, trace
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


@dataclass
class Task:
    id: TaskId
    parent: Task | None
    name: str
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
        TaskDescriptor.validate()

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
    def _parse_spec_(cls, task: GenericTask) -> Spec | None:
        if task.spec is None:
            return None

        if task.spec in CONFIG.specs:
            return Spec(CONFIG.specs[task.spec])

        if task.spec in CONFIG.specs.values():
            return Spec(task.spec)

        raise BackendDataError(f"Task '{task.id}': invalid spec '{task.spec}'")

    @classmethod
    def _parse_jira_(cls, task: GenericTask) -> JiraId | None:
        if task.jira:
            return JiraId(task.jira)

        if task.id not in TaskDescriptor.descriptors:
            raise ConfigError(f"Task '{task.title}' (ID={task.id}) missing in config")

        jira_id = TaskDescriptor.descriptors[task.id].jira
        return JiraId(jira_id) if jira_id else None

    @classmethod
    def _parse_parent_(cls, task: GenericTask) -> Task | None:
        if not task.parent:
            return None

        if task.parent in cls.all:
            return cls.all[task.parent]

        raise BackendDataError(
            f"Task '{task.id}': Parent id '{task.parent}' not in the list"
        )


@dataclass(slots=True, frozen=True)
class TaskDescriptor:
    id: int
    name: str
    space: str
    jira: str | None

    descriptors: ClassVar[dict[int, Self]] = {}

    @classmethod
    def load_from_config(cls, config: dict[str, dict[str, dict[str, Any]]]):
        for space, task_specs in config.items():
            assert isinstance(task_specs, dict)
            for spec in task_specs.values():
                assert isinstance(spec, dict)
                assert all(attr in spec for attr in ('id', 'task', 'jira'))
                cls(int(spec['id']), spec['task'], space, spec['jira'])

    @classmethod
    def validate(cls):
        for descriptor in cls.descriptors.values():
            if descriptor.id not in Task.all:
                raise ConfigError(f"Unknown task: '{descriptor.name}' (ID={descriptor.id})")

            task = Task.all[descriptor.id]
            if not descriptor.validate_name(task):
                raise ConfigError(
                    f"Task name mismatch: server='{task.name}', config='{descriptor.name}'"
                )
            if not descriptor.validate_space(task):
                raise ConfigError(
                    f"Task '{descriptor.name}' (ID={descriptor.id}) "
                    f"has invalid space '{descriptor.space}'"
                )

    def validate_name(self, task: Task) -> bool:
        return self.name == task.name

    def validate_space(self, task: Task | None) -> bool:
        while task is not None:
            if self.space == task.name:
                return True
            task = task.parent
        return False

    def __post_init__(self):
        self.__class__.descriptors[self.id] = self


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
