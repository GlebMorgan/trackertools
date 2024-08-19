from __future__ import annotations

import os
import sys
from bisect import insort
from collections import defaultdict
from datetime import date, timedelta
from itertools import groupby
from typing import Callable, ClassVar, Collection, Dict, List

from config import CONFIG
from entry import Entry
from jira_client import Jira
from task import JiraId, Task
from tools import TODAY, AppError, constrict, seconds_to_duration, timespan_to_duration


TOP_SCROLL_SEQUENCE = "\033[H\033[J"
GAP = " " * 3


class Table:
    widths: ClassVar[Dict[str, int]] = defaultdict(int)
    scrollback: ClassVar[bool] = CONFIG.scrollback
    show_estimates: ClassVar[bool] = CONFIG.jira_estimates
    stored_interval: ClassVar[tuple[date, date] | None] = None
    targets: ClassVar[List[timedelta | None]] = []

    @staticmethod
    def _display_order_(entry: Entry) -> date:
        return entry.start.date()

    @staticmethod
    def _get_status_glyph_(entry: Entry) -> str:
        if entry.logged():
            return '✓'
        if entry.formatted():
            return '○'
        return '·'

    @classmethod
    def _set_column_widths_(cls):
        cls.widths.clear()
        for entry in Entry.all.values():
            if (jira_width := len(str(entry.task.jira))) > cls.widths['jira']:
                cls.widths['jira'] = jira_width
            if (taskname_width := len(entry.task.name)) > cls.widths['task']:
                cls.widths['task'] = taskname_width

    @classmethod
    def _trunc_description_(cls, description: str) -> str:
        # TODO: calculate width left for description dynamically
        console_width = os.get_terminal_size().columns
        max_width = console_width - cls.widths['jira'] - len(GAP) - cls.widths['task'] - 38
        return constrict(description, width=max_width)

    @classmethod
    def list(cls, entries: List[Entry]):
        for current_date, daily_entries in groupby(entries, key=lambda e: e.start.date()):
            print(current_date)
            for entry in daily_entries:
                print(entry)

    @classmethod
    def format_row(cls, entry: Entry) -> str:
        columns = dict(
            alias=f"{entry.alias:2}",
            start=f"{entry.start.strftime('%H:%M'):5}",
            duration=f"{entry.duration:6}",
            remaining=None,
            jira=f"{entry.task.jira or '-' :<{cls.widths['jira']}}",
            taskname=f"{entry.task.name :<{cls.widths['task']}}",
            description=f"{cls._trunc_description_(entry.description)}",
        )

        if cls.show_estimates is True:
            remaining_duration = cls._format_time_remaining_(entry)
            duration_column = f"{cls._align_negative_time_(remaining_duration) :{8}}"
            columns['remaining'] = duration_column

        status = cls._get_status_glyph_(entry)
        return status + " " + GAP.join(filter(None, columns.values()))

    @classmethod
    def group_by_days(cls, entries: Collection[Entry]) -> Dict[date, List[Entry]]:
        entries_grouped: Dict[date, List[Entry]] = defaultdict(list)
        for entry in entries:
            entries_list = entries_grouped[entry.start.date()]
            insort(entries_list, entry, key=cls._display_order_)
        return entries_grouped

    @classmethod
    def get_total_duration(cls, entries: Collection[Entry]) -> timedelta:
        return sum((entry.span for entry in entries), start=timedelta())

    @classmethod
    def display_grouped(cls, entries: Collection[Entry]):
        cls._set_column_widths_()

        if cls.scrollback is False:
            print(TOP_SCROLL_SEQUENCE, end="")

        total_duration = cls.get_total_duration(entries)
        entries_grouped = cls.group_by_days(entries)

        print(f"Total - {len(entries)} entries - {timespan_to_duration(total_duration)}")
        for i, (curr_date, daily_entries) in enumerate(sorted(entries_grouped.items())):
            daily_total = sum((entry.span for entry in daily_entries), start=timedelta())
            daily_duration = timespan_to_duration(daily_total)
            daily_header = (
                f"\n{curr_date:%A} {curr_date}"
                f" - {len(daily_entries)} entries"
                f" - {daily_duration}"
            )
            if len(cls.targets) > i:
                target_duration = cls.targets[i]  # make it explicit for PyLance
                if target_duration is not None:
                    daily_header += f" ({timespan_to_duration(target_duration)} target)"

            print(daily_header)
            for entry in daily_entries:
                print(cls.format_row(entry))

    @classmethod
    def display_all(cls):
        cls.display_grouped(Entry.all.values())
        cls.stored_interval = (date.min, date.max)

    @classmethod
    def display_for(cls, since: date, until: date):
        within_bounds: Callable[[Entry], bool] = lambda entry: since <= entry.day <= until
        cls.display_grouped(list(filter(within_bounds, Entry.all.values())))
        cls.stored_interval = (since, until)

    @classmethod
    def display_latest(cls):
        if cls.stored_interval is not None:
            cls.display_for(*cls.stored_interval)

    @classmethod
    def display_task_estimations(cls):
        tasks = [task for task in Entry.all_tasks() if task.name not in CONFIG.tasks]
        max_task_name = max(len(task.name) for task in tasks)

        print(
            "Task name".ljust(max_task_name),
            "Jira".ljust(12),
            "Estimate".ljust(12),
            "Remaining".ljust(12),
            "Spent".ljust(12),
            sep=GAP,
        )

        for task in tasks:
            tracking = Jira.get_timetracking(task.jira)
            if tracking is None:
                continue

            logged = sum(
                int(entry.span.total_seconds())
                for entry in Entry.all.values()
                if entry.task.jira == task.jira
            )

            print(
                f"{task.name:{max_task_name}}",
                f"{task.jira :12}",
                f"{seconds_to_duration(tracking.estimated):12}",
                f"{seconds_to_duration(tracking.remaining):12}",
                f"{seconds_to_duration(logged):12}",
                sep=GAP,
            )

    @classmethod
    def _get_time_spent_(cls, jira_id: JiraId) -> timedelta:
        spent = sum(
            int(entry.span.total_seconds())
            for entry in Entry.all.values()
            if entry.task.jira == jira_id
        )
        return timedelta(seconds=spent)

    @classmethod
    def _format_time_remaining_(cls, entry: Entry) -> str:
        if entry.task.jira is None:
            return "-"

        if entry.task.name in CONFIG.tasks:
            return ""

        Jira.login(CONFIG.credentials.jira.token)
        tracking = Jira.get_timetracking(entry.task.jira)

        if tracking is None:
            raise AppError(f"Failed to get time tracking for {entry.task.jira}")

        if tracking.estimated == 0:
            return "N/A"

        spent = cls._get_time_spent_(entry.task.jira)
        remaining = tracking.remaining - int(spent.total_seconds())
        return seconds_to_duration(remaining)

    @staticmethod
    def _align_negative_time_(string: str) -> str:
        if string.startswith("-") and string != "-":
            return string
        return f" {string}"

    @classmethod
    def set_daily_targets(cls, target_durations: List[timedelta | None]):
        cls.targets = target_durations


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if mode == 'list':
        Task.load()
        Entry.load(TODAY, TODAY)
        Table.display_all()

    if mode == 'combine':
        Task.load()
        Entry.load(TODAY, TODAY)
        Entry.combine(Entry.all.values())
        Table.display_all()
