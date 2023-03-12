import os
import sys
from bisect import insort
from collections import defaultdict
from datetime import date, timedelta
from itertools import groupby
from typing import Callable, ClassVar, Dict, Iterable, List, Tuple

from activity import Activity
from config import CONFIG
from entry import Entry
from tools import deprecated, timespan_to_duration


TOP_SCROLL_SEQUENCE = "\033[H\033[J"
GAP = 3


class Table:
    widths: ClassVar[Dict[str, int]] = defaultdict(int)
    stored_interval: ClassVar[Tuple[date, date]|None] = None

    @staticmethod
    def _display_order_(entry: Entry) -> Tuple[int, date]:
        if entry.activity.name in CONFIG.general_tasks:
            task_index = list(CONFIG.general_tasks.keys()).index(entry.activity.name)
        else:
            task_index = entry.activity.id
        return (task_index, entry.start.date())

    @classmethod
    def _update_column_widths_(cls):
        cls.widths.clear()
        for entry in Entry.all.values():
            if (jira_width := len(str(entry.activity.jira))) > cls.widths['jira']:
                cls.widths['jira'] = jira_width
            if (taskname_width := len(entry.activity.name)) > cls.widths['task']:
                cls.widths['task'] = taskname_width

    @classmethod
    def _trunc_description_(cls, description: str):
        max_width = os.get_terminal_size().columns - cls.widths['jira'] - GAP - cls.widths['task'] - GAP - 30
        output = ' | '.join(description.splitlines())
        if (len(output) > max_width):
            output = output[:max_width - len('...')] + '...'
        return output[:max_width]

    @classmethod
    def list(cls, entries: List[Entry]):
        for date, daily_entries in groupby(entries, key=lambda e: e.start.date()):
            print(date)
            for entry in daily_entries:
                print(entry)

    @classmethod
    def format_row(cls, i: int, alias: str, entry: Entry):
        jira = str(entry.activity.jira).ljust(cls.widths['jira'] + GAP)
        start = entry.start.strftime('%H:%M')
        taskname = entry.activity.name.ljust(cls.widths['task'] + GAP)
        description = cls._trunc_description_(str(entry.text))
        return(f"#{i:<{2+GAP}}{alias:{2+GAP}}{start:{5+GAP}}{entry.duration:{6+GAP}}{jira}{taskname}{description}")

    @classmethod
    def display_grouped(cls, entries: Iterable[Entry]):
        cls._update_column_widths_()
        entries_grouped: Dict[date, List[Entry]] = defaultdict(list)

        total_duration = timedelta()
        for entry in entries:
            entries_list = entries_grouped[entry.start.date()]
            insort(entries_list, entry, key=cls._display_order_)
            total_duration += entry.span

        if CONFIG.scrollback is False:
            print(TOP_SCROLL_SEQUENCE, end="")

        i = 0
        print(f"Total - {timespan_to_duration(total_duration)}")
        for curr_date, daily_entries in sorted(entries_grouped.items()):
            daily_duration = sum((entry.span for entry in daily_entries), start=timedelta())
            print(f"\n{curr_date.strftime('%A')} {curr_date} - {timespan_to_duration(daily_duration)}")
            for i, entry in enumerate(daily_entries, start=i+1):
                print(cls.format_row(i, entry.alias, entry))

    @classmethod
    def display_all(cls):
        cls.display_grouped(Entry.all.values())
        cls.stored_interval = (date.min, date.max)

    @classmethod
    def display_for(cls, since: date, until: date):
        filter_by_interval: Callable[[Entry], bool] = lambda e: since <= e.start.date() <= until
        cls.display_grouped(filter(filter_by_interval, Entry.all.values()))
        cls.stored_interval = (since, until)

    @classmethod
    def display_latest(cls):
        if cls.stored_interval is None:
            return
        cls.display_for(*cls.stored_interval)

    @classmethod
    @deprecated
    def OLD_display_grouped(cls):
        cls._update_column_widths_()
        entries = sorted(Entry.all.items(), key=lambda item: item[1].start)
        i = 0
        for date, daily_entries in groupby(entries, key=lambda item: item[1].start.date()):
            daily_entries = list(daily_entries)
            total_duration = sum((entry.span for alias, entry in daily_entries), start=timedelta())
            print(f"\n{date.strftime('%A')} {date} - {timespan_to_duration(total_duration)}")
            for i, (alias, entry) in enumerate(daily_entries, start=i+1):
                print(cls.format_row(i, alias, entry))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if mode == 'list':
        Activity.load()
        Entry.load_all()
        Table.display_all()

    if mode == 'combine':
        Activity.load()
        Entry.load_all()
        Entry.combine_all()
        Table.display_all()
