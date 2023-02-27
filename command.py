from datetime import date, time, timedelta
from enum import Enum
from itertools import groupby
from operator import itemgetter
from parser import Date, Get, Node, Quit, Span, Task, Text, Time, Toggle, Token, Week
from typing import Callable, ClassVar, Dict, List, Literal, Tuple, Type

from activity import Activity
from api import Timeular as server
from config import CONFIG
from entry import Entry
from table import Table
from tools import AppError, Format, deprecated, noop, timespan_to_duration


Handler = Callable[..., None]
CmdPattern = List[Type[Token]|str]
LoadMethod = Literal['get', 'load', 'fetch']


log = print if CONFIG.debug is True else noop
backend: dict[str, str] = CONFIG[CONFIG.backend]


class Group(Enum):
    Show = 'show'
    Load = 'get'
    Delete = 'del'
    Modify = 'mod'
    Combine = 'fuse'
    Bulk = 'bulk'
    Cache = 'cache'
    Config = 'conf'


class Command:
    pattern: CmdPattern
    group: Group

    all: ClassVar[Dict[str, 'Command']] = {}

    def __init__(self, group: Group, tokens: CmdPattern):
        self.group = group
        self.pattern: CmdPattern = tokens

    def __call__(self, func: Handler):
        self.handler = func
        self.description = func.__doc__
        self.__class__.all[func.__name__] = self

    def parse(self, command: str) -> int|None:
        tokens: List[Token] = []
        marker: int = 0

        # Enter means 'show' command
        if command.strip() == '':
            Table.display_latest()
            return None

        for component in self.pattern:
            # Skip whitespace
            marker += len(command[marker:]) - len(command[marker:].lstrip())

            # Match syntax literal
            if isinstance(component, str):
                if command.startswith(component, marker):
                    marker += len(component)
                else:
                    return marker

            # Match and parse Token
            elif isinstance(component, type):
                token = component()
                token.parse(command, marker)
                if token.match is not None:
                    tokens.append(token)
                    marker = token.match.end()
                else:
                    return marker

        # Check for leftover symbols
        if command[marker:].strip():
            return marker

        # Execute handler
        args = [token.evaluate() for token in tokens]
        self.handler(*args)
        return None

    @classmethod
    @deprecated
    def show_help_table(cls):
        table: List[Tuple[str, str, str, str]] = []
        for func_name, cmd in cls.all.items():
            name = func_name.replace('_', ' ').capitalize()
            signature = ' '.join((x if isinstance(x, str) else f'[{x.__name__}]' for x in cmd.pattern))
            table.append((name, signature, cmd.description or '', cmd.group.name))
        widths = tuple((max(len(row[n]) for row in table) for n in range(2)))
        for key, group in groupby(table, key=itemgetter(3)):
            print(f"\n{key}:")
            for name, signature, description, groupname in group:
                print(f"  {name:{widths[0]}}  {signature:{widths[1]}}  {description}")

    @classmethod
    def show_help(cls):
        for cmd in cls.all.values():
            signature = ' '.join((x if isinstance(x, str) else f'[{x.__name__}]' for x in cmd.pattern))
            print(f"{signature} - {cmd.description}")


@Command(Group.Show, ['show'])
def display_table_recent():
    """Re-display last shown table of entries (all loaded entries if never displayed)"""
    if Table.stored_interval is None:
        log("Table of all entries:")
        Table.display_all()
    else:
        log("Redisplay table:")
        Table.display_latest()


@Command(Group.Show, ['show', 'all'])
def display_table_all():
    """Display table of all loaded entries"""
    log("Table of all entries:")
    Table.display_all()


@Command(Group.Show, ['show', Date])
def display_table_for_day(day: date):
    """Display table of entries for the specified date"""
    log(f"Table entries for {day:%Y-%m-%d} day:")
    Table.display_for(day, day)


@Command(Group.Show, ['show', Week])
def display_table_for_week(monday: date):
    """Display table of entries for the specified week"""
    log(f"Table entries for {monday:%Y-%m-%d} week:")
    Table.display_for(*Week.get_work_week(monday))


@Command(Group.Show, ['show', Date, '..', Date])
def display_table_for_period(start: date, end: date):
    """Display table of entries for the specified time interval"""
    log(f"Table entries for {start:%Y-%m-%d} - {end:%Y-%m-%d} period:")
    Table.display_for(since=start, until=end)


@Command(Group.Show, ['show', Node])
def display_table_for_node(entry: Entry):
    """Display table of entries for the day containing the specified entry"""
    log(f"Table of entries for the day containing entry #{entry.alias} ({entry.text}):")
    raise AppError(f"Not implemented: show [Node]")


@Command(Group.Load, [Get, Date])
def load_data_for_day(method: LoadMethod, day: date):
    """Load or fetch entries for the specified date"""
    match method:
        case 'get':
            raise AppError(f"Not implemented: get method")
        case 'load':
            Activity.load()
            loaded = Entry.load(day, day, ignore_missing=True)
        case 'fetch':
            server.login(backend['key'], backend['secret'])
            Activity.fetch()
            loaded = Entry.fetch(day, day)
            server.logout()
    log(f"{method.capitalize()}ed {loaded} entries for {day:%Y-%m-%d} day")


@Command(Group.Load, [Get, Week])
def load_data_for_week(method: LoadMethod, monday: date):
    """Load or fetch entries for the current week"""
    monday, friday = Week.get_work_week(monday)
    match method:
        case 'get':
            raise AppError(f"Not implemented: get method")
        case 'load':
            Activity.load()
            loaded = Entry.load(monday, friday, ignore_missing=True)
        case 'fetch':
            server.login(backend['key'], backend['secret'])
            Activity.fetch()
            loaded = Entry.fetch(monday, friday)
            server.logout()
    log(f"{method.capitalize()}ed {loaded} entries for {monday:%Y-%m-%d} week")


@Command(Group.Load, [Get, Date, '..', Date])
def load_data_for_period(method: LoadMethod, start: date, end: date):
    """Load or fetch entries for the specified time interval"""
    match method:
        case 'get':
            raise AppError(f"Not implemented: get method")
        case 'load':
            Activity.load()
            loaded = Entry.load(start, end, ignore_missing=True)
        case 'fetch':
            server.login(backend['key'], backend['secret'])
            Activity.fetch()
            loaded = Entry.fetch(start, end)
            server.logout()
    log(f"{method.capitalize()}ed {loaded} entries for {start:%Y-%m-%d} - {end:%Y-%m-%d} period")


@Command(Group.Delete, ['-', Node])
def delete_entry(entry: Entry):
    """Delete the specified entry"""
    entry.delete()
    log(f"Removed entry #{entry.alias} ({entry.text})")


@Command(Group.Delete, ['del', Date])
def delete_entries_for(day: date):
    """Delete all entries within the specified date"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if entry.start.date() == day:
            entry.delete()
            deleted += 1
    log(f"Deleted {deleted} entries within {day:%Y-%m-%d} day")


@Command(Group.Delete, ['del', Date, '..', Date])
def delete_entries_for_period(start: date, end: date):
    """Delete all entries for the specified time period"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if start <= entry.start.date() <= end:
            entry.delete()
            deleted += 1
    log(f"Deleted {deleted} entries within {start:%Y-%m-%d} - {end:%Y-%m-%d} period")


@Command(Group.Delete, ['del', 'personal'])
def delete_personal_entries():
    """Delete all entries with activities that does not have associated Jira ID"""
    deleted = 0
    for entry in list(Entry.all.values()):
        activity_name = entry.activity.name
        if activity_name in CONFIG.general_tasks:
            if CONFIG.general_tasks[activity_name] is None:
                entry.delete()
                deleted += 1
    deleted_activities = [f"'{name}'" for name, jira in CONFIG.general_tasks.items() if jira is None]
    log(f"Deleted {deleted} entries with activity names: {', '.join(deleted_activities)}")


@Command(Group.Delete, ['del', Task])
def delete_entries_by_task_name(target_activity: str):
    """Delete all entries with the specified activity name"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if entry.activity.name == target_activity:
            entry.delete()
            deleted += 1
    log(f"Deleted {deleted} entries with activity name '{target_activity}'")


@Command(Group.Combine, ['combine'])
def combine_entries_all():
    """Merge all entries with the same description within the same day"""
    merged = Entry.combine_all()
    log(f"Combined {merged} entries with the same description")


@Command(Group.Combine, ['combine', Date])
def combine_entries_for_day(day: date):
    """Merge entries with the same description within the specified date"""
    merged = Entry.combine_for(day, day)
    log(f"Combined {merged} entries within {day:%Y-%m-%d} day")


@Command(Group.Combine, ['combine', Week])
def combine_entries_for_week(monday: date):
    """Merge entries with the same description within the specified week"""
    merged = Entry.combine_for(*Week.get_work_week(monday))
    log(f"Combined {merged} entries within {monday:%Y-%m-%d} week")


@Command(Group.Combine, ['combine', Date, '..', Date])
def combine_entries_for_period(start: date, end: date):
    """Merge entries with the same description within the specified time interval"""
    merged = Entry.combine_for(since=start, until=end)
    log(f"Combined {merged} entries within {start:%Y-%m-%d} - {end:%Y-%m-%d} period")


@Command(Group.Combine, [Node, '>>', Node])
def fuse_entry_into_second(donor: Entry, acceptor: Entry):
    """Fuse the 1st entry into the 2nd entry, taking entry description from the 2nd"""
    if donor.activity != acceptor.activity:
        raise AppError("Cannot fuse entires from different tasks:"
                       f" '{donor.activity.name}' and '{acceptor.activity.name}'")
    acceptor.start = min(donor.start, acceptor.start)
    acceptor.span += donor.span
    donor.delete()
    log(f"Fused #{donor.alias} —>",
        f"#{acceptor.alias}: {acceptor.start:{Format.YMDHM}} {acceptor.duration}"
    )


@Command(Group.Combine, [Node, '<<', Node])
def fuse_entry_into_first(acceptor: Entry, donor: Entry):
    """Fuse the 2nd entry into the 1st entry, taking entry description from the 1st"""
    if donor.activity != acceptor.activity:
        raise AppError("Cannot fuse entires from different tasks:"
                       f" '{donor.activity.name}' and '{acceptor.activity.name}'")
    acceptor.start = min(donor.start, acceptor.start)
    acceptor.span += donor.span
    donor.delete()
    log(f"Fused #{donor.alias} —>",
        f"#{acceptor.alias}: {acceptor.start:{Format.YMDHM}} {acceptor.duration}"
    )


@Command(Group.Combine, [Node, '|', Span, ':', Text])
def split_entry(parent: Entry, span: timedelta, text: str):
    """Detach new entry from the end with the specified duration and description"""
    if span > parent.span:
        raise AppError(f"Cannot detach entry with duration {timespan_to_duration(span)}"
                       f" > parent duration {parent.span}")
    parent.span -= span
    if not text or text == '...':
        text = parent.text
    child = Entry(parent.activity, parent.start + parent.span, span, text)
    log(f"Detached #{parent.alias} ->",
        f"#{child.alias}: {child.start:{Format.YMDHM}} {child.duration} ({child.text})"
    )


@Command(Group.Modify, [Node, '=', Span])
def set_entry_duration(entry: Entry, duration: timedelta):
    """Set entry duration to the specified amount of time"""
    entry.span = duration
    log(f"#{entry.alias}: {entry.text}")


@Command(Group.Modify, [Node, '+', Span])
def increase_entry_duration(entry: Entry, delta: timedelta):
    """Increase entry duration by the specified amount of time"""
    entry.span += delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '-', Span])
def decrease_entry_duration(entry: Entry, delta: timedelta):
    """Decrease entry duration by the specified amount of time"""
    entry.span -= delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '>', Span])
def contract_entry_duration(entry: Entry, delta: timedelta):
    """Contract entry duration from the beginning by the specified amount of time"""
    entry.start += delta
    entry.span -= delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '<', Span])
def expand_entry_duration(entry: Entry, delta: timedelta):
    """Expand entry duration from the beginning by the specified amount of time"""
    entry.start -= delta
    entry.span += delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '>>', Span])
def shift_entry_ahead(entry: Entry, delta: timedelta):
    """Shift entry to the specified amount of time ahead"""
    entry.start += delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '<<', Span])
def shift_entry_behind(entry: Entry, delta: timedelta):
    """Shift entry to the specified amount of time behind"""
    entry.start -= delta
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '=', Time])
def set_entry_start_time(entry: Entry, start_time: time):
    """Set entry start time to the specified amount of time"""
    entry.start = entry.start.combine(date=entry.start.date(), time=start_time)
    log(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.Modify, [Node, '->', Node])
def copy_entry_description(donor: Entry, acceptor: Entry):
    """Copy the 1st entry description to the 2nd entry"""
    acceptor.text = donor.text
    log(f"#{acceptor.alias}: {acceptor.text}")


@Command(Group.Modify, [Node, Task])
def set_entry_activity(entry: Entry, activity: Activity):
    """Set entry activity to the activity with the specified name"""
    entry.activity = activity
    log(f"#{entry.alias}: [{entry.activity}]")


@Command(Group.Modify, [Node, ':', Text])
def set_entry_description(entry: Entry, text: str):
    """Edit entry description"""
    entry.text = text
    entry.fix_whitespace()
    log(f"#{entry.alias}: {entry.text}")


@Command(Group.Bulk, ['fix', 'spaces'])
def fix_entries_description():
    """Replace all consecutive space characters in entry description with a single one"""
    fixed = 0
    for entry in list(Entry.all.values()):
        fixed += entry.fix_whitespace()
    log(f"Fixed whitespace in descriptions of {fixed} entries")


@Command(Group.Cache, ['clear'])
def clear_cache():
    raise AppError("Not implemented: clear cache")


@Command(Group.Cache, ['clear', Date, '..', Date])
def clear_cache_for(start: date, end: date):
    raise AppError("Not implemented: clear cache from .. to")


@Command(Group.Config, ['scrollback', Toggle])
def toggle_auto_display(state: bool):
    CONFIG.scrollback = state


@Command(Group.Config, ['help'])
def help():
    """Exit the application"""
    log("Available commands:")
    Command.show_help()


@Command(Group.Config, [Quit])
def finish(_):
    """Exit the application"""
    server.logout()
    exit(0)
