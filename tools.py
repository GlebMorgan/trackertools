import sys

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple

from decorator import decorator


TODAY = date.today()

Config = Dict[str, int | str | bool | Path | dict[str, 'Config'] | None]
Method = Callable[..., Any]


class Format:
    HM = '%H:%M'
    HMS = '%H:%M:%S'
    YMD = '%Y-%m-%d'
    YMDHM = '%Y-%m-%d %H:%M'
    YMDHMS = '%Y-%m-%d %H:%M:%S'


class ConfigDict(dict[str, Any]):
    __slots__ = ()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        for name, value in self.items():
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
    return s


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


def timespan_to_duration(timespan: timedelta) -> str:
    """Convert `timedelta` object to string of hour-minute format: 'Xh Ym'"""
    seconds = int(timespan.total_seconds())
    hours = seconds // 60 // 60
    minutes = (seconds // 60) % 60
    components = dict(h=hours, m=minutes)
    return ' '.join(str(value) + marker for marker, value in components.items() if value)


def date_range(start: date, end: date) -> Iterable[date]:
    return (start + timedelta(days=x) for x in range((end - start).days + 1))


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['round-bounds']:
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

            for start, end, start_ref, end_ref in round_time_tests:
                start_round, end_round = round_bounds(start, end)
                assert start_round == start_ref, f"{start=}, {start_ref=}, {start_round=}"
                assert end_round == end_ref, f"{end = }, {end_ref = }, {end_round = }"

            print("'round_bounds()' tests passed")

        case other:
            pass
