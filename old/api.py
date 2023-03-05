import sys

from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

from requests import Session

from tools import AppError, Json, noop


TEntry = Dict[str, Any]
TActivity = Dict[str, Any]


class Timeular:
    api = 'https://api.timeular.com/api/v3'
    _trace_: Callable[..., None] = print if '-d' in sys.argv else noop
    _session_: Session | None = None

    @classmethod
    def _get_(cls, path: str, **kwargs: Any) -> Json:
        if cls._session_ is None:
            raise AppError("Session is not open")
        response = cls._session_.get(f'{cls.api}/{path}', params=kwargs)
        if not response:
            raise AppError(f"GET /{path} - status {response.status_code} - {response.text}")
        cls._trace_(f"GET /{path} - OK {response.status_code}")
        return response.json()

    @classmethod
    def _post_(cls, path: str, request: Json | None = None) -> Json:
        if cls._session_ is None:
            raise AppError("Session is not open")
        response = cls._session_.post(f'{cls.api}/{path}', json=request)
        if not response:
            raise AppError(f"POST /{path} - status {response.status_code} - {response.text}")
        cls._trace_(f"POST /{path} - OK {response.status_code}")
        return response.json() if request else {}

    @classmethod
    def login(cls, key: str, secret: str):
        if cls._session_ is not None:
            cls._trace_("Already logged in")
            return

        cls._session_ = Session()
        cls._session_.headers.update({'Content-Type': 'application/json'})

        api_keys = {'apiKey': key, 'apiSecret': secret}
        response = cls._post_('developer/sign-in', api_keys)
        cls._trace_(f"Response = {response}")

        cls._session_.headers.update({'Authorization': f"Bearer {response['token']}"})

    @classmethod
    def logout(cls):
        if cls._session_ is not None:
            response = cls._post_('developer/logout')
            cls._trace_(f"Response = {response}")
            cls._session_.close()
            cls._session_ = None

    @classmethod
    def get_activities(cls) -> List[TActivity]:
        response = cls._get_('activities')
        return response['activities']

    @classmethod
    def get_entries(cls, start: datetime, end: datetime) -> List[TEntry]:
        start_iso = start.isoformat(timespec='milliseconds')
        end_iso = end.isoformat(timespec='milliseconds')
        response = cls._get_(f'time-entries/{start_iso}/{end_iso}')
        return response['timeEntries']

    @classmethod
    def get_tags(cls) -> Tuple[Json, Json]:
        response = cls._get_('tags-and-mentions')
        return response['tags'], response['mentions']

    @classmethod
    def get_spaces(cls) -> List[Json]:
        response = cls._get_('space')
        return response['data']
