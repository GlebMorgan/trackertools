from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import constricted_repr


class ConfigDict(dict[str, Any]):
    # ToDo: Recursive `ConfigDict`s
    __slots__ = ()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        if isinstance(value, ConfigLoader):
            contents = value.load()
            self[key] = contents
            return contents
        else:
            return value

    def __getattr__(self, name: str) -> Any:
        return self.__getitem__(name)

    def __setattr__(self, name: str, value: Any):
        raise AttributeError(f"'{self.__class__.__name__}' object is read-only")

    def __str__(self) -> str:
        attrs = (f"{key}: {value}" for key, value in self.items())
        return f"{{{', '.join(attrs)}}}"

    def __repr__(self) -> str:
        attrs = (f"{key}={value!r}" for key, value in self.items())
        return f"<{self.__class__.__qualname__} {' '.join(attrs)}>"


class ConfigLoader:
    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__}>"

    def load(self) -> Any:
        raise NotImplementedError


class DictLoader(ConfigLoader):
    config: dict[str, Any]

    def __init__(self, config_dict: dict[str, Any]):
        self.config = config_dict

    def __str__(self) -> str:
        serialized_dict = constricted_repr(self.config, 40)
        return f"{self.__class__.__name__}({serialized_dict})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} config={self.config!r}>"

    def load(self) -> ConfigDict:
        return ConfigDict(self.config)


class FileLoader(ConfigLoader):
    filepath: Path

    def __init__(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File '{path}' not found")
        self.filepath = path

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(\"{self.filepath.name}\")"

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} file=\"{self.filepath.as_posix()}\">"

    def load(self) -> Any:
        raise NotImplementedError


class StringLoader(FileLoader):
    def load(self) -> str:
        with self.filepath.open(encoding='utf-8') as file:
            value = file.read()
        return value.strip()


class KeyValueLoader(FileLoader):
    @staticmethod
    def _validate_key_(key: str):
        if not key.isidentifier():
            raise ValueError(f"Invalid key: {key}")

    def load(self) -> ConfigDict:
        config = ConfigDict()
        with self.filepath.open(encoding='utf-8') as file:
            for line in file:
                key, value = line.split(' = ', 1)
                key = key.strip()
                self._validate_key_(key)
                config[key] = value.strip()
        return config


class JsonLoader(FileLoader):
    def load(self) -> ConfigDict:
        with self.filepath.open(encoding='utf-8') as file:
            data = json.load(file)
        return ConfigDict(data)


class TestLoader(ConfigLoader):
    def __init__(self, string: str):
        self.string = string

    def load(self) -> str:
        return self.string


if __name__ == '__main__':
    conf = ConfigDict(
        num=42,
        str='string',
        loaded=TestLoader("loaded-string"),
        ref=StringLoader("test-data/test.txt"),
        keyval=KeyValueLoader("test-data/key-value.txt"),
        dict=DictLoader({'number': 42, 'array': [1, 2, 3], 'stuff': ...}),
        projects=JsonLoader("config/projects.json"),
    )
