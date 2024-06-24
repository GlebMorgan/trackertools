from __future__ import annotations

import random
import re
import string
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import groupby
from typing import Callable, ClassVar, Dict, Iterable, List, NewType, Sequence, Tuple

from adapter import GenericEntry
from api import BackendData
from cache import CacheManager
from config import CONFIG, trace
from jira_formatter import JiraFormatter
from task import Task
from tools import TODAY, first_word, round_bounds, timespan_to_duration


match CONFIG.backend:
    case 'timecamp':
        from timecamp_adapter import TimecampAdapter as Adapter
        from timecamp_api import Timecamp as Server
    case 'timeular':
        from timeular_adapter import TimeularAdapter as Adapter
        from timeular_api import Timeular as Server
    case other:
        raise ImportError(f"Invalid backend config: '{other}'")


Alias = NewType("Alias", str)


@dataclass(slots=True)
class Entry:

    alias: Alias = field(init=False, compare=False)
    task: Task
    start: datetime
    end: datetime
    text: str
    markup: str | None = None
    worklog_id: int = 0

    all: ClassVar[Dict[Alias, Entry]] = {}
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

    @classmethod
    def gen(cls, generic_entry: GenericEntry) -> Entry:
        task_id: int = generic_entry.task
        assert task_id in Task.all

        start, end = round_bounds(generic_entry.start, generic_entry.end)
        assert start <= end

        text: str = generic_entry.description

        return cls(Task.all[task_id], start, end, text)

    @classmethod
    def fetch(cls, since: date, until: date, validate: bool = True):
        """Download entries from server, store them to cache and load into application"""

        trace(f"Fetching entries for {(until-since).days} days...")
        raw_entries: Sequence[BackendData] = Server.get_entries(since, until)
        CacheManager.save(raw_entries)

        cls.all.clear()
        for raw_entry in raw_entries:
            generic_entry: GenericEntry = Adapter.parse_entry(raw_entry)

            if generic_entry.task == 0:
                # Drop entries without a task silently
                # This can happen with Timecamp, when entry is created accidentally
                continue

            entry: Entry = cls.gen(generic_entry)
            if validate is True:
                entry.check_health()

    @classmethod
    def load(cls, since: date, until: date, validate: bool = True):
        """Load entries from cache into application"""
        raw_entries: Sequence[BackendData] = CacheManager.load_entries(since, until)

        cls.all.clear()
        for raw_entry in raw_entries:
            generic_entry: GenericEntry = Adapter.parse_entry(raw_entry)
            if cls._within_dates_(generic_entry.start, generic_entry.end, since, until):
                entry: Entry = cls.gen(generic_entry)
                if validate is True:
                    entry.check_health()

    @classmethod
    def combine(cls, entries: Iterable[Entry]) -> int:
        deleted = 0

        sorted_entries: List[Entry] = sorted(entries, key=cls._grouping_order_)
        for key, group in groupby(sorted_entries, key=cls._grouping_order_):
            fragments: List[Entry] = sorted(group, key=lambda e: e.start)
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

    def logged(self) -> bool:
        return self.worklog_id != 0

    def formatted(self) -> bool:
        return self.markup is not None

    def delete(self):
        del self.__class__.all[self.alias]

    def check_health(self) -> bool:
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
        if first_word(self.text).endswith('ing'):
            print(f"[WARNING] Entry '{self}' description is not imperative")
            healthy = False
        if self.task.name.startswith("Sprint") and not self.text:
            print(f"[WARNING] Entry '{self}' is missing sprint number")
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

    def gen_markup(self) -> bool:
        self.markup = self.formatter.format(self.task, self.text)
        return True if self.markup else False

    def __post_init__(self):
        self.alias = Alias(self._gen_alias_())
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

    @classmethod
    def _gen_alias_(cls):
        while True:
            alias = str().join(random.choice(string.ascii_uppercase) for char in 'XX')
            if alias not in cls.all.keys():
                return alias

    @staticmethod
    def _within_dates_(start: datetime, end: datetime, first: date, last: date) -> bool:
        return first <= start.date() <= last or first <= end.date() <= last

    @staticmethod
    def _grouping_order_(entry: Entry) -> Tuple[date, int, str]:
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
