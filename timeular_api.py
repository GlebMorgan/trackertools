from __future__ import annotations

import sys

from datetime import date, datetime, time
from typing import Mapping, Sequence, Tuple, TypedDict

from api import Backend, Credentials
from config import CONFIG, trace


class TimeularSpace(TypedDict):
    id: str
    name: str
    members: Sequence[Mapping[str, str]]


class TimeularTag(TypedDict):
    id: int
    label: str


class TimeularMention(TypedDict):
    id: int
    label: str


class TimeularTask(TypedDict):
    id: str
    name: str


class TimeularEntryNote(TypedDict):
    text: str | None
    tags: Sequence[TimeularTag]
    mentions: Sequence[TimeularMention]


class TimeularEntryDuration(TypedDict):
    startedAt: str
    stoppedAt: str


class TimeularEntry(TypedDict):
    id: str
    activityId: str
    duration: TimeularEntryDuration
    note: TimeularEntryNote


class Timeular(Backend):
    """Timeular API docs: https://developers.timeular.com"""

    api = 'https://api.timeular.com/api/v3'

    @classmethod
    def login(cls, credentials: Credentials):
        super().login(credentials)
        assert cls._session_ is not None
        assert 'secret' in credentials

        api_keys = {'apiKey': credentials['key'], 'apiSecret': credentials['secret']}
        response = cls._post_('developer/sign-in', request=api_keys)
        assert isinstance(response, Mapping)

        cls._session_.headers.update({'Content-Type': 'application/json'})
        cls._session_.headers.update({'Authorization': f"Bearer {response['token']}"})

    @classmethod
    def logout(cls):
        if cls._session_ is not None:
            response = cls._post_('developer/logout')
            trace(f"Response = {response}")
        super().logout()

    @classmethod
    def get_tasks(cls) -> Sequence[TimeularTask]:
        response = cls._get_('activities')
        assert isinstance(response, Mapping)

        tasks: Sequence[TimeularTask] = response['activities']
        assert isinstance(tasks, Sequence)

        return tasks

    @classmethod
    def get_entries(cls, start: date, end: date) -> Sequence[TimeularEntry]:
        start_iso = datetime.combine(start, time.min).isoformat(timespec='milliseconds')
        end_iso = datetime.combine(end, time.max).isoformat(timespec='milliseconds')

        response = cls._get_(f'time-entries/{start_iso}/{end_iso}')
        assert isinstance(response, Mapping)

        entries: Sequence[TimeularEntry] = response['timeEntries']
        assert isinstance(entries, Sequence)

        return entries

    @classmethod
    def get_tags(cls) -> Tuple[Sequence[TimeularTag], Sequence[TimeularMention]]:
        response = cls._get_('tags-and-mentions')
        assert isinstance(response, Mapping)

        tags: Sequence[TimeularTag] = response['tags']
        assert isinstance(tags, Sequence)

        mentions: Sequence[TimeularMention] = response['mentions']
        assert isinstance(mentions, Sequence)

        return tags, mentions

    @classmethod
    def get_spaces(cls) -> Sequence[TimeularSpace]:
        response = cls._get_('space')
        assert isinstance(response, Mapping)

        spaces: Sequence[TimeularSpace] = response['data']
        assert isinstance(spaces, Sequence)

        return spaces


if __name__ == '__main__':
    credentials = Credentials(
        key=CONFIG.api.timeular.key,
        secret=CONFIG.api.timeular.secret,
    )

    match sys.argv[1:]:
        case ['tasks']:
            Timeular.login(credentials)
            response = Timeular.get_tasks()
            print(f"Response: {type(response)}")
            print(response)
            Timeular.logout()

        case ['entries']:
            Timeular.login(credentials)
            response = Timeular.get_entries(start=date(2023, 1, 23), end=date(2023, 1, 25))
            print(f"Response: {type(response)}")
            print(response)
            Timeular.logout()

        case other:
            pass
