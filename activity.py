import json
import re
import sys
from dataclasses import dataclass
from typing import ClassVar, Dict, List, Tuple

from api import TActivity
from api import Timeular as server
from config import CONFIG
from tools import AppError, CacheError, unwrap


JIRA_TASK_REGEX = re.compile(r'\[(?P<jira>[A-Z-0-9]+)\](?: \((?P<client>\w+)\))? (?P<title>.*)')


@dataclass(frozen=True, slots=True)
class Activity:
    id: int
    name: str
    jira: str|None
    spec: str|None

    all: ClassVar[Dict[int, "Activity"]] = {}
    cache: ClassVar[str] = 'timeular-activities.json'

    def __post_init__(self):
        self.__class__.all[self.id] = self

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and self.id == other.id

    def __str__(self):
        spec = f'({self.spec})' if self.spec else None
        return ' '.join(filter(None, (self.jira, self.name, spec)))

    def __class_getitem__(cls, id: int) -> "Activity":
        try:
            return cls.all[id]
        except KeyError:
            if not cls.all:
                raise AppError("Activities are not initialized")
            else:
                raise AppError(f"Unknown activity id {id}")

    @classmethod
    def _parse_general_task_(cls, title: str) -> str|None:
        title = unwrap(title)
        if not title:
            raise AppError(f"Empty activity title")
        if title not in CONFIG.general_tasks:
            raise AppError(f"Invalid task: {title}")
        return CONFIG.general_tasks[title]

    @classmethod
    def _parse_client_(cls, title: str, client_id: str|None) -> str|None:
        if client_id is None:
            return None
        if client_id in CONFIG.client_names:
            return CONFIG.client_names[client_id]
        else:
            raise AppError(f"Unknown client abbreviation: '{client_id}'. Task: {title}")

    @classmethod
    def _parse_title_(cls, title: str) -> Tuple[str, str|None, str|None]:
        if match := JIRA_TASK_REGEX.match(title):
            if '-' in match['jira']:
                jira_id = match['jira']
            else:
                jira_id = f"FM64-{match['jira']}"
            client = cls._parse_client_(title, match['client'])
            if not (name := match['title']):
                raise AppError(f"Empty activity title")
            return (name, jira_id, client)
        else:
            name = unwrap(title).strip()
            jira = cls._parse_general_task_(title)
            return (name, jira, None)

    @classmethod
    def _update_activities_(cls, timeular_activities: List[TActivity]):
        cls.all.clear()
        for timeular_activity in timeular_activities:
            cls.gen(timeular_activity)

    @classmethod
    def _update_cache_(cls, timeular_activities: List[TActivity]):
        cache_file = CONFIG.cache_path / cls.cache
        cache_file.resolve().write_text(json.dumps(timeular_activities))

    @classmethod
    def gen(cls, timeular_activity: TActivity) -> "Activity":
        id = int(timeular_activity['id'])
        if id in cls.all:
            raise RuntimeError(f"Activity with {id=} already exists: {cls.all[id]}")
        name, jira, spec = cls._parse_title_(timeular_activity['name'])
        return cls(id, name, jira, spec)

    @classmethod
    def clear_cache(cls):
        cache_file = CONFIG.cache_path / cls.cache
        cache_file.resolve().unlink()

    @classmethod
    def load(cls):
        cache_file = CONFIG.cache_path / cls.cache
        if not cache_file.exists():
            raise CacheError(f"Cache miss on {cache_file.name}")
        with cache_file.resolve().open(encoding='utf-8') as file:
            timeular_activities = json.load(file)
        cls._update_activities_(timeular_activities)

    @classmethod
    def fetch(cls):
        timeular_activities = server.get_activities()
        cls._update_cache_(timeular_activities)
        cls._update_activities_(timeular_activities)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if mode == 'fetch':
        server.login(CONFIG.timeular['key'], CONFIG.timeular['secret'])
        Activity.fetch()
        server.logout()
        print(*Activity.all.values(), sep='\n')

    if mode == 'list':
        Activity.load()
        print(*Activity.all.values(), sep='\n')
