from __future__ import annotations

import re
import sys

from datetime import date, datetime, time, timezone
from typing import Tuple

from adapter import BackendAdapter, GenericEntry, GenericTask, ParseError
from api import BackendData
from timecamp_api import TimecampEntry, TimecampTask
from tools import Format


# JIRA_REGEX = re.compile(r'\[([A-Z0-9]+-[0-9]+)\] ')
TASK_NAME_REGEX = re.compile(r'(?:\[(?P<jira>[A-Z0-9]+-[0-9]+)\])?\s*(?:(?P<title>.+))?')


class TimecampAdapter(BackendAdapter):
    @classmethod
    def parse_task(cls, raw_task: BackendData) -> GenericTask:
        timecamp_task = TimecampTask(**raw_task)
        try:
            task_id: int = int(timecamp_task['task_id'])
        except (ValueError, TypeError):
            error_msg = "Invalid task id '{task_id}'"
            raise ParseError(error_msg.format(**timecamp_task))

        try:
            parent_id: int = int(timecamp_task['parent_id'])
        except (ValueError, TypeError):
            error_msg = "Task '{task_id}': Invalid parent id '{parent_id}'"
            raise ParseError(error_msg.format(**timecamp_task))

        title, jira = cls._parse_title_(timecamp_task)

        # TODO: get spec from task tags

        return GenericTask(task_id, parent_id, title, jira, spec=None)

    @classmethod
    def parse_entry(cls, raw_entry: BackendData) -> GenericEntry:
        timecamp_entry = TimecampEntry(**raw_entry)
        try:
            entry_id: int = int(timecamp_entry['id'])
        except (ValueError, TypeError):
            error_msg = "Invalid entry id '{id}'"
            raise ParseError(error_msg.format(**timecamp_entry))

        try:
            task_id: int = int(timecamp_entry['task_id'])
        except (ValueError, TypeError):
            error_msg = "Entry '{id}': Invalid task id '{task_id}'"
            raise ParseError(error_msg.format(**timecamp_entry))

        try:
            day: date = date.fromisoformat(timecamp_entry['date'])
        except ValueError:
            error_msg = "Entry '{id}': Invalid date format '{date}'"
            raise ParseError(error_msg.format(**timecamp_entry))

        try:
            raw_start_time = timecamp_entry['start_time']
            start_time: time = datetime.strptime(raw_start_time, Format.HMS).time()
        except ValueError:
            error_msg = "Entry '{id}': Invalid start time format '{start_time}'"
            raise ParseError(error_msg.format(**timecamp_entry))

        try:
            raw_end_time = timecamp_entry['end_time']
            end_time: time = datetime.strptime(raw_end_time, Format.HMS).time()
        except ValueError:
            error_msg = "Entry '{id}': Invalid end time format '{end_time}'"
            raise ParseError(error_msg.format(**timecamp_entry))

        start = datetime.combine(day, start_time).replace(tzinfo=timezone.utc).astimezone()
        end = datetime.combine(day, end_time).replace(tzinfo=timezone.utc).astimezone()

        text = timecamp_entry['description']

        return GenericEntry(entry_id, task_id, start, end, text)

    @staticmethod
    def _parse_title_(raw_task: TimecampTask) -> Tuple[str, str]:
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
        level=1,
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
