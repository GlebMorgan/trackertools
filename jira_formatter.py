from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import cached_property
from re import Match, Pattern
from typing import Any, ClassVar, Iterable, Type, TypeAlias

from config import CONFIG
from task import Task


MarkupList: TypeAlias = Iterable[str] | None


class Markup:
    @dataclass(slots=True, frozen=True)
    class Result:
        text: str
        substitutions: int
        complete: bool = False

    all: ClassVar[dict[str, Type[Markup]]] = {}
    pattern: ClassVar[Pattern[str]]

    def __init_subclass__(cls, /, name: str, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        Markup.all[name] = cls

    def apply(self, task: Task, text: str) -> Markup.Result:
        raise NotImplementedError


class CodeMarkup(Markup, name='code'):
    pattern: ClassVar[Pattern[str]] = re.compile(r'`(.*?)`')

    def apply(self, task: Task, text: str) -> Markup.Result:
        output, substitutions = self.pattern.subn(r'_{{\1}}_', text)
        return Markup.Result(output, substitutions)


class HyphenMarkup(Markup, name='hyphen'):
    pattern: ClassVar[Pattern[str]] = re.compile(r' -- ')

    def apply(self, task: Task, text: str) -> Markup.Result:
        output, substitutions = self.pattern.subn(r' – ', text)
        return Markup.Result(output, substitutions)


class URLMarkup(Markup, name='url'):
    pattern: ClassVar[Pattern[str]] = re.compile(r'\[(.*?)\]\((.*?)\)')

    def apply(self, task: Task, text: str) -> Markup.Result:
        output, substitutions = self.pattern.subn(r'[\1|\2]', text)
        return Markup.Result(output, substitutions)


class UserMarkup(Markup, name='user'):
    pattern: ClassVar[Pattern[str]] = re.compile(r'@([A-z]+(?:\.[A-z]+)?)')

    users: dict[str, str]

    def __init__(self):
        self.users = CONFIG.users

    def _format_user_(self, match: Match[str]) -> str:
        user = match.group(1)
        try:
            return self.users[user]
        except KeyError:
            print(f"[ERROR] User '{user}' is not found in users spec")
            return match.group(0)

    def apply(self, task: Task, text: str) -> Markup.Result:
        output, substitutions = re.subn(self.pattern, self._format_user_, text)
        return Markup.Result(output, substitutions)


class MRLinkMarkup(Markup, name='mr-link'):
    # https://gps-gitlab.teltonika.lt/fleet/tms/teltonika-tdf/-/merge_requests/42
    BASE_URL: ClassVar[str] = 'https://gps-gitlab.teltonika.lt'
    pattern: ClassVar[Pattern[str]] = re.compile(
        (
            r'{gitlab_base_url}'
            r'(?P<project_path>(?:/{id})+)/-/merge_requests/'
            r'(?P<mr_id>\d+)'
            r'(?P<subpath>/{id})*'
            r'(?P<url_query>\?{id}={id})?'
            r'(?P<url_params>&{id}={id})*'
            r'(?P<url_fragment>#{id})?'
        ).format(gitlab_base_url=re.escape(BASE_URL), id=r'[\w-]+')
    )

    projects: dict[str, str]

    def __init__(self):
        self.projects = CONFIG.projects

    def _format_project_(self, match: Match[str]) -> str:
        project = match.group('project_path')
        try:
            alias = self.projects[project]
        except KeyError:
            print(f"[ERROR] Project '{project}' is not found in projects spec")
            return match.group(0)
        short_link = f"{alias}/{match.group('mr_id')}"
        return f"[{short_link}|{match.group(0)}]"

    def apply(self, task: Task, text: str) -> Markup.Result:
        output, substitutions = re.subn(self.pattern, self._format_project_, text)
        return Markup.Result(output, substitutions)


class MRReviewMarkup(MRLinkMarkup, name='mr-review'):
    def apply(self, task: Task, text: str) -> Markup.Result:
        if not self.pattern.fullmatch(text):
            return Markup.Result(text, 0)
        result = super().apply(task, text)
        output = f"MR {result.text} review"
        return Markup.Result(output, 1, complete=True)


class SprintMeetingMarkup(Markup, name='meeting'):
    @classmethod
    def _is_meeting_task_(cls, task: Task | None) -> bool:
        if task is None:
            return False
        if task.name == "Meeting":
            return True
        return cls._is_meeting_task_(task.parent)

    def apply(self, task: Task, text: str) -> Markup.Result:
        # TODO: refactor this and remove _is_meeting_task_() method
        if not self._is_meeting_task_(task):
            return Markup.Result(text, 0)

        if task.name == "StandUp":
            output = task.name if not text else f"{task.name}: {text}"
        elif task.name.startswith("Sprint"):
            if not text:
                output = f"{task.name} meeting"
            elif text.isdecimal():
                output = f"{task.name} {text} meeting"
            else:
                return Markup.Result(text, 0)
        else:
            return Markup.Result(text, 0)

        return Markup.Result(output, 1, complete=True)


class JiraFormatter:
    DEFAULT_FORMATTERS: ClassVar[list[str]] = [
        'mr-review',
        'meeting',
        'mr-link',
        'user',
        'code',
        'hyphen',
    ]

    formatters: list[str]

    def __init__(self, formatters: MarkupList = None, exclude: MarkupList = None):
        if formatters is None:
            formatters = self.DEFAULT_FORMATTERS
        if exclude is not None:
            formatters = [item for item in formatters if item not in exclude]
        self.formatters = list(formatters)

    @cached_property
    def markups(self) -> list[Markup]:
        return [Markup.all[formatter]() for formatter in self.formatters]

    def format(self, task: Task, text: str) -> str:
        output = text
        for markup in self.markups:
            result = markup.apply(task, output)
            if result.complete is True:
                return result.text
            if result.substitutions > 0:
                output = result.text

        # TODO: Change this to apply only to children of General task
        if not output and task.name in CONFIG.tasks:
            output = task.name.lower().capitalize()
        return output


if __name__ == '__main__':
    from task import TaskId

    mode = sys.argv[1] if len(sys.argv) > 1 else 'example'

    formatter = JiraFormatter()

    meeting_task = Task(TaskId(13), None, "Meeting", None, None)
    sprint_task = Task(TaskId(28), meeting_task, "Sprint Review", None, None)
    standup_task = Task(TaskId(37), meeting_task, "Standup", None, None)
    test_task = Task(TaskId(42), None, "Some Task", None, None)

    if mode == 'example':
        res = formatter.format(
            test_task,
            "Discuss MR "
            "https://gps-gitlab.teltonika.lt/fleet/tms/teltonika-tdf"
            "/-/merge_requests/666/diffs"
            "?commit_id=f1557db17a036bc7a013c9fe017747f40c0e50b6&test=42"
            "#6a1cedd04f2a144f2720e56745b259dfab28ed9c_313_313 "
            "with @Kirill\n"
            "Discuss `--some-option` -- with @Kirill\n",
        )
        print(res)

    if mode == 'meeting':
        res = formatter.format(meeting_task, "Goofy discussion with @Kirill")
        print(res)

    if mode == 'sprint':
        res = formatter.format(sprint_task, "123")
        print(res)

    if mode == 'standup':
        res = formatter.format(standup_task, "")
        print(res)

    if mode == 'empty':
        res = formatter.format(test_task, "")
        print(res)
