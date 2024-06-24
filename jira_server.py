from __future__ import annotations

from typing import ClassVar

from jira import JIRA, Worklog

from config import CONFIG
from entry import Entry


class Jira:
    URL: ClassVar[str] = "https://test-jira.teltonika.lt"

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
    def add_worklog(cls, entry: Entry) -> Worklog | None:
        assert cls._server_ is not None

        if entry.task.jira is None:
            print(f"[WARNING] Entry '{entry}' has no Jira task")
            return None

        comment = entry.markup
        print(f"WARNING! Testing change: task {entry.task.jira} changed to 'DEV3-75'")
        worklog = cls._server_.add_worklog(
            # entry.task.jira,
            "DEV3-75",
            timeSpent=entry.duration,
            started=entry.start,
            comment=comment,
        )

        entry.worklog_id = worklog.id

        return worklog

    @classmethod
    def delete_worklog(cls, entry: Entry):
        assert cls._server_ is not None
        assert entry.logged() is True
        assert entry.task.jira is not None

        worklog = cls._server_.worklog(issue=entry.task.jira, id=entry.worklog_id)
        worklog.delete()

        entry.worklog_id = 0


if __name__ == '__main__':
    # pylint: disable=protected-access
    Jira.login(CONFIG.credentials.jira.token)
    print(Jira._server_)
    Jira.logout()
