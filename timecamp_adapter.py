import re
import sys

from datetime import date, datetime, time
from typing import Tuple

from backend_adapter import BackendAdapter, Jira, ParseError, TEntry, TTask
from timecamp import TimecampEntry, TimecampTask
from tools import Format


# JIRA_REGEX = re.compile(r'\[([A-Z0-9]+-[0-9]+)\] ')
TASK_NAME_REGEX = re.compile(r'(?:\[(?P<jira>[A-Z0-9]+-[0-9]+)\])?\s*(?:(?P<title>.+))?')


class TimecampAdapter(BackendAdapter):
    @classmethod
    def parse_task(cls, raw_task: TimecampTask) -> TTask:
        try:
            task_id: int = int(raw_task['task_id'])
        except (ValueError, TypeError):
            error_msg = "Invalid task id '{task_id}'"
            raise ParseError(error_msg.format(**raw_task))

        try:
            parent_id: int = int(raw_task['parent_id'])
        except (ValueError, TypeError):
            error_msg = "Task '{task_id}': Invalid parent id '{parent_id}'"
            raise ParseError(error_msg.format(**raw_task))

        title, jira = cls._parse_title_(raw_task)

        # TODO: get spec from task tags

        return TTask(task_id, parent_id, title, jira, spec=None)

    @classmethod
    def parse_entry(cls, raw_entry: TimecampEntry) -> TEntry:
        try:
            entry_id: int = int(raw_entry['id'])
        except (ValueError, TypeError):
            error_msg = "Invalid entry id '{id}'"
            raise ParseError(error_msg.format(**raw_entry))

        try:
            task_id: int = int(raw_entry['task_id'])
        except (ValueError, TypeError):
            error_msg = "Entry '{id}': Invalid task id '{task_id}'"
            raise ParseError(error_msg.format(**raw_entry))

        try:
            day: date = date.fromisoformat(raw_entry['date'])
        except ValueError:
            error_msg = "Entry '{id}': Invalid date format '{date}'"
            raise ParseError(error_msg.format(**raw_entry))

        try:
            start_time: time = datetime.strptime(raw_entry['start_time'], Format.HMS).time()
        except ValueError:
            error_msg = "Entry '{id}': Invalid start time format '{start_time}'"
            raise ParseError(error_msg.format(**raw_entry))

        try:
            end_time: time = datetime.strptime(raw_entry['end_time'], Format.HMS).time()
        except ValueError:
            error_msg = "Entry '{id}': Invalid end time format '{end_time}'"
            raise ParseError(error_msg.format(**raw_entry))

        start = datetime.combine(day, start_time)
        end = datetime.combine(day, end_time)

        text = raw_entry['description']

        return TEntry(entry_id, task_id, start, end, text)

    @staticmethod
    def _parse_title_(raw_task: TimecampTask) -> Tuple[str, Jira]:
        # TODO: review the algorithm

        match = TASK_NAME_REGEX.match(raw_task['name'].strip())

        if not match:
            error_msg = "Task '{task_id}': Invalid task name format: '{name}'"
            raise ParseError(error_msg.format(**raw_task))

        if match['title'] is None:
            error_msg = "Task '{task_id}': Missing task title: '{name}'"
            raise ParseError(error_msg.format(**raw_task))

        return match['title'], match['jira']


if __name__ == '__main__':
    # pyright: reportPrivateUsage=false

    test_raw_entry = TimecampEntry(
        id=168460559,
        duration='660',
        task_id='120550731',
        date='2023-02-23',
        start_time='09:10:00',
        end_time='09:21:00',
        name='StandUp',
        description='',
    )

    test_raw_task = TimecampTask(
        task_id=12345678,
        parent_id=0,
        name="[FMXX-1234] (TT) Task name (valid)",
    )

    match sys.argv[1:]:
        case ['entry']:
            entry = TimecampAdapter.parse_entry(test_raw_entry)
            print(entry)

        case ['task']:
            task = TimecampAdapter.parse_task(test_raw_task)
            print(task)

        case ['title']:
            title, jira = TimecampAdapter._parse_title_(test_raw_task)
            print(f"{title=}, {jira=}")

        case other:
            pass
