import random
import string

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import ClassVar, Dict

from backend_adapter import TEntry
from task import Task
from tools import TODAY, AppError, round_bounds, timespan_to_duration


@dataclass(slots=True)
class Entry:
    alias: str = field(init=False, compare=False)
    task: Task
    day: date
    start: time
    span: timedelta
    text: str

    all: ClassVar[Dict[str, 'Entry']] = {}

    @classmethod
    def gen(cls, generic_entry: TEntry) -> 'Entry':
        task_id: int = generic_entry.task
        assert task_id in Task.all

        start: datetime = generic_entry.start
        end: datetime = generic_entry.end
        start, end = round_bounds(start, end)
        assert start.date() <= TODAY
        assert end.date() <= TODAY

        text: str = generic_entry.description

        return cls(Task.all[task_id], start.date(), start.time(), end - start, text)

    def validate(self):
        if not self.text and self.task.jira is not None:
            print(f"WARNING: {self.task.name} ({self.day} {self.start}): no description")

    @property
    def duration(self) -> str:
        return timespan_to_duration(self.span)

    def __post_init__(self):
        self.alias = self.__class__._gen_alias_()
        self.__class__.all[self.alias] = self

    def __str__(self):
        task = self.task.name
        if self.task.jira is not None:
            task = f"[{self.task.jira}] {task}"
        if self.text:
            description = ' | '.join(self.text.splitlines())
            task = f"{task}: {description}"
        start_time = f"{self.start.hour:02}:{self.start.minute:02}"
        return f"{self.alias}: {task} ({self.day} {start_time} {self.duration})"

    def __class_getitem__(cls, alias: str) -> "Entry":
        try:
            return cls.all[alias]
        except KeyError:
            raise AppError(f"No such entry '{alias}'")

    @classmethod
    def _gen_alias_(cls):
        while True:
            alias = str().join(random.choice(string.ascii_uppercase) for char in 'XX')
            if alias not in cls.all.keys():
                return alias
