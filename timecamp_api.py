from __future__ import annotations

import sys

from datetime import date
from operator import itemgetter
from typing import List, Mapping, Sequence, TypedDict, cast

from api import Backend, Credentials
from config import CONFIG


class TimecampTask(TypedDict):
    task_id: int
    parent_id: int
    level: int
    name: str


class TimecampEntry(TypedDict):
    id: int
    duration: str
    task_id: str
    date: str
    start_time: str
    end_time: str
    name: str
    description: str


class Timecamp(Backend):
    """Timecamp API docs: https://developer.timecamp.com"""

    api = 'https://app.timecamp.com/third_party/api'

    @classmethod
    def login(cls, credentials: Credentials):
        super().login(credentials)
        assert cls._session_ is not None

        cls._session_.headers.update({'Content-Type': 'application/json'})
        cls._session_.headers.update({'Authorization': credentials['key']})

    @classmethod
    def logout(cls):
        super().logout()

    @classmethod
    def get_tasks(cls) -> Sequence[TimecampTask]:
        response = cls._get_('tasks', format='json')
        assert isinstance(response, Mapping)
        assert all('level' in raw_task for raw_task in response.values())

        raw_tasks: List[TimecampTask] = sorted(response.values(), key=itemgetter('level'))
        return raw_tasks

    @classmethod
    def get_entries(cls, start: date, end: date) -> Sequence[TimecampEntry]:
        args = {'from': start.isoformat(), 'to': end.isoformat()}
        response = cls._get_('entries', format='json', **args)
        assert isinstance(response, Sequence)

        raw_entries: List[TimecampEntry] = cast(List[TimecampEntry], response)
        return raw_entries


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['tasks']:
            Timecamp.login({'key': CONFIG.api.timecamp.key})
            response = Timecamp.get_tasks()
            print(f"Response: {type(response)}")
            print(response)
            Timecamp.logout()

        case ['entries']:
            Timecamp.login({'key': CONFIG.api.timecamp.key})
            response = Timecamp.get_entries(start=date(2023, 2, 27), end=date(2023, 3, 2))
            print(f"Response: {type(response)}")
            print(response)
            Timecamp.logout()

        case other:
            pass
