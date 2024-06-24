from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from re import Match, Pattern
from typing import Callable, ClassVar, Self, TypeAlias


# RegexReplacer: TypeAlias = Callable[["JiraFormatter", Match[str]], str]


class JiraFormatter:

    Test: TypeAlias = Callable[[Self, Match[str]], str]

    @dataclass(frozen=True, slots=True)
    class FormatSpec:
        pattern: Pattern[str]
        replacer: JiraFormatter.Test | str

    formatters: ClassVar[dict[str, FormatSpec]]

    features: set[str] = set()
    users: dict[str, str] | None
    projects: dict[str, str] | None

    def __init__(
        self,
        users: dict[str, str] | None = None,
        projects: dict[str, str] | None = None,
    ):
        self.users = users
        self.projects = projects
        self.features = set(self.formatters.keys())

    @staticmethod
    def _verify_file_(file_path: str) -> Path:
        file = Path(file_path)
        if file.suffix != '.json':
            raise ValueError(f"Expected .json file, got '{file.name}'")
        if not file.exists():
            raise FileNotFoundError(f"File '{file_path}' does not exist")
        return file

    def load_users(self, spec_path: str) -> Self:
        json_file = self._verify_file_(spec_path)

        with open(json_file, encoding='utf-8') as file:
            self.users = json.load(file)

        assert isinstance(self.users, dict)
        for user_reference in self.users.values():
            assert isinstance(user_reference, str)

        return self

    def load_projects(self, spec_path: str) -> Self:
        json_file = self._verify_file_(spec_path)

        with open(json_file, encoding='utf-8') as file:
            self.projects = json.load(file)

        assert isinstance(self.projects, dict)
        for project_alias in self.projects.values():
            assert isinstance(project_alias, str)

        return self

    def set_features(self, *features: str) -> Self:
        self.features = set(features)
        return self

    def exclude_features(self, *features: str) -> Self:
        self.features.difference_update(features)
        return self

    @staticmethod
    def _format_code_(text: str) -> str:
        return re.sub(r'`(.*?)`', r'{{\1}}', text)

    @staticmethod
    def _format_url_(text: str) -> str:
        return re.sub(r'\[(.*?)\]\((.*?)\)', r'[\1|\2]', text)

    def _format_user_(self, match: Match[str]) -> str:
        assert self.users is not None
        user = match.group(1)
        try:
            return self.users[user]
        except KeyError as cause:
            raise KeyError(f"User '{user}' is not found in users spec") from cause

    def format_user(self, text: str) -> str:
        return re.sub(r'@([A-z]+(?:\.[A-z]+)?)', self._format_user_, text)

    formatters = {
        'code': FormatSpec(re.compile(r'`(.*?)`'), r'{{\1}}'),
        'url': FormatSpec(re.compile(r'\[(.*?)\]\((.*?)\)'), r'[\1|\2]'),
        'user': FormatSpec(re.compile(r'@([A-z]+(?:\.[A-z]+)?)'), _format_user_),
    }

    def format(self, text: str) -> str:
        for feature in self.features:
            try:
                format_spec = self.formatters[feature]
            except KeyError as cause:
                raise ValueError(f"Unknown markup feature '{feature}'") from cause
            result = format_spec.pattern.sub(format_spec.replacer, text)
        return text


if __name__ == '__main__':
    formatter = JiraFormatter()
    formatter.load_users('config/users.json')
    formatter.load_projects('config/projects.json')
    formatter.exclude_features('code', 'url')
    res = formatter.format_user("Consult @Denis with smth")
