from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from re import Match, Pattern
from re import compile as compile_regex
from typing import Any, ClassVar, List, NoReturn, Tuple

from alias import Alias
from entry import Entry
from task import Task
from tools import TODAY, AppError, Format


FormatSpec = Tuple[str, Pattern[str]]


class ParseError(AppError):
    pass


def genspec(**kwargs: str) -> List[FormatSpec]:
    return [(name, compile_regex(pattern)) for name, pattern in kwargs.items()]


class Token:
    match: Match[str] | None
    format: str

    formatspec: ClassVar[List[FormatSpec]]

    def __init__(self) -> None:
        self.match = None
        self.format = ''

    def parse(self, string: str, marker: int) -> bool:
        for name, regex in self.formatspec:
            match = regex.match(string, marker)
            if match is not None:
                self.match = match
                self.format = name
                return True
        return False

    def evaluate(self) -> Any:
        assert self.match is not None
        assert self.format is not None
        return self.match[0]

    def handle_unknown_format(self, formatspec: str) -> NoReturn:
        assert self.match
        token = self.__class__.__name__
        raise ParseError(f"Unknown format of '{token}' token: {formatspec}={self.match[0]}")


class Get(Token):
    formatspec = genspec(
        get=r'get',
        load=r'load',
        fetch=r'fetch',
    )


class Node(Token):
    formatspec = genspec(
        alias=r'[A-Za-z]{2}',
    )

    def evaluate(self) -> Entry:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'alias':
                alias = Alias(self.match[0].upper())
                if alias not in Entry.all.keys():
                    raise ParseError(f"No entry with alias '{alias}'")
                return Entry.all[alias]

            case unknown:
                self.handle_unknown_format(unknown)


class Date(Token):
    weeklist: List[str] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    # pylint: disable=consider-using-f-string
    formatspec = genspec(
        date=r'\d{4}-\d{2}-\d{2}',
        day=r'\d{1,2}',
        today=r'today',
        yesterday=r'yesterday',
        week=r'({days})'.format(days='|'.join(weeklist)),
        lastweek=r'last[- ]({days})'.format(days='|'.join(weeklist)),
    )

    @staticmethod
    def _verify_monthday_(monthday: int):
        max_monthday = monthrange(TODAY.year, TODAY.month)[1]
        if monthday > max_monthday:
            raise ParseError(f"Invalid day of the month: {monthday} > {max_monthday}")

    @classmethod
    def _weekday_to_date_(cls, weekday: str) -> date:
        offset = TODAY.weekday() - cls.weeklist.index(weekday)
        return TODAY - timedelta(days=offset)

    def evaluate(self) -> date:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'date':
                return datetime.strptime(self.match[0], Format.YMD).date()

            case 'day':
                monthday = int(self.match[0])
                self._verify_monthday_(monthday)
                return TODAY.replace(day=monthday)

            case 'today':
                return TODAY

            case 'yesterday':
                return TODAY - timedelta(days=1)

            case 'week':
                weekday = self.match[1]
                assert weekday in self.weeklist, f"Invalid weekday name '{weekday}'"
                return self._weekday_to_date_(weekday)

            case 'lastweek':
                weekday = self.match[1]
                assert weekday in self.weeklist, f"Invalid weekday name '{weekday}'"
                return self._weekday_to_date_(weekday) - timedelta(days=7)

            case unknown:
                self.handle_unknown_format(unknown)


class Week(Token):
    formatspec = genspec(
        week=r'week[- ](\d+)',
        thisweek=r'week',
        lastweek=r'last[- ]week',
    )

    @staticmethod
    def _get_monday_() -> date:
        return TODAY - timedelta(days=TODAY.weekday())

    @staticmethod
    def get_work_week(monday: date) -> Tuple[date, date]:
        return monday, monday + timedelta(days=4)

    def evaluate(self) -> date:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'thisweek':
                return self._get_monday_()

            case 'lastweek':
                return self._get_monday_() - timedelta(days=7)

            case 'week':
                offset = int(self.match[1])
                return self._get_monday_() - timedelta(days=7 * offset)

            case unknown:
                self.handle_unknown_format(unknown)


class Time(Token):
    formatspec = genspec(time=r'\d{1,2}:\d{2}')

    def evaluate(self) -> time:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'time':
                return datetime.strptime(self.match[0], Format.HM).time()

            case unknown:
                self.handle_unknown_format(unknown)


class Span(Token):
    formatspec = genspec(
        days=r'(\d+)d',
        hourmin=r'(\d+)h[- ]?(\d+)m',
        hours=r'(\d+)h',
        minutes=r'(\d+)m',
        number=r'(\d+)',
    )

    def evaluate(self) -> timedelta:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'days':
                days = int(self.match[1])
                return timedelta(days=days)

            case 'hourmin':
                hours = int(self.match[1])
                seconds = int(self.match[2]) * 60
                return timedelta(hours=hours, seconds=seconds)

            case 'hours':
                hours = int(self.match[1])
                return timedelta(hours=hours)

            case 'minutes' | 'number':
                seconds = int(self.match[1]) * 60
                return timedelta(seconds=seconds)

            case unknown:
                self.handle_unknown_format(unknown)


class JiraID(Token):
    formatspec = genspec(
        taskname=r'([A-Z0-9]+-\d+)',
    )

    def evaluate(self) -> Task:
        assert self.match is not None
        assert self.format is not None

        target_jira = self.match[1]
        for task in Task.all.values():
            if task.jira == target_jira:
                return task

        raise ParseError(f"Unknown task '{target_jira}'")


class Text(Token):
    formatspec = genspec(
        text=r'.*',
    )


class Num(Token):
    formatspec = genspec(
        text=r'-?\d+',
    )

    def evaluate(self) -> int:
        assert self.match is not None
        assert self.format is not None
        return int(self.match[0])


class Toggle(Token):
    formatspec = genspec(
        on=r'1|ON|YES|Y|TRUE',
        off=r'0|OFF|NO|N|FALSE',
    )

    def evaluate(self) -> bool:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'on':
                return True
            case 'off':
                return False
            case unknown:
                self.handle_unknown_format(unknown)


class Quit(Token):
    formatspec = genspec(
        get=r'x|q|exit|quit',
    )


class TimeList(Token):
    formatspec = genspec(
        list=r'(((\d+(:\d+)?)|-)(, )?)+',
    )

    def parse_time(self, hour_min_time: str) -> timedelta | None:
        if hour_min_time == '-':
            return None
        components = hour_min_time.split(':')
        if len(components) == 1:
            return timedelta(hours=int(components[0]))
        if len(components) == 2:
            hours, minutes = components
            return timedelta(hours=int(hours), minutes=int(minutes))
        raise ParseError(f"Invalid time format: {time}")

    def evaluate(self) -> List[timedelta | None]:
        assert self.match is not None
        assert self.format is not None

        match self.format:
            case 'list':
                items = filter(None, self.match[0].split(', '))
                return [self.parse_time(item) for item in items]

            case unknown:
                self.handle_unknown_format(unknown)
