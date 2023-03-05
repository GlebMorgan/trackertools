from dataclasses import dataclass
from typing import ClassVar, Dict

from backend_adapter import TTask


@dataclass(frozen=True, slots=True)
class Task:
    id: int
    parent: 'Task' | None
    name: str
    jira: str | None
    spec: str | None

    all: ClassVar[Dict[int, 'Task']] = {}

    @classmethod
    def gen(cls, generic_task: TTask) -> 'Task':
        """Draft"""
        id: int = generic_task.id

        if generic_task.parent is not None:
            parent = cls.all[generic_task.parent]
        else:
            parent = None

        if id in cls.all:
            raise RuntimeError(f"Activity with {id=} already exists: {cls.all[id]}")
        return cls(id, parent, generic_task.title, generic_task.jira, generic_task.spec)

    def __post_init__(self):
        self.__class__.all[self.id] = self

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and self.id == other.id

    def __str__(self):
        spec = f'({self.spec})' if self.spec else None
        return ' '.join(filter(None, (self.jira, self.name, spec)))
