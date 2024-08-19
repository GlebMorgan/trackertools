from __future__ import annotations

import sys
from datetime import date, time, timedelta
from enum import Enum
from itertools import groupby
from operator import itemgetter
from typing import Any, Callable, ClassVar, Dict, List, Literal, Tuple, Type

from config import CONFIG, trace
from entry import Entry
from jira_client import Jira
from table import Table
from task import Task
from tokens import Date, Get, JiraID, Node, Quit, Span, Text
from tokens import Time, TimeList, Toggle, Token, Week
from tools import AppError, Format, deprecated, quoted, timespan_to_duration


match CONFIG.backend:
    case 'timecamp':
        from timecamp_api import Timecamp as Server
    case 'timeular':
        from timeular_api import Timeular as Server
    case other:
        raise ImportError(f"Invalid backend config: '{other}'")


Handler = Callable[..., Any]
Template = List[Type[Token] | str]
LoadMethod = Literal['get', 'load', 'fetch']


class Group(Enum):
    SHOW = 'show'
    LOAD = 'get'
    DELETE = 'del'
    MODIFY = 'mod'
    COMBINE = 'fuse'
    FORMAT = 'format'
    CACHE = 'cache'
    CONFIG = 'conf'
    JIRA = 'jira'
    RND = 'rnd'


class Command:
    all: ClassVar[Dict[str, Command]] = {}

    group: Group
    pattern: Template
    handler: Handler
    description: str | None

    def __init__(self, group: Group, tokens: Template):
        self.group = group
        self.pattern = tokens

    def __call__(self, func: Handler) -> Handler:
        """Decorator descriptor"""
        self.handler = func
        self.description = func.__doc__
        self.__class__.all[func.__name__] = self
        return func

    def parse(self, command: str) -> int | None:
        tokens: List[Token] = []
        marker: int = 0

        # Enter means 'show' commands
        # TODO: change this to "last entered command" and remove Table.display_latest()
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
            tokens = (x if isinstance(x, str) else f'[{x.__name__}]' for x in cmd.pattern)
            table.append((name, ' '.join(tokens), cmd.description or '', cmd.group.name))
        widths = tuple((max(len(row[n]) for row in table) for n in range(2)))
        for key, group in groupby(table, key=itemgetter(3)):
            print(f"\n{key}:")
            for name, signature, description, groupname in group:
                print(f"  {name:{widths[0]}}  {signature:{widths[1]}}  {description}")

    def signature(self):
        tokens = (x if isinstance(x, str) else f'[{x.__name__}]' for x in self.pattern)
        return ' '.join(tokens)

    @classmethod
    def show_help(cls):
        for cmd in cls.all.values():
            print(f"{cmd.signature()} - {cmd.description}")


@Command(Group.SHOW, ['show'])
def display_table_recent():
    """Re-display last shown table of entries (all loaded entries if never displayed)"""
    if Table.stored_interval is None:
        trace("Table of all entries:")
        Table.display_all()
    else:
        trace("Redisplay table:")
        Table.display_latest()


@Command(Group.SHOW, ['show', 'all'])
def display_table_all():
    """Display table of all loaded entries"""
    trace("Table of all entries:")
    Table.display_all()


@Command(Group.SHOW, ['show', Date])
def display_table_for_day(day: date):
    """Display table of entries for the specified date"""
    trace(f"Table entries for {day:{Format.YMD}} day:")
    Table.display_for(day, day)


@Command(Group.SHOW, ['show', Week])
def display_table_for_week(monday: date):
    """Display table of entries for the specified week"""
    trace(f"Table entries for {monday:{Format.YMD}} week:")
    Table.display_for(*Week.get_work_week(monday))


@Command(Group.SHOW, ['show', Date, '..', Date])
def display_table_for_period(start: date, end: date):
    """Display table of entries for the specified time interval"""
    trace(f"Table entries for {start:{Format.YMD}} — {end:{Format.YMD}} period:")
    Table.display_for(since=start, until=end)


@Command(Group.SHOW, ['show', Node])
def display_table_for_node(entry: Entry):
    """Display table of entries for the day containing the specified entry"""
    trace(f"Table of entries for the day containing entry #{entry.alias} ({entry.text}):")
    print(NotImplemented)


@Command(Group.SHOW, ['tasks'])
def show_tasks():
    """Display tasks time estimation"""
    Jira.login(CONFIG.credentials.jira.token)
    Table.display_task_estimations()


@Command(Group.LOAD, [Get, Date])
def load_data_for_day(method: LoadMethod, day: date):
    """Load or fetch entries for the specified date"""
    match method:
        case 'get':
            raise NotImplementedError("App.get()")
            # App.get(day, day)
        case 'load':
            Task.load()
            Entry.load(day, day)
        case 'fetch':
            Server.login(CONFIG.credentials[CONFIG.backend])
            Task.fetch()
            Entry.fetch(day, day)
    action: str = method.capitalize() + 'ed'
    trace(f"{action} {len(Entry.all)} entries for {day:{Format.YMD}} day")


@Command(Group.LOAD, [Get, Week])
def load_data_for_week(method: LoadMethod, monday: date):
    """Load or fetch entries for the current week"""
    monday, friday = Week.get_work_week(monday)
    match method:
        case 'get':
            raise NotImplementedError("App.get()")
            # App.get()
        case 'load':
            Task.load()
            Entry.load(monday, friday)
        case 'fetch':
            Server.login(CONFIG.credentials[CONFIG.backend])
            Task.fetch()
            Entry.fetch(monday, friday)
    action: str = method.capitalize() + 'ed'
    trace(f"{action} {len(Entry.all)} entries for {monday:{Format.YMD}} week")


@Command(Group.LOAD, [Get, Date, '..', Date])
def load_data_for_period(method: LoadMethod, start: date, end: date):
    """Load or fetch entries for the specified time interval"""
    match method:
        case 'get':
            raise NotImplementedError("App.get()")
            # App.get()
        case 'load':
            Task.load()
            Entry.load(start, end)
        case 'fetch':
            Server.login(CONFIG.credentials[CONFIG.backend])
            Task.fetch()
            Entry.fetch(start, end)
    action: str = method.capitalize() + 'ed'
    time_period: str = f"{start:{Format.YMD}} — {end:{Format.YMD}} period"
    trace(f"{action} {len(Entry.all)} entries for {time_period}")


@Command(Group.DELETE, ['del', Node])
def delete_entry(entry: Entry):
    """Delete the specified entry"""
    entry.delete()
    trace(f"Removed entry #{entry.alias} ({entry.text})")


@Command(Group.DELETE, ['del', Date])
def delete_entries_for_day(day: date):
    """Delete all entries within the specified date"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if entry.start.date() == day:
            entry.delete()
            deleted += 1
    trace(f"Removed {deleted} entries within {day:{Format.YMD}} day")


@Command(Group.DELETE, ['del', Date, '..', Date])
def delete_entries_for_period(start: date, end: date):
    """Delete all entries for the specified time period"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if start <= entry.start.date() <= end:
            entry.delete()
            deleted += 1
    time_period: str = f"{start:{Format.YMD}} — {end:{Format.YMD}} period"
    trace(f"Removed {deleted} entries within {time_period}")


@Command(Group.DELETE, ['del', 'personal'])
def delete_personal_entries():
    """Delete all entries with activities that does not have associated Jira ID"""
    deleted = 0
    personal_tasks = [name for name, jira in CONFIG.tasks.items() if jira is None]
    for entry in list(Entry.all.values()):
        if entry.task.name in personal_tasks:
            entry.delete()
            deleted += 1
    trace(f"Removed {deleted} entries with task names: {', '.join(quoted(personal_tasks))}")


@Command(Group.DELETE, ['del', JiraID])
def delete_entries_by_task_name(target_task: str):
    """Delete all entries with the specified task name"""
    deleted = 0
    for entry in list(Entry.all.values()):
        if entry.task.name == target_task:
            entry.delete()
            deleted += 1
    trace(f"Removed {deleted} entries with task name '{target_task}'")


@Command(Group.COMBINE, ['combine'])
def combine_all_entries():
    """Merge all entries with the same description within the same day"""
    merged = Entry.combine(Entry.all.values())
    trace(f"Combined {merged} entries with the same description")


@Command(Group.COMBINE, ['combine', Date])
def combine_entries_for_day(day: date):
    """Merge entries with the same description within the specified date"""
    merged = Entry.combine_for(day, day)
    trace(f"Combined {merged} entries within {day:{Format.YMD}} day")


@Command(Group.COMBINE, ['combine', Week])
def combine_entries_for_week(monday: date):
    """Merge entries with the same description within the specified week"""
    merged = Entry.combine_for(*Week.get_work_week(monday))
    trace(f"Combined {merged} entries within {monday:{Format.YMD}} week")


@Command(Group.COMBINE, ['combine', Date, '..', Date])
def combine_entries_for_period(start: date, end: date):
    """Merge entries with the same description within the specified time interval"""
    merged = Entry.combine_for(since=start, until=end)
    time_period: str = f"{start:{Format.YMD}} — {end:{Format.YMD}} period"
    trace(f"Combined {merged} entries within {time_period}")


@Command(Group.COMBINE, [Node, '>>', Node])
def fuse_entry_right(donor: Entry, acceptor: Entry):
    """Fuse the 1st entry into the 2nd entry, taking entry description from the 2nd"""
    if donor.task != acceptor.task:
        raise AppError(
            "Cannot fuse entires from different tasks: "
            f"'{donor.task.name}' and '{acceptor.task.name}'"
        )
    total_span = acceptor.span + donor.span
    acceptor.start = min(donor.start, acceptor.start)
    acceptor.end = acceptor.start + total_span
    donor.delete()
    trace(
        f"Fused #{donor.alias} —> #{acceptor.alias}: "
        f"{acceptor.start:{Format.YMDHM}} {acceptor.duration} ({acceptor.text})"
    )


@Command(Group.COMBINE, [Node, '<<', Node])
def fuse_entry_left(acceptor: Entry, donor: Entry):
    """Fuse the 2nd entry into the 1st entry, taking entry description from the 1st"""
    fuse_entry_right(donor, acceptor)


@Command(Group.COMBINE, [Node, '|', Span, ':', Text])
def split_entry(parent: Entry, span: timedelta, text: str):
    """Detach new entry from the end with the specified duration and description"""
    if span >= parent.span:
        raise AppError(
            f"Cannot detach entry with duration "
            f"{timespan_to_duration(span)} ≥ parent duration {parent.duration}"
        )
    if not text or text == '...':
        text = parent.text

    child = Entry(Entry.gen_id(parent), parent.task, parent.end - span, parent.end, text)
    parent.end -= span
    trace(
        f"Detached #{parent.alias} —> #{child.alias}: "
        f"{child.start:{Format.YMDHM}} {child.duration} ({child.text})",
    )


@Command(Group.MODIFY, [Node, '=', Span])
def set_entry_duration(entry: Entry, duration: timedelta):
    """Set entry duration to the specified amount of time"""
    entry.end = entry.start + duration
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '+', Span])
def increase_entry_duration(entry: Entry, delta: timedelta):
    """Increase entry duration by the specified amount of time"""
    entry.end += delta
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '-', Span])
def decrease_entry_duration(entry: Entry, delta: timedelta):
    """Decrease entry duration by the specified amount of time"""
    if delta >= entry.span:
        raise AppError(
            f"Cannot decrease entry duration by "
            f"{timespan_to_duration(delta)} ≥ current duration {entry.duration}"
        )
    entry.end -= delta
    assert entry.start < entry.end
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '<', Span])
def expand_entry_duration(entry: Entry, delta: timedelta):
    """Expand entry duration from the beginning by the specified amount of time"""
    entry.start -= delta
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '>', Span])
def contract_entry_duration(entry: Entry, delta: timedelta):
    """Contract entry duration from the beginning by the specified amount of time"""
    if delta >= entry.span:
        raise AppError(
            f"Cannot contract entry by "
            f"{timespan_to_duration(delta)} ≥ current duration {entry.duration}"
        )
    entry.start += delta
    assert entry.start < entry.end
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '>>', Span])
def shift_entry_ahead(entry: Entry, delta: timedelta):
    """Shift entry to the specified amount of time ahead"""
    entry.start += delta
    entry.end += delta
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '<<', Span])
def shift_entry_behind(entry: Entry, delta: timedelta):
    """Shift entry to the specified amount of time behind"""
    entry.start -= delta
    entry.end -= delta
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, ':=', Time])
def set_entry_start_time(entry: Entry, start_time: time):
    """Set entry start time to the specified amount of time"""
    initial_span = entry.span
    entry.start = entry.start.combine(date=entry.day, time=start_time)
    entry.end = entry.start + initial_span
    trace(f"#{entry.alias}: {entry.start:{Format.HM}} {entry.duration}")


@Command(Group.MODIFY, [Node, '->', Node])
def copy_entry_description(donor: Entry, acceptor: Entry):
    """Copy the 1st entry description to the 2nd entry"""
    acceptor.text = donor.text
    trace(f"#{acceptor.alias}: {acceptor.text}")


@Command(Group.MODIFY, [Node, '=>', JiraID])
def set_entry_task(entry: Entry, task: Task):
    """Set entry task to the task with the specified name"""
    entry.task = task
    trace(f"#{entry.alias}: {entry.task}")


@Command(Group.MODIFY, [Node, ':', Text])
def set_entry_description(entry: Entry, text: str):
    """Edit entry description"""
    new_description = '\n'.join(text.split(' | '))

    if entry.formatted():
        entry.markup = new_description
    else:
        entry.text = new_description

    entry.fix_whitespace()
    trace(f"#{entry.alias}: \"{entry.description}\"")


@Command(Group.FORMAT, ['fix'])
def fix_all_entries_description():
    """Replace all consecutive space characters in entry description with a single one"""
    fixed = 0
    for entry in list(Entry.all.values()):
        fixed += entry.fix_whitespace()
    trace(f"Fixed whitespace in descriptions of {fixed} entries")


@Command(Group.FORMAT, ['format', Node])
def apply_jira_formatting(entry: Entry):
    """Generate Jira markup from entry description"""
    result = entry.gen_markup()
    if result is True:
        trace(f"Generated Jira markup for #{entry.alias}")
    else:
        trace(f"Nothing to generate for entry #{entry.alias}")


@Command(Group.FORMAT, ['format'])
def apply_jira_formatting_for_all():
    """Generate Jira markup from entry description for all entries"""
    generated = 0
    for entry in list(Entry.all.values()):
        result = entry.gen_markup()
        if result is True:
            generated += 1
    trace(f"Generated Jira markup for {generated} entries")


@Command(Group.CACHE, ['cache', 'clear'])
def cache_clear():
    """Clear all cached tasks and entries"""
    print(NotImplemented, "clear cache")


@Command(Group.JIRA, ['log', Node])
def log_work(entry: Entry) -> bool:
    """Add entry worklog to Jira"""
    Jira.login(CONFIG.credentials.jira.token)
    was_logged = entry.logged()
    if was_logged:
        entry.remove_jira_log()
    result = entry.log_to_jira()
    if result is True:
        trace(
            f"{'Adjusted' if was_logged else 'Logged'} work:"
            f" {entry.task.jira}"
            f" ({entry.day} {entry.start.hour:02}:{entry.start.minute:02})"
            f" [{entry.duration}]: {entry.description}"
        )
    return result


@Command(Group.JIRA, ['log', 'all'])
def log_all():
    """Add worklog of all loaded entries to Jira"""
    logged = 0
    failed = 0

    Jira.login(CONFIG.credentials.jira.token)

    for entry in Entry.all.values():
        result = log_work(entry)
        if result is True:
            logged += 1
        else:
            failed += 1

    summary = f"Added worklog to Jira for {logged} entries"
    if failed > 0:
        summary += f", failed {failed} entries"
    print(summary)


@Command(Group.RND, ['rnd', TimeList])
def get_rnd_times_manually(hours: List[timedelta | None]):
    """Get RND hours for loaded work days manually"""
    total_days = len(Table.group_by_days(Entry.all.values()))
    if len(hours) != total_days:
        raise AppError(f"Expected {total_days} RND time intervals, got {len(hours)}")

    Table.set_daily_targets(hours)

    durations = [timespan_to_duration(x) if x is not None else '-' for x in hours]
    trace(f"Set RND hours for {total_days} days: [{', '.join(durations)}]")


@Command(Group.CONFIG, ['scrollback', Toggle])
def toggle_auto_display(state: bool):
    """Toggle auto-scrolling of displayed entry table to the top of the screen"""
    Table.scrollback = state


@Command(Group.CONFIG, ['estimates', Toggle])
def toggle_jira_estimates_display(state: bool):
    """Toggle fetching and showing Jira time logging info (time remaining)"""
    Table.show_estimates = state


@Command(Group.CONFIG, ['help'])
def show_help():
    """Display commands help"""
    trace("Available commands:")
    Command.show_help()


@Command(Group.CONFIG, [Quit])
def finish(_):
    """Exit the application"""
    Server.logout()
    Jira.logout()
    sys.exit(0)
