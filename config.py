from __future__ import annotations

import sys

from config_loader import ConfigDict, JsonLoader, KeyValueLoader, TomlLoader
from tools import AppError, noop


class ConfigError(AppError):
    pass


CONFIG = ConfigDict(
    debug=True,
    scrollback=True,
    cache_path='./__cache__',
    backend='timecamp',
    credentials=ConfigDict(
        timeular=KeyValueLoader("keys/timeular.cfg"),
        timecamp=KeyValueLoader("keys/timecamp.cfg"),
        jira=KeyValueLoader("keys/jira.cfg"),
    ),
    tasks=TomlLoader("config/tasks.toml"),
    specs=JsonLoader("config/specs.json"),
    users=JsonLoader("config/users.json"),
    projects=JsonLoader("config/projects.json"),
)

# TODO: Move this to tools.py if possible
trace = print if CONFIG.debug is True or '-d' in sys.argv else noop
