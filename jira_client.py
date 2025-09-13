from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import ClassVar

from jira import JIRA, JIRAError, Worklog

from config import CONFIG


@dataclass
class TimeEstimate:
    estimated: int
    remaining: int
    logged: int


class Jira:
    URL: ClassVar[str] = "https://jira.teltonika.lt"

    _server_: ClassVar[JIRA | None] = None

    @classmethod
    def login(cls, token: str):
        if cls._server_ is not None:
            return
        cls._server_ = JIRA(server=cls.URL, token_auth=token)

    @classmethod
    def logout(cls):
        if cls._server_ is not None:
            cls._server_.close()
            cls._server_ = None

    @classmethod
    def add_worklog(
        cls, task_id: str, duration: str, started: datetime, comment: str
    ) -> Worklog | None:
        assert cls._server_ is not None
        try:
            return cls._server_.add_worklog(
                task_id, timeSpent=duration, started=started, comment=comment
            )
        except JIRAError as exception:
            print("[ERROR] Failed to add Jira worklog")
            print(exception)
            return None

    @classmethod
    def delete_worklog(cls, task_id: str, worklog_id: int):
        assert cls._server_ is not None
        # TODO: Handle exceptions
        worklog = cls._server_.worklog(issue=task_id, id=worklog_id)
        worklog.delete()

    @classmethod
    @lru_cache(maxsize=16)
    def get_timetracking(cls, task_id: str) -> TimeEstimate | None:
        assert cls._server_ is not None
        assert task_id is not None

        issue = cls._server_.issue(task_id)
        timetracking = issue.fields.timetracking

        original_estimate = getattr(timetracking, 'originalEstimateSeconds', 0)
        remaining_estimate = getattr(timetracking, 'remainingEstimateSeconds', 0)
        time_spent = getattr(timetracking, 'timeSpentSeconds', 0)

        return TimeEstimate(
            estimated=original_estimate,
            remaining=remaining_estimate,
            logged=time_spent,
        )


if __name__ == '__main__':
    # pylint: disable=protected-access
    Jira.login(CONFIG.credentials.jira.token)
    tracking = Jira.get_timetracking('DEV3-75')
    Jira.logout()
