from __future__ import annotations

import sys
from traceback import print_exception

from command import Command
from config import CONFIG
from task import TaskDescriptor


class App:
    @classmethod
    def main(cls):
        TaskDescriptor.load_from_config(CONFIG.tasks)
        while True:
            command = input("> ")
            cls.process(command)

    @classmethod
    def process(cls, command: str):
        max_parsed = 0

        for cmd in Command.all.values():
            try:
                parsed = cmd.parse(command)
            # pylint: disable=broad-except
            except Exception as error:
                print_exception(error)
                return

            if parsed is None:
                return

            if parsed > max_parsed:
                max_parsed = parsed

        if max_parsed == 0:
            print(f"Invalid command: '{command}'")
        else:
            print(f"Invalid command syntax: {command}")
            print(f"Error at this position: {' '*max_parsed}^")


if __name__ == '__main__':
    if CONFIG.debug is False:
        sys.tracebacklimit = 0

    App.main()
