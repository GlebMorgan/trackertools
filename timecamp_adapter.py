from __future__ import annotations

import re
import sys
from datetime import date, datetime, time

from adapter import BackendAdapter, BackendDataError, GenericEntry, GenericTask
from api import BackendData
from timecamp_api import TimecampEntry, TimecampTask
from tools import CURRENT_TZ, Format, unwrap


PROPERTY_REGEX = re.compile(r'(\w+):\s*(.+)', re.IGNORECASE)


class TimecampAdapter(BackendAdapter):
    @classmethod
    def parse_task(cls, raw_task: BackendData) -> GenericTask:
        timecamp_task = TimecampTask(**raw_task)
        try:
            task_id: int = int(timecamp_task['task_id'])
        except (ValueError, TypeError) as cause:
            error_msg = "Invalid task id '{task_id}'"
            raise BackendDataError(error_msg.format(**timecamp_task)) from cause

        try:
            parent_id: int = int(timecamp_task['parent_id'])
        except (ValueError, TypeError) as cause:
            error_msg = "Task '{task_id}': Invalid parent id '{parent_id}'"
            raise BackendDataError(error_msg.format(**timecamp_task)) from cause

        title = unwrap(timecamp_task['name'].strip())
        properties = cls._get_properties_(timecamp_task)

        return GenericTask(task_id, parent_id, title, properties)

    @classmethod
    def parse_entry(cls, raw_entry: BackendData) -> GenericEntry:
        timecamp_entry = TimecampEntry(**raw_entry)
        try:
            entry_id: int = int(timecamp_entry['id'])
        except (ValueError, TypeError) as cause:
            error_msg = "Invalid entry id '{id}'"
            raise BackendDataError(error_msg.format(**timecamp_entry)) from cause

        try:
            task_id: int = int(timecamp_entry['task_id'])
        except (ValueError, TypeError) as cause:
            error_msg = "Entry '{id}': Invalid task id '{task_id}'"
            raise BackendDataError(error_msg.format(**timecamp_entry)) from cause

        try:
            day: date = date.fromisoformat(timecamp_entry['date'])
        except ValueError as cause:
            error_msg = "Entry '{id}': Invalid date format '{date}'"
            raise BackendDataError(error_msg.format(**timecamp_entry)) from cause

        try:
            raw_start_time = timecamp_entry['start_time']
            start_time: time = datetime.strptime(raw_start_time, Format.HMS).time()
        except ValueError as cause:
            error_msg = "Entry '{id}': Invalid start time format '{start_time}'"
            raise BackendDataError(error_msg.format(**timecamp_entry)) from cause

        try:
            raw_end_time = timecamp_entry['end_time']
            end_time: time = datetime.strptime(raw_end_time, Format.HMS).time()
        except ValueError as cause:
            error_msg = "Entry '{id}': Invalid end time format '{end_time}'"
            raise BackendDataError(error_msg.format(**timecamp_entry)) from cause

        start = datetime.combine(day, start_time, tzinfo=CURRENT_TZ)
        end = datetime.combine(day, end_time, tzinfo=CURRENT_TZ)

        text = timecamp_entry['description']

        return GenericEntry(entry_id, task_id, start, end, text)

    @staticmethod
    def _get_properties_(raw_task: TimecampTask) -> dict[str, str]:
        properties: dict[str, str] = {}
        for line in raw_task['note'].splitlines():
            prop_match = PROPERTY_REGEX.match(line.strip())
            if prop_match:
                key = prop_match.group(1).lower()
                value = prop_match.group(2).strip()
                properties[key] = value
        return properties


if __name__ == '__main__':
    # pylint: disable=protected-access

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
        note="""
             Type: Ticket
             Jira: FMXX-1234
             Spec: TT
             Description: Test task description
             """,
    )

    match sys.argv[1:]:
        case ['entry']:
            test_entry = TimecampAdapter.parse_entry(test_raw_entry)
            print(test_entry)

        case ['task']:
            test_task = TimecampAdapter.parse_task(test_raw_task)
            print(test_task)

        case ['props']:
            test_props = TimecampAdapter._get_properties_(test_raw_task)
            print(test_props)

        case other:
            pass
