import sys

from datetime import date
from typing import Any, ClassVar, Dict, List, Sequence, TypedDict

from requests import Session

from config import trace
from tools import AppError


Json = Dict[str, Any] | List[Dict[str, Any]]


class Backend:
    api: ClassVar[str]

    @classmethod
    def login(cls, credentials: Dict[str, str]):
        if cls._session_ is not None:
            trace("Already logged in")
            return
        cls._session_ = Session()

    @classmethod
    def logout(cls):
        if cls._session_ is not None:
            cls._session_.close()
            cls._session_ = None

    @classmethod
    def get_tasks(cls) -> Sequence[TypedDict]:
        raise NotImplementedError

    @classmethod
    def get_entries(cls, start: date, end: date) -> Sequence[TypedDict]:
        raise NotImplementedError

    _session_: ClassVar[Session | None] = None

    @classmethod
    def _get_(cls, path: str, **kwargs: Any) -> Json:
        if cls._session_ is None:
            raise AppError("Session is not open")
        response = cls._session_.get(f'{cls.api}/{path}', params=kwargs)
        if not response:
            raise AppError(f"GET /{path} - code {response.status_code} - {response.text}")
        trace(f"GET /{path} - OK {response.status_code}")
        return response.json()

    @classmethod
    def _post_(cls, path: str, request: Json | None = None) -> Json:
        if cls._session_ is None:
            raise AppError("Session is not open")
        response = cls._session_.post(f'{cls.api}/{path}', json=request)
        if not response:
            raise AppError(f"POST /{path} - code {response.status_code} - {response.text}")
        trace(f"POST /{path} - OK {response.status_code}")
        return response.json() if request else {}


if __name__ == '__main__':
    # pyright: reportPrivateUsage=false

    class HTTPBin(Backend):
        api = 'https://httpbin.org'

    match sys.argv[1:]:
        case ['get']:
            HTTPBin.login({})
            reply = HTTPBin._get_("get")
            print(reply)
            HTTPBin.logout()

        case ['post']:
            HTTPBin.login({})
            request = {'key': 'value'}
            reply = HTTPBin._post_("post", request)
            print(reply)
            HTTPBin.logout()

        case other:
            pass
