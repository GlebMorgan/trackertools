from __future__ import annotations

import sys
from traceback import print_exception

from command import Command
from config import CONFIG
from tools import AppError


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
    if CONFIG.debug is False:
        sys.tracebacklimit = 0

    App.main()
