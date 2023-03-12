import json
import random
import re
import string
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from itertools import groupby
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Pattern, Tuple

from activity import Activity
from api import TEntry
from api import Timeular as server
from config import CONFIG
from tools import AppError, CacheError
from tools import Format, date_range, deprecated, round_time_bounds, timespan_to_duration


@dataclass(slots=True)
class Entry:
    alias: str = field(init=False, compare=False)
    activity: Activity
    start: datetime
    span: timedelta
    text: str

    all: ClassVar[Dict[str, "Entry"]] = {}
    tag_regex: ClassVar[Pattern[str]] = re.compile(r'<{{\|(?P<type>[mt])\|(?P<id>\d+)\|}}>')
    cache: ClassVar[str] = 'timeular-entries-{date}.json'

    def __post_init__(self):
        self.alias = self.__class__._gen_alias_()
        self.__class__.all[self.alias] = self

    def __str__(self):
        jira = self.activity.jira
        task = self.activity.name
        date = self.start.date()
        description = ' | '.join(self.text.splitlines()) or '<None>'
        start_time = f"{self.start.hour:02}:{self.start.minute:02}"
        return f"{self.alias}: [{jira}] {task}: {description} ({date} {start_time} {self.duration})"

    def __class_getitem__(cls, alias: str) -> "Entry":
        try:
            return cls.all[alias]
        except KeyError:
            raise AppError(f"No such entry '{alias}'")

    @classmethod
    def _gen_alias_(cls):
        while True:
            alias = ''.join(random.choice(string.ascii_uppercase) for char in 'AB')
            if alias not in cls.all.keys():
                return alias

    @classmethod
    def _parse_duration_(cls, timeular_entry: TEntry) -> Tuple[datetime, datetime]:
        start = datetime.fromisoformat(timeular_entry['duration']['startedAt'])
        end = datetime.fromisoformat(timeular_entry['duration']['stoppedAt'])
        return tuple(ts.replace(tzinfo=timezone.utc).astimezone() for ts in (start, end))

    @classmethod
    def _parse_tags_(cls, note: Dict[str, Any]) -> str:
        text: str = note['text']
        if text is None:
            return ''
        for tag in note['tags']:
            assert type(tag['id'] is int)
            text = text.replace(f"<{{{{|t|{tag['id']}|}}}}>", tag['label'])
        for mention in note['mentions']:
            assert type(mention['id'] is int)
            text = text.replace(f"<{{{{|m|{mention['id']}|}}}}>", f"@{mention['label']}")
        return text

    @classmethod
    def _gen_entries_(cls, timeular_entries: Iterable[TEntry]):
        for timeular_entry in timeular_entries:
            cls.gen(timeular_entry)

    @classmethod
    def _validate_cache_(cls, day: date, timeular_entries: Iterable[TEntry]):
        start_of_day = (
            datetime.combine(day, time.min).replace(tzinfo=timezone.utc).astimezone()
        )
        end_of_day = (
            datetime.combine(day, time.max).replace(tzinfo=timezone.utc).astimezone()
        )
        for timeular_entry in timeular_entries:
            start, end = cls._parse_duration_(timeular_entry)
            if start < start_of_day or start > end_of_day:
                raise AppError(
                    f"Invalid entry '{timeular_entry.get('id', '<Unknown>')}':"
                    f" start time {start.strftime(Format.YMDHMS)}"
                    f" is outside designated date {day.strftime(Format.YMD)}"
                )
            if end < start_of_day or end > end_of_day:
                raise AppError(
                    f"Invalid entry '{timeular_entry.get('id', '<Unknown>')}':"
                    f" end time {end.strftime(Format.YMDHMS)}"
                    f" is outside designated date {day.strftime(Format.YMD)}"
                )

    @classmethod
    def _update_cache_(cls, day: date, timeular_entries: Iterable[TEntry]):
        cache_file = CONFIG.cache_path / cls.cache.format(date=day.strftime(Format.YMD))
        with cache_file.resolve().open('w', encoding='utf-8') as file:
            json.dump(list(timeular_entries), file, indent=4)

    @classmethod
    def _load_cached_(cls, day: date, validate: bool = True) -> int:
        """Load entries for the specified day from cache into application"""
        cache_file = CONFIG.cache_path / cls.cache.format(date=day.strftime(Format.YMD))
        cache_file = cache_file.resolve()
        if not cache_file.exists():
            raise CacheError(f"Cache miss on {cache_file.name}")
        with cache_file.open(encoding='utf-8') as file:
            timeular_entries = json.load(file)
        if validate:
            cls._validate_cache_(day, timeular_entries)
        cls._gen_entries_(timeular_entries)
        return len(timeular_entries)

    @staticmethod
    def _combine_order_(entry: 'Entry') -> Tuple[date, int, str]:
        return (entry.start.date(), entry.activity.id, entry.text)

    @classmethod
    def gen(cls, timeular_entry: TEntry) -> "Entry":
        activity_id = int(timeular_entry['activityId'])
        activity: Activity = Activity[activity_id]  # type: ignore
        start, end = round_time_bounds(*cls._parse_duration_(timeular_entry))
        text = cls._parse_tags_(timeular_entry['note'])
        if not text and activity.jira is not None:
            print(
                f"WARNING: time entry at {start.date()} {start.time()} has no description"
            )
        return cls(activity, start, end - start, text)

    @classmethod
    def clear_cache(cls, until: date | None = None):
        """Delete cache files with entries older than specified date"""
        date_regex = re.compile(re.sub(r'{(\w*)}', r'(?P<\1>.+?)', cls.cache))
        for entry_cache_file in CONFIG.cache_path.glob(cls.cache.format(date='*')):
            if not entry_cache_file.is_file():
                continue
            if until is not None:
                match = date_regex.fullmatch(entry_cache_file.name)
                if match is None:
                    continue
                day = datetime.strptime(match['date'], Format.YMD)
                if day >= until:
                    continue
            entry_cache_file.unlink()

    @classmethod
    def load(
        cls, since: date, until: date, validate: bool = True, ignore_missing: bool = False
    ) -> int:
        """Load entries from cache into application"""
        loaded = 0
        cls.all.clear()
        for day in date_range(since, until):
            try:
                loaded += cls._load_cached_(day, validate)
            except CacheError as error:
                if ignore_missing is False:
                    raise error
        return loaded

    @classmethod
    def load_all(cls) -> int:
        """Load entries from all cache files into application"""
        loaded = 0
        cls.all.clear()
        for cache_file in CONFIG.cache_path.glob(cls.cache.format(date='*')):
            with cache_file.open(encoding='utf-8') as file:
                timeular_entries = json.load(file)
            cls._gen_entries_(timeular_entries)
            loaded += len(timeular_entries)
        return loaded

    @classmethod
    def fetch(cls, since: date, until: date) -> int:
        """Download entries from server, store them to cache and load into application"""
        start = datetime.combine(since, time.min)
        end = datetime.combine(until, time.max)

        timeular_entries = server.get_entries(start, end)

        timeular_entries.sort(key=cls._parse_duration_)
        group_by_date: Callable[[TEntry], date] = lambda item: cls._parse_duration_(item)[
            0
        ].date()
        entries_grouper = groupby(timeular_entries, key=group_by_date)

        created = 0
        cls.all.clear()
        for day, entries in entries_grouper:
            daily_entries = list(entries)
            cls._update_cache_(day, daily_entries)
            cls._gen_entries_(daily_entries)
            created += len(daily_entries)
        return created

    @classmethod
    def combine(cls, entries: Iterable['Entry']) -> int:
        deleted = 0
        sorted_entries: List[Entry] = sorted(entries, key=cls._combine_order_)
        for key, entries_to_combine in groupby(sorted_entries, key=cls._combine_order_):
            entries_to_combine = sorted(entries_to_combine, key=lambda e: e.start)
            total_duration = sum(
                (entry.span for entry in entries_to_combine), start=timedelta()
            )
            entries_to_combine[0].span = total_duration
            for entry in entries_to_combine[1:]:
                entry.delete()
                deleted += 1
        return deleted

    @classmethod
    def combine_all(cls) -> int:
        return cls.combine(cls.all.values())

    @classmethod
    def combine_for(cls, since: date, until: date) -> int:
        filter_by_interval: Callable[[Entry], bool] = (
            lambda e: since <= e.start.date() <= until
        )
        return cls.combine(filter(filter_by_interval, Entry.all.values()))

    @property
    def duration(self):
        return timespan_to_duration(self.span)

    def delete(self):
        del self.__class__.all[self.alias]

    def fix_whitespace(self) -> bool:
        fixed_text, count = re.subn(r' +', ' ', self.text)
        if count > 0:
            self.text = fixed_text
            return True
        return False

    @deprecated
    def get_duration(self):
        hours, minutes, seconds = str(self.span).split(':')
        if self.span.days > 1:
            hours = int(hours.split()[-1]) + 24 * self.span.days
        h = f'{hours}h' if int(hours) else ''
        m = f'{minutes}m' if int(minutes) else ''
        return f"{h} {m}".strip()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if mode == 'fetch':
        server.login(CONFIG.timeular['key'], CONFIG.timeular['secret'])
        Activity.fetch()
        Entry.fetch(since=date(2022, 8, 1), until=date(2022, 8, 7))
        server.logout()
        print(*Entry.all.values(), sep='\n')

    if mode == 'load':
        Activity.load()
        Entry.load(since=date(2022, 8, 1), until=date(2022, 8, 5))
        print(*Entry.all.values(), sep='\n')

    if mode == 'list':
        Activity.load()
        Entry.load_all()
        entries = sorted(Entry.all.values(), key=lambda entry: entry.start)
        print(*entries, sep='\n')

    if mode == 'test':
        server.login(CONFIG.timeular['key'], CONFIG.timeular['secret'])
        Activity.fetch()
