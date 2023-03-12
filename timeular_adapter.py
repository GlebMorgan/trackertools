from __future__ import annotations

import re
import sys

from datetime import datetime, timezone
from typing import Dict, List, Sequence, Tuple, cast

from adapter import BackendAdapter, GenericEntry, GenericTask, ParseError
from api import BackendData
from timeular_api import TimeularEntry, TimeularEntryNote
from timeular_api import TimeularMention, TimeularTag, TimeularTask
from tools import unwrap


# JIRA_REGEX = re.compile(r'\[([A-Z0-9]+-[0-9]+)\] ')
# SPEC_REGEX = re.compile(r'\((\w+)\) ')
TASK_NAME_REGEX = re.compile(
    r'(?:\[(?P<jira>[A-Z-0-9]+)\])?\s*(?:\((?P<spec>\w+)\))?\s*(?:(?P<title>.+))?'
)


class TimeularAdapter(BackendAdapter):
    @classmethod
    def parse_task(cls, raw_task: BackendData) -> GenericTask:
        timeular_task = cast(TimeularTask, raw_task)
        try:
            task_id: int = int(timeular_task['id'])
        except (ValueError, TypeError):
            error_msg = "Invalid task id '{id}'"
            raise ParseError(error_msg.format(**timeular_task))

        title, jira, spec = cls._parse_title_(timeular_task)

        return GenericTask(task_id, None, title, jira, spec)

    @classmethod
    def parse_entry(cls, raw_entry: BackendData) -> GenericEntry:
        timeular_entry = cast(TimeularEntry, raw_entry)
        try:
            entry_id: int = int(timeular_entry['id'])
        except (ValueError, TypeError):
            error_msg = "Invalid entry id '{id}'"
            raise ParseError(error_msg.format(**timeular_entry))

        try:
            task_id: int = int(timeular_entry['activityId'])
        except (ValueError, TypeError):
            error_msg = "Entry '{id}': Invalid task id '{activityId}'"
            raise ParseError(error_msg.format(**timeular_entry))

        try:
            raw_start_timestamp = timeular_entry['duration']['startedAt']
            start: datetime = datetime.fromisoformat(raw_start_timestamp)
        except ValueError:
            error_msg = "Entry '{id}': Invalid start time format '{duration[startedAt]}'"
            raise ParseError(error_msg.format(**timeular_entry))

        try:
            raw_end_timestamp = timeular_entry['duration']['stoppedAt']
            end: datetime = datetime.fromisoformat(raw_end_timestamp)
        except ValueError:
            error_msg = "Entry '{id}': Invalid end time format '{duration[stoppedAt]}'"
            raise ParseError(error_msg.format(**timeular_entry))

        start = start.replace(tzinfo=timezone.utc).astimezone()
        end = end.replace(tzinfo=timezone.utc).astimezone()

        text = cls._parse_tags_(timeular_entry['note'])

        return GenericEntry(entry_id, task_id, start, end, text)

    @staticmethod
    def _parse_title_(raw_task: TimeularTask) -> Tuple[str, str, str]:
        # TODO: review the algorithm

        match = TASK_NAME_REGEX.match(raw_task['name'].strip())

        if not match:
            error_msg = "Task '{id}': Invalid task name format: '{name}'"
            raise ParseError(error_msg.format(**raw_task))

        title = match['title']
        if title is None:
            error_msg = "Task '{id}': Missing task title: '{name}'"
            raise ParseError(error_msg.format(**raw_task))
        title = unwrap(title).strip()

        jira = match['jira']
        if jira is not None:
            if '-' not in jira:
                jira = f"FM64-{jira}"

        spec = match['spec']
        if spec is not None and jira is None:
            error_msg = "Task '{id}': Missing jira id: '{name}'"
            raise ParseError(error_msg.format(**raw_task))

        return title, jira, spec

    @classmethod
    def _parse_tags_(cls, raw_entry_note: TimeularEntryNote) -> str:
        Mentions = List[Dict[str, str | int]]

        text: str | None = raw_entry_note['text']
        if text is None:
            return ''

        tags: Sequence[TimeularTag] = raw_entry_note['tags']
        for tag in tags:
            id = tag['id']
            label = tag['label']
            text = text.replace(f"<{{{{|t|{id}|}}}}>", label)

        mentions: Sequence[TimeularMention] = raw_entry_note['mentions']
        for mention in mentions:
            id = mention['id']
            label = mention['label']
            text = text.replace(f"<{{{{|m|{id}|}}}}>", f"@{label}")

        return text


if __name__ == '__main__':
    # pyright: reportPrivateUsage=false

    test_raw_entry = TimeularEntry(
        id='59706926',
        activityId='1225816',
        duration={
            'startedAt': '2022-05-27T08:00:00.000',
            'stoppedAt': '2022-05-27T09:10:00.000',
        },
        note=TimeularEntryNote(
            text='<{{|t|2693042|}}> 71 (with <{{|m|205973|}}>)',
            tags=[TimeularTag(id=2693042, label='Sprint')],
            mentions=[TimeularMention(id=205973, label='Person')],
        ),
    )

    test_raw_task = TimeularTask(
        id='1006908',
        name="[FMXX-1234] (TT) Task name (valid)",
    )

    match sys.argv[1:]:
        case ['entry']:
            entry = TimeularAdapter.parse_entry(test_raw_entry)
            print(entry)

        case ['task']:
            task = TimeularAdapter.parse_task(test_raw_task)
            print(task)

        case ['title']:
            title, jira, spec = TimeularAdapter._parse_title_(test_raw_task)
            print(f"{title=}, {jira=}, {spec=}")

        case other:
            pass
