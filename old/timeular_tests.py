from datetime import date, datetime
from urllib import response
import requests
import json
import re


noop = lambda *args, **kwargs: None


# parse timestamp: datetime.datetime.fromisoformat
# round time: ((<time>-1)/5 + 1)×5
# start time of combined Jira time log entry = start time of largest timeular time entry

other_activities = dict(
    jiraid = 'DEV-XX',
    activities = ['General', 'Relocation', 'Meeting', 'MR'],
)

class Timeular:
    api = "https://api.timeular.com/api/v3"

    def __init__(self, debug=False):
        self.debug = print if debug else noop
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def _get_(self, path, **kwargs):
        response = self.session.request("GET", f"{self.api}/{path}", params=kwargs)
        if not response:
            print(f"GET /{path} - status {response.status_code} - {response.text}")
            return None
        self.debug(f"GET /{path} - OK {response.status_code}")
        return response.json()

    def _post_(self, path, request=None):
        payload = json.dumps(request)
        response = self.session.request("POST", f"{self.api}/{path}", data=payload)
        if not response:
            print(f"POST /{path} - status {response.status_code} - {response.text}")
            return None
        self.debug(f"POST /{path} - OK {response.status_code}")
        return response.json() if request else response

    @staticmethod
    def _get_day_range_iso_(date: date) -> str:
        start = f"{date.isoformat()}T00:00:00.000"
        end = f"{date.isoformat()}T23:59:59.999"
        return f"{start}/{end}"

    def login(self, key: str, secret: str):
        api_keys = {'apiKey': key, 'apiSecret': secret}
        response = self._post_('developer/sign-in', api_keys)
        self.debug(f"Response = {response}")
        self.session.headers.update({"Authorization": f"Bearer {response['token']}"})

    def logout(self):
        response = self._post_('developer/logout')
        self.debug(f"Response = {response}")
        self.session.close()

    def get_activities(self):
        response = self._get_('activities')
        return response['activities']

    def get_entries_for(self, date: date):
        response = self._get_(f'time-entries/{self._get_day_range_iso_(date)}')
        return response['timeEntries']

    def get_tags(self):
        response = self._get_('tags-and-mentions')
        return response

    def get_spaces(self):
        response = self._get_('space')
        return response


class Entry:
    __slots__ = ('jiraid', 'activity_id', 'start', 'end', 'note')

    JiraID_REGEX = re.compile(r"\[(\d+)\].*")
    JIRA_PROJECT = "FM64"

    activities = {}

    def __init__(self):
        NotImplemented

    def __str__(self):
        start_time = f"{self.start.hour:02}:{self.start.minute:02}"
        end_time = f"{self.end.hour:02}:{self.end.minute:02}"
        jira = f"{self.JIRA_PROJECT}-{self.jiraid}" if self.jiraid else "OTHER"
        return f"[{jira}] {activities[self.activity_id]}: {self.note} ({start_time}-{end_time})"

    @staticmethod
    def _trim_time_(ts: datetime) -> datetime:
        return ts.replace(minute=(ts.minute//5)*5, second=0, microsecond=0)

    @classmethod
    def from_dict(cls, item):
        entry = cls()
        entry.activity_id = int(item['activityId'])
        entry.jiraid = entry.get_jiraid()
        entry.start = cls._trim_time_(datetime.fromisoformat(item['duration']['startedAt']))
        entry.end = cls._trim_time_(datetime.fromisoformat(item['duration']['stoppedAt']))
        entry.note = item['note']['text'] or ''
        return entry

    def get_jiraid(self):
        activity = activities[self.activity_id]
        if activity in other_activities['activities']:
            return None
        match = self.JiraID_REGEX.match(activity)
        if not match:
            self.jiraid = '????'
            print(f"JiraID not found in activity '{activity}'")
        else:
            return int(match[1])

if __name__ == '__main__':
    api_key = "MTEwMTI3XzJiMzRiMzM4MDRmNzRiOTk5ODdiNWZmNjEzOTJiY2Q1"
    api_secret = "MDhjZDNkNTY5NjI2NGQyOTg5ZTY1YjcwMDEwNzdhMzk="

    app = Timeular(debug=True)
    app.login(api_key, api_secret)
    # activities = {int(item['id']):item['name'] for item in app.get_activities()}
    # Entry.activities = activities
    # entries = {Entry.from_dict(item) for item in app.get_entries_for(date(2022, 5, 27))}
    # print(*entries, sep='\n')
    # spaces = app.get_spaces()
    # print(spaces)
    tags = app.get_tags()
    print(tags)
    app.logout()
