from calendar import monthrange
from datetime import date, datetime, time, timedelta
from re import Match, Pattern, compile
from typing import Any, ClassVar, Dict, List, Tuple

from activity import Activity
from entry import Entry
from tools import TODAY, AppError, Format, ParseError


Spec = Tuple[str, Pattern[str]]


def genspec(**kwargs: str) -> List[Spec]:
    return [(name, compile(pattern)) for name, pattern in kwargs.items()]


class Token:
    formats: Dict[str, str]
    formatspec: ClassVar[List[Spec]]

    match: Match[str]|None
    format: str|None

    def __init__(self) -> None:
        self.match = None
        self.format = None

    def parse(self, input: str, marker: int) -> bool:
        for name, regex in self.formatspec:
            match = regex.match(input, marker)
            if match is not None:
                self.match = match
                self.format = name
                return True
        return False

    def evaluate(self) -> Any:
        if self.match is None or self.format is None:
            raise RuntimeError("Evaluating token which does not have a match")
        return self.match[0]


class Get(Token):
    formatspec = genspec(
        get   = r'get',
        load  = r'load',
        fetch = r'fetch',
    )


class Node(Token):
    formatspec = genspec(
        alias = r'[A-Za-z]{2}',
    )

    def evaluate(self) -> Entry:
        super().evaluate()
        self.match: Match[str]

        match self.format:
            case 'alias':
                alias = self.match[0].upper()
                if alias not in Entry.all.keys():
                    raise ParseError(f"No entry with alias '{alias}' exists")
                return Entry[alias]  # type: ignore

            case other:
                assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Date(Token):
    weeklist: List[str] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    formatspec = genspec(
        date      = r'\d{4}-\d{2}-\d{2}',
        day       = r'\d{1,2}',
        today     = r'today',
        yesterday = r'yesterday',
        week      = r'({days})'.format(days='|'.join(weeklist)),
        lastweek  = r'last[- ]({days})'.format(days='|'.join(weeklist)),
    )

    @staticmethod
    def _verify_monthday_(monthday: int):
        max_monthday = monthrange(TODAY.year, TODAY.month)[1]
        if monthday > max_monthday:
            raise ParseError(f"Day of the month exceeds maximum: {monthday} > {max_monthday}")

    @classmethod
    def _weekday_to_date_(cls, weekday: str) -> date:
        offset = TODAY.weekday() - cls.weeklist.index(weekday)
        return TODAY - timedelta(days=offset)

    def evaluate(self) -> date:
        super().evaluate()
        self.match: Match[str]

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
                return self.__class__._weekday_to_date_(weekday)

            case 'lastweek':
                weekday = self.match[1]
                assert weekday in self.weeklist, f"Invalid weekday name '{weekday}'"
                return self.__class__._weekday_to_date_(weekday) - timedelta(days=7)

            case other:
                assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Week(Token):
    formatspec = genspec(
        thisweek = r'week',
        lastweek = r'last[- ]week',
        week     = r'week[- ](\d)',
    )

    @staticmethod
    def _get_monday_() -> date:
        return TODAY - timedelta(days=TODAY.weekday())

    @staticmethod
    def get_work_week(monday: date) -> Tuple[date, date]:
        return monday, monday + timedelta(days=4)

    def evaluate(self) -> date:
        super().evaluate()
        self.match: Match[str]

        match self.format:
            case 'thisweek':
                return self._get_monday_()

            case 'lastweek':
                return self._get_monday_() - timedelta(days=7)

            case 'week':
                offset = int(self.match[1])
                return self._get_monday_() - timedelta(days=7*offset)

            case other:
                assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Time(Token):
    formatspec = genspec(
        time = r'\d{1,2}:\d{2}'
    )

    def evaluate(self) -> time:
        super().evaluate()
        self.match: Match[str]

        match self.format:
            case 'time':
                return datetime.strptime(self.match[0], Format.HM).time()

            case other:
                assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Span(Token):
    formatspec = genspec(
        days = r'(\d+)d',
        hourmin = r'(\d+)h[- ]?(\d+)m',
        hours   = r'(\d+)h',
        minutes = r'(\d+)m',
        number  = r'(\d+)',
    )

    def evaluate(self) -> timedelta:
        super().evaluate()
        self.match: Match[str]

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

            case other:
                assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Task(Token):
    formatspec = genspec(
        taskname = r'\[(\w+)\]',
    )

    def evaluate(self) -> Activity:
        super().evaluate()
        self.match: Match[str]

        target_name = self.match[1]
        for activity in Activity.all.values():
            if activity.name == target_name:
                return activity

        raise AppError(f"Unknown activity '{target_name}'")


class Text(Token):
    formatspec = genspec(
        text = r'.*',
    )


class Num(Token):
    formatspec = genspec(
        text = r'-?\d+',
    )

    def evaluate(self) -> int:
        super().evaluate()
        self.match: Match[str]
        return int(self.match[0])


class Toggle(Token):
    formatspec = genspec(
        on  = r'1|ON|YES|Y|TRUE',
        off = r'0|OFF|NO|N|FALSE'
    )

    def evaluate(self) -> bool:
        super().evaluate()
        self.match: Match[str]

        match self.format:
            case 'on': return True
            case 'off': return False
            case other: assert False, f"Unknown format of '{self.__class__.__name__}' token: {other}={self.match[0]}"


class Quit(Token):
    formatspec = genspec(
        get = r'x|q|exit|quit',
    )
