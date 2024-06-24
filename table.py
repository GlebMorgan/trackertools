from __future__ import annotations

import os
import sys
from bisect import insort
from collections import defaultdict
from datetime import date, timedelta
from itertools import groupby
from typing import Callable, ClassVar, Collection, Dict, List, Tuple

from config import CONFIG
from entry import Entry
from task import Task
from tools import TODAY, constrict, timespan_to_duration


TOP_SCROLL_SEQUENCE = "\033[H\033[J"
GAP = 3


class Table:
    widths: ClassVar[Dict[str, int]] = defaultdict(int)
    stored_interval: ClassVar[tuple[date, date] | None] = None

    @staticmethod
    def _display_order_(entry: Entry) -> Tuple[int, date]:
        if entry.task.name in CONFIG.tasks:
            task_index = list(CONFIG.tasks.keys()).index(entry.task.name)
        else:
            task_index = entry.task.id
        return (task_index, entry.start.date())

    @staticmethod
    def _get_status_glyph_(entry: Entry) -> str:
        if entry.logged():
            return '✓'
        if entry.formatted():
            return '○'
        return '·'

    @classmethod
    def _update_column_widths_(cls):
        cls.widths.clear()
        for entry in Entry.all.values():
            if (jira_width := len(str(entry.task.jira))) > cls.widths['jira']:
                cls.widths['jira'] = jira_width
            if (taskname_width := len(entry.task.name)) > cls.widths['task']:
                cls.widths['task'] = taskname_width

    @classmethod
    def _trunc_description_(cls, description: str) -> str:
        console_width = os.get_terminal_size().columns
        max_width = console_width - cls.widths['jira'] - GAP - cls.widths['task'] - GAP - 30
        output = ' | '.join(description.splitlines())
        return constrict(output, max_width)

    @classmethod
    def list(cls, entries: List[Entry]):
        for current_date, daily_entries in groupby(entries, key=lambda e: e.start.date()):
            print(current_date)
            for entry in daily_entries:
                print(entry)

    @classmethod
    def format_row(cls, i: int, entry: Entry) -> str:
        status = cls._get_status_glyph_(entry)
        description = entry.markup if entry.formatted() else entry.text
        return (
            f"{status} {entry.alias :{2 + GAP}}"
            f"{entry.start.strftime('%H:%M') :{5 + GAP}}"
            f"{entry.duration :{6 + GAP}}"
            f"{entry.task.jira or '-' :<{cls.widths['jira'] + GAP}}"
            f"{entry.task.name :<{cls.widths['task'] + GAP}}"
            f"{cls._trunc_description_(str(description))}"
        )

    @classmethod
    def display_grouped(cls, entries: Collection[Entry]):
        cls._update_column_widths_()
        entries_grouped: Dict[date, List[Entry]] = defaultdict(list)

        total_duration = timedelta()
        for entry in entries:
            entries_list = entries_grouped[entry.start.date()]
            insort(entries_list, entry, key=cls._display_order_)
            total_duration += entry.span

        if CONFIG.scrollback is False:
            print(TOP_SCROLL_SEQUENCE, end="")

        index = 0
        print(f"Total - {len(entries)} entries - {timespan_to_duration(total_duration)}")
        for curr_date, daily_entries in sorted(entries_grouped.items()):
            daily_total = sum((entry.span for entry in daily_entries), start=timedelta())
            daily_duration = timespan_to_duration(daily_total)
            print(
                f"\n{curr_date:%A} {curr_date}"
                f" - {len(daily_entries)} entries"
                f" - {daily_duration}"
            )
            for index, entry in enumerate(daily_entries, start=index + 1):
                print(cls.format_row(index, entry))

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
