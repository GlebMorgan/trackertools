from __future__ import annotations

import sys

from config_loader import ConfigDict, JsonLoader, KeyValueLoader
from tools import noop


CONFIG = ConfigDict(
    debug=True,
    scrollback=False,
    cache_path='./__cache__',
    backend='timecamp',
    credentials=ConfigDict(
        timeular=KeyValueLoader("credentials/timeular.cfg"),
        timecamp=KeyValueLoader("credentials/timecamp.cfg"),
        jira=KeyValueLoader("credentials/jira.cfg"),
    ),
    tasks=JsonLoader("config/tasks.json"),
    specs=JsonLoader("config/specs.json"),
    users=JsonLoader("config/users.json"),
    projects=JsonLoader("config/projects.json"),
)

trace = print if CONFIG.debug is True or '-d' in sys.argv else noop
