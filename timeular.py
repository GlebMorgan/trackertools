import sys

from datetime import date, datetime, time
from typing import Any, Dict, List, Sequence, Tuple, TypedDict

from api import Backend
from config import CONFIG, trace


class TimeularTask(TypedDict):
    id: str
    name: str


class TimeularEntry(TypedDict):
    id: str
    activityId: str
    duration: Dict[str, Any]
    note: Dict[str, Any]


class TimeularTag(TypedDict):
    id: str
    label: str
    spaceId: str


class TimeularMention(TypedDict):
    id: str
    label: str
    spaceId: str


class TimeularSpace(TypedDict):
    id: str
    name: str
    members: List[Dict[str, Any]]


class Timeular(Backend):
    """
    Timeular API docs: https://developers.timeular.com
    """

    api = 'https://api.timeular.com/api/v3'

    @classmethod
    def login(cls, credentials: Dict[str, str] = {}):
        super().login(credentials)
        assert cls._session_ is not None

        api_keys = {'apiKey': credentials['key'], 'apiSecret': credentials['secret']}
        response = cls._post_('developer/sign-in', request=api_keys)
        assert isinstance(response, dict)

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
        assert isinstance(response, dict)

        tasks: List[TimeularTask] = response['activities']
        assert type(tasks) is list

        return tasks

    @classmethod
    def get_entries(cls, start: date, end: date) -> Sequence[TimeularEntry]:
        start_iso = datetime.combine(start, time.min).isoformat(timespec='milliseconds')
        end_iso = datetime.combine(end, time.max).isoformat(timespec='milliseconds')

        response = cls._get_(f'time-entries/{start_iso}/{end_iso}')
        assert isinstance(response, dict)

        entries: List[TimeularEntry] = response['timeEntries']
        return entries

    @classmethod
    def get_tags(cls) -> Tuple[Sequence[TimeularTag], Sequence[TimeularMention]]:
        response = cls._get_('tags-and-mentions')
        assert isinstance(response, dict)

        tags: List[TimeularTag] = response['tags']
        assert type(tags) is list

        mentions: List[TimeularMention] = response['mentions']
        assert type(mentions) is list

        return tags, mentions

    @classmethod
    def get_spaces(cls) -> Sequence[TimeularSpace]:
        response = cls._get_('space')
        assert isinstance(response, dict)

        spaces: List[TimeularSpace] = response['data']
        assert type(spaces) is list

        return spaces


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['tasks']:
            credentials = {
                'key': CONFIG.api.timeular.key,
                'secret': CONFIG.api.timeular.secret,
            }
            Timeular.login(credentials)
            response = Timeular.get_tasks()
            print(type(response))
            print(response)
            Timeular.logout()

        case ['entries']:
            credentials = {
                'key': CONFIG.api.timeular.key,
                'secret': CONFIG.api.timeular.secret,
            }
            Timeular.login(credentials)
            response = Timeular.get_entries(start=date(2023, 2, 23), end=date(2023, 2, 25))
            print(type(response))
            print(response)
            Timeular.logout()

        case other:
            pass
