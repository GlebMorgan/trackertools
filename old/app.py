import sys
from traceback import print_exception

from command import Command
from config import CONFIG
from tools import AppError


WEEK = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


TOKENS = dict(
    node = [
        r'(?P<alias>[A-Za-z]{2})',
    ],
    span = [
        r'((?P<hours>\d+)h)?[- ]?((?P<minutes>\d+)m)?',
    ],
### span = [
###     r'(?P<hours>\d+)h[- ]?(?P<minutes>\d+)m',
###     r'(?P<hours>\d+)h',
###     r'(?P<minutes>\d+)m',
###     r'(?P<minutes>\d+)',
### ],
    time = [
        r'(?P<hours>\d{1,2}):(?P<minutes>\d{1,2})'
    ],
    date = [
        r'(?P<date>\d{4}-\d{2}-\d{2})',
        r'(?P<day>\d{1,2})',
        r'(?P<today>today)',
        r'(?P<yesterday>yesterday)',
        r'(?P<week>{days})'.format(days='|'.join(WEEK)),
        r'last[- ](?P<lastweek>{days})'.format(days='|'.join(WEEK)),
    ],
    week = [
        r'(?P<thisweek>week)',
        r'(?P<lastweek>last[- ]week)',
        r'week[- ](?P<week>\d)',
    ],
    get = [
        r'(?P<get>get)',
        r'(?P<load>load)',
        r'(?P<fetch>fetch)',
    ],
)


class App:
    @classmethod
    def main(cls):
        while True:
            command = input("> ")
            cls.process(command)

    @classmethod
    def process(cls, command: str):
        max_parsed = 0

        for cmd in Command.all.values():
            try:
                parsed = cmd.parse(command)
            except AppError as error:
                print_exception(error)
                return
            if parsed is None:
                return
            elif parsed > max_parsed:
                max_parsed = parsed

        if max_parsed == 0:
            print(f"Invalid command: '{command}'")
        else:
            print(f"Invalid command syntax: {command}")
            print(f"Error at this position: {' '*max_parsed}^")


if __name__ == '__main__':
    if CONFIG.debug == False:
        sys.tracebacklimit = 0

    returncode = App.main()
    sys.exit(returncode)
