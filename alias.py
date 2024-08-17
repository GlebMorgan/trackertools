import random
import string
import sys
from typing import ClassVar, Self


class Alias(str):
    LEN: ClassVar[int] = 2

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} {super().__repr__()}>"

    @staticmethod
    def _gen_letter_(seed: int) -> str:
        index = seed % len(string.ascii_uppercase)
        return string.ascii_uppercase[index]

    @staticmethod
    def _partition_seed_(seed: int, size: int, base: int) -> list[int]:
        return [(seed // base**x) % base for x in range(size)]

    @classmethod
    def gen(cls, seed: int) -> Self:
        letters = cls._partition_seed_(seed, cls.LEN, len(string.ascii_uppercase))
        alias = str().join(string.ascii_uppercase[num] for num in letters)
        return cls(alias)

    def __init__(self, alias: str) -> None:
        if len(alias) != self.LEN:
            raise ValueError(f"Alias must be {self.LEN} characters long")


class RandomAlias(Alias):
    @classmethod
    def gen(cls, seed: int) -> Self:
        alias = str().join(random.choice(string.ascii_uppercase) for _ in range(cls.LEN))
        return cls(alias)


if __name__ == '__main__':
    match sys.argv[1:]:
        case ['gen']:
            test_alias = Alias.gen(42)
            print(test_alias)

        case ['new']:
            new_alias = Alias("XX")
            print(new_alias)

        case ['format']:
            test_alias = Alias("AB")
            print(f"repr={test_alias!r}, str={test_alias}")

        case ['contains']:
            test_alias = Alias("AB")
            print(f"in={test_alias in ['AB', 'CD']}, out={test_alias in []}")

        case [value]:
            test_alias = Alias.gen(int(value))
            print(test_alias)

        case _:
            pass
