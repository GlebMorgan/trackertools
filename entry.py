from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import count as counter
from itertools import groupby
from typing import Callable, ClassVar, Iterable, NewType, Self, Sequence

from adapter import GenericEntry
from alias import Alias
from api import BackendData
from cache import CacheManager
from config import CONFIG, trace
from jira_client import Jira
from jira_formatter import JiraFormatter
from task import Task
from tools import TODAY, Format, first_word, round_bounds, timespan_to_duration


match CONFIG.backend:
    case 'timecamp':
        from timecamp_adapter import TimecampAdapter as Adapter
        from timecamp_api import Timecamp as Server
    case 'timeular':
        from timeular_adapter import TimeularAdapter as Adapter
        from timeular_api import Timeular as Server
    case other:
        raise ImportError(f"Invalid backend config: '{other}'")


EntryId = NewType("EntryId", int)


@dataclass(slots=True)
class Entry:
    alias: Alias = field(init=False, compare=False)
    id: EntryId = field(compare=False)
    task: Task
    start: datetime
    end: datetime
    text: str
    markup: str | None = None
    worklog_id: int = 0

    all: ClassVar[dict[Alias, Entry]] = {}
    formatter: ClassVar[JiraFormatter] = JiraFormatter()

    @property
    def day(self) -> date:
        return self.start.date()

    @property
    def span(self) -> timedelta:
        return self.end - self.start

    @property
    def duration(self) -> str:
        return timespan_to_duration(self.span)

    @property
    def description(self) -> str:
        description = self.markup if self.markup is not None else self.text
        return ' | '.join(description.splitlines())

    @classmethod
    def gen(cls, generic_entry: GenericEntry) -> Entry:
        task_id: int = generic_entry.task
        assert task_id in Task.all

        start, end = round_bounds(generic_entry.start, generic_entry.end)
        assert start <= end

        entry_id: int = generic_entry.id
        text: str = generic_entry.description

        return cls(EntryId(entry_id), Task.all[task_id], start, end, text)

    @classmethod
    def fetch(cls, since: date, until: date, validate: bool = True):
        """Download entries from server, store them to cache and load into application"""

        trace(f"Fetching entries for {(until-since).days} days...")
        raw_entries: Sequence[BackendData] = Server.get_entries(since, until)
        CacheManager.save(raw_entries)
        cls._reload_(raw_entries, check_health=validate)

    @classmethod
    def load(cls, since: date, until: date, validate: bool = True):
        """Load entries from cache into application"""
        raw_entries: Sequence[BackendData] = CacheManager.load_entries(since, until)
        cls._reload_(raw_entries, check_health=validate)

    @classmethod
    def combine(cls, entries: Iterable[Entry]) -> int:
        deleted = 0

        sorted_entries: list[Entry] = sorted(entries, key=cls._grouping_order_)
        for key, group in groupby(sorted_entries, key=cls._grouping_order_):
            fragments: list[Entry] = sorted(group, key=lambda e: e.start)
            total_duration: timedelta = sum((e.span for e in fragments), start=timedelta())
            composite_entry = fragments[0]
            composite_entry.end = composite_entry.start + total_duration
            for entry in fragments[1:]:
                entry.delete()
                deleted += 1

        return deleted

    @classmethod
    def combine_for(cls, since: date, until: date) -> int:
        range_filter: Callable[[Entry], bool] = lambda e: since <= e.start.date() <= until
        return cls.combine(filter(range_filter, Entry.all.values()))

    @classmethod
    def all_tasks(cls) -> list[Task]:
        tasks: list[Task] = []
        for entry in cls.all.values():
            if all(task.jira != entry.task.jira for task in tasks):
                tasks.append(entry.task)
        return tasks

    def logged(self) -> bool:
        return self.worklog_id != 0

    def formatted(self) -> bool:
        return self.markup is not None

    def delete(self):
        del self.__class__.all[self.alias]

    @classmethod
    def _reload_(cls, raw_entries: Sequence[BackendData], *, check_health: bool):
        cls.all.clear()
        for raw_entry in raw_entries:
            generic_entry: GenericEntry = Adapter.parse_entry(raw_entry)

            if generic_entry.task == 0:
                # Drop entries without a task silently
                # This can happen with Timecamp, when entry is created accidentally
                # TODO: Consider moving this to _check_health_() + make sure gen() is happy
                print(f"[WARNING] Entry at {generic_entry.start:{Format.WHM}} has no task")
                continue

            entry: Entry = cls.gen(generic_entry)

            if check_health is True:
                entry._check_health_()

    def _check_health_(self) -> bool:
        healthy: bool = True
        if not self.text and self.task.name not in CONFIG.tasks:
            print(f"[WARNING] Entry '{self}' has no description")
            healthy = False
        if self.start.date() > TODAY or self.end.date() > TODAY:
            print(f"[WARNING] Entry '{self}' day is invalid: {self.day}")
            healthy = False
        if self.start.date() != self.end.date():
            print(f"[WARNING] Entry '{self}' spans across multiple days")
            healthy = False
        if any(first_word(line).endswith('ing') for line in self.text.splitlines()):
            print(f"[WARNING] Entry '{self}' description is not imperative")
            healthy = False
        if self.task.name == "MR" and not self.text:
            print(f"[WARNING] Entry '{self}' is missing MR link")
            healthy = False
        return healthy

    def fix_whitespace(self) -> bool:
        fixed_text, count = re.subn(r' {2,}', ' ', self.text)
        if count > 0:
            self.text = fixed_text
            return True
        return False

    @classmethod
    def gen_id(cls, reference: Self) -> EntryId:
        for i in counter(1):
            new_id = EntryId(reference.id + i)
            if all(entry.id != new_id for entry in cls.all.values()):
                return new_id
        return EntryId(reference.id)

    def gen_markup(self) -> bool:
        self.markup = self.formatter.format(self.task, self.text)
        return bool(self.markup)

    def log_to_jira(self) -> bool:
        if self.task.jira is None:
            print(f"[ERROR] Entry '{self}' has no Jira task")
            return False

        if self.markup is None:
            print(f"[ERROR] Entry '{self}' is not formatted")
            return False

        worklog = Jira.add_worklog(self.task.jira, self.duration, self.start, self.markup)

        if worklog is None:
            return False

        self.worklog_id = worklog.id
        return True

    def remove_jira_log(self) -> bool:
        if self.task.jira is None:
            print(f"[ERROR] Entry '{self}' has no Jira task")
            return False

        if self.logged() is False:
            return False

        Jira.delete_worklog(self.task.jira, self.worklog_id)

        self.worklog_id = 0
        return True

    def __post_init__(self):
        self.alias = self._gen_alias_()
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

    def _gen_alias_(self, entry_id: int | None = None) -> Alias:
        seed = entry_id or self.id
        alias = Alias.gen(seed)
        if alias in self.all.keys():
            return self._gen_alias_(seed + 1)
        return alias

    @staticmethod
    def _grouping_order_(entry: Entry) -> tuple[date, int, str]:
        return (entry.start.date(), entry.task.id, entry.text)


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['fetch']:
            credentials = CONFIG.credentials.timecamp
            Server.login(credentials)
            Task.fetch()
            Entry.fetch(since=date(2023, 3, 6), until=date(2023, 3, 7))
            Server.logout()
            print(*Entry.all.values(), sep='\n')

        case ['load']:
            print(NotImplemented)

        case _:
            pass
