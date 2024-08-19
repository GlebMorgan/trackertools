from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple

from decorator import decorator


TODAY = date.today()
CURRENT_TZ = datetime.now().astimezone().tzinfo

Config = Dict[str, int | str | bool | Path | dict[str, 'Config'] | None]
Method = Callable[..., Any]


class Format:
    HM = '%H:%M'
    HMS = '%H:%M:%S'
    YMD = '%Y-%m-%d'
    YMDHM = '%Y-%m-%d %H:%M'
    YMDHMS = '%Y-%m-%d %H:%M:%S'
    WHM = '%a %H:%M'


class AttrDict(dict[str, Any]):
    __slots__ = ()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        for name, value in self.items():
            # pylint: disable=unidiomatic-typecheck
            if type(value) is dict:
                self[name] = self.__class__(value)

    def __getattr__(self, *args: Any, **kwargs: Any):
        return super().__getitem__(*args, **kwargs)

    def __setattr__(self, *args: Any, **kwargs: Any):
        raise AttributeError(f"'{self.__class__.__name__}' object is read-only")


class AppError(RuntimeError):
    pass


def noop(*args: Any, **kwargs: Any):
    pass


@decorator
def deprecated(func: Method, *args: Any, **kwargs: Any):
    print(f"WARNING: function '{func.__name__}' is deprecated")
    return func(*args, **kwargs)


def unwrap(s: str) -> str:
    """Remove wrapping braces from string"""
    for brackets in zip('{([{', '}])}'):
        if s[0] == brackets[0] and s[-1] == brackets[1]:
            s = s[1:-1]
    return s.strip()


def quoted(strings: Iterable[str]) -> Iterable[str]:
    yield from (f"'{s}'" for s in strings)


def round_time(dt: datetime, to: int = 5) -> datetime:
    """Round a datetime object to any interval in min"""
    rounding = to * 60
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounded = (seconds + rounding / 2) // rounding * rounding
    return dt + timedelta(0, rounded - seconds, -dt.microsecond)


def round_bounds(start: datetime, end: datetime, to: int = 5) -> Tuple[datetime, datetime]:
    assert start <= end
    rounding = to * 60

    start_seconds = (start.replace(tzinfo=None) - datetime.min).seconds
    end_seconds = (end.replace(tzinfo=None) - datetime.min).seconds

    start_rounded = (start_seconds + rounding // 2) // rounding * rounding
    start_shift = start_seconds - start_rounded
    end_rounded = (end_seconds + rounding // 2) // rounding * rounding
    end_shift = end_seconds - end_rounded

    if abs(start_shift) < abs(end_shift):
        end_rounded = ((end_seconds - start_shift) + rounding // 2) // rounding * rounding
    else:
        start_rounded = ((start_seconds - end_shift) + rounding // 2) // rounding * rounding

    return (
        start + timedelta(0, start_rounded - start_seconds, -start.microsecond),
        end + timedelta(0, end_rounded - end_seconds, -end.microsecond),
    )


def seconds_to_duration(total_seconds: int) -> str:
    """Convert seconds to string of hour-minute format: '##h ##m'"""
    if total_seconds == 0:
        return "0m"

    minutes, seconds = divmod(abs(total_seconds), 60)
    hours, minutes = divmod(minutes, 60)

    components = {"h": hours, "m": minutes}
    string = ' '.join(str(value) + marker for marker, value in components.items() if value)

    if total_seconds < 0:
        string = '-' + string
    return string


def timespan_to_duration(timespan: timedelta) -> str:
    """Convert `timedelta` object to string of hour-minute format: '##h ##m'"""
    return seconds_to_duration(int(timespan.total_seconds()))


def date_range(start: date, end: date) -> Iterable[date]:
    return (start + timedelta(days=x) for x in range((end - start).days + 1))


def constrict(string: str, *, width: int) -> str:
    if len(string) > width:
        string = string[: width - 3] + '...'
    return string


def constricted_repr(mapping: dict[str, Any], width: int) -> str:
    attrs: list[str] = []
    for key, value in mapping.items():
        attrs.append(f"{key!r}: {value!r}")
        representation = ", ".join(attrs)
        if len(representation) > width:
            attrs[-1] = "..."
            break
    return "{" + ", ".join(attrs) + "}"


def first_word(string: str) -> str:
    try:
        return string.split(maxsplit=1)[0]
    except IndexError:
        return ""


if __name__ == '__main__':

    def test_round_bounds():
        # fmt: off
        round_time_tests = [
            (
                datetime(2022, 12, 31, 9, 10, 0), datetime(2022, 12, 31, 9, 50, 0),
                datetime(2022, 12, 31, 9, 10, 0), datetime(2022, 12, 31, 9, 50, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 7, 30), datetime(2022, 12, 31, 9, 27, 30),
                datetime(2022, 12, 31, 9, 10, 0), datetime(2022, 12, 31, 9, 30, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 30, 2), datetime(2022, 12, 31, 9, 30, 2),
                datetime(2022, 12, 31, 9, 30, 0), datetime(2022, 12, 31, 9, 30, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 1, 42), datetime(2022, 12, 31, 9, 22, 1),
                datetime(2022, 12, 31, 9, 0, 0),  datetime(2022, 12, 31, 9, 20, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 1, 42), datetime(2022, 12, 31, 9, 22, 55),
                datetime(2022, 12, 31, 9, 0, 0),  datetime(2022, 12, 31, 9, 20, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 4, 42), datetime(2022, 12, 31, 9, 17, 45),
                datetime(2022, 12, 31, 9, 5, 0),  datetime(2022, 12, 31, 9, 20, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 4, 42), datetime(2022, 12, 31, 9, 17, 25),
                datetime(2022, 12, 31, 9, 5, 0),  datetime(2022, 12, 31, 9, 20, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 9, 30), datetime(2022, 12, 31, 9, 30, 45),
                datetime(2022, 12, 31, 9, 10, 0), datetime(2022, 12, 31, 9, 30, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 12, 40), datetime(2022, 12, 31, 9, 30, 45),
                datetime(2022, 12, 31, 9, 10, 0),  datetime(2022, 12, 31, 9, 30, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 10, 40), datetime(2022, 12, 31, 9, 44, 45),
                datetime(2022, 12, 31, 9, 10, 0),  datetime(2022, 12, 31, 9, 45, 0)
            ),
            (
                datetime(2022, 12, 31, 9, 7, 25), datetime(2022, 12, 31, 9, 44, 45),
                datetime(2022, 12, 31, 9, 10, 0), datetime(2022, 12, 31, 9, 45, 0)
            ),
        ]
        # fmt: on

        for start_time, end_time, start_ref, end_ref in round_time_tests:
            start_round, end_round = round_bounds(start_time, end_time)
            assert start_round == start_ref, f"{start_time=}, {start_ref=}, {start_round=}"
            assert end_round == end_ref, f"{end_time = }, {end_ref = }, {end_round = }"

        print("'round_bounds()' tests passed")

    match sys.argv[1:]:
        case ['round-bounds']:
            test_round_bounds()

        case _:
            pass
