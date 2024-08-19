from __future__ import annotations

import re
import sys
from datetime import date, datetime, time

from adapter import BackendAdapter, BackendDataError, GenericEntry, GenericTask
from api import BackendData
from timecamp_api import TimecampEntry, TimecampTask
from tools import CURRENT_TZ, Format, unwrap


JIRA_REGEX = re.compile(r'jira:\s?([A-Z0-9]+-[0-9]+)', re.IGNORECASE)
SPEC_REGEX = re.compile(r'spec:\s?([A-Z]+)', re.IGNORECASE)


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
        jira = cls._get_jira_(timecamp_task)
        spec = cls._get_spec_(timecamp_task)

        return GenericTask(task_id, parent_id, title, jira, spec)

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
    def _get_jira_(raw_task: TimecampTask) -> str | None:
        for line in raw_task['note'].splitlines():
            jira_match = JIRA_REGEX.match(line)
            if jira_match:
                return jira_match.group(1)
        return None

    @staticmethod
    def _get_spec_(raw_task: TimecampTask) -> str | None:
        for line in raw_task['note'].splitlines():
            spec_match = SPEC_REGEX.match(line)
            if spec_match:
                return spec_match.group(1)
        return None


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
        note='\n'.join(("jira: TEST-42", "spec: TT", "Test task description")),
    )

    match sys.argv[1:]:
        case ['entry']:
            test_entry = TimecampAdapter.parse_entry(test_raw_entry)
            print(test_entry)

        case ['task']:
            test_task = TimecampAdapter.parse_task(test_raw_task)
            print(test_task)

        case ['jira']:
            test_jira = TimecampAdapter._get_jira_(test_raw_task)
            print(test_jira)

        case ['spec']:
            test_spec = TimecampAdapter._get_spec_(test_raw_task)
            print(test_spec)

        case other:
            pass
