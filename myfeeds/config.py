import logging
import os
import typing
from typing import Any, Dict, Tuple

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Singleton(type):
    def __init__(
        cls, name: str, bases: Tuple[type], namespace: Dict[str, Any],
    ) -> None:
        cls.instance = None
        super().__init__(name, bases, namespace)

    def __call__(cls, *args, **kwargs) -> Any:
        if cls.instance is None:
            cls.instance = super().__call__(*args, **kwargs)
        return cls.instance


LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


class ConfigError(Exception):
    pass


class ConfigFileError(ConfigError):
    pass


class UpperDict:
    def __init__(self, data: dict):
        self.__dict: typing.Dict[str, typing.Any] = dict()

        for key in data.keys():
            self[key] = data[key]

    def __str__(self) -> str:
        indent = 4
        result = ["{"]

        def append(line):
            result.append(" " * indent + line)

        for key, value in self.__dict.items():
            if isinstance(value, UpperDict):
                append(f"{key}: {{")
                for line in str(value).splitlines()[1:-1]:
                    append(f"{line}")
                append("}")
            else:
                if isinstance(value, str):
                    append(f"{key}: '{value}',")
                else:
                    append(f"{key}: {value},")

        result.append("}")

        return "\n".join(result)

    def __setitem__(self, key: str, value: typing.Any) -> None:
        key = key.upper()

        if isinstance(value, dict):
            if key in self.__dict.keys():
                for k, v in value.items():
                    self.__dict[key][k.upper()] = v
            else:
                self.__dict[key] = UpperDict(value)
        else:
            self.__dict[key] = value

    def __getitem__(self, key: str) -> typing.Any:
        return self.__dict[key.upper()]

    def __getattr__(self, name: str) -> typing.Any:
        try:
            value = self.get(name, ...)
            if value is ...:
                raise KeyError()
            return value
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

    def get(self, key: str, default=None) -> typing.Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.__dict.keys()


def _import_environ() -> typing.Dict:
    result: typing.Dict[str, typing.Any] = {}

    if os.environ.get("MYFEEDS_DEBUG"):
        result["debug"] = os.environ.get("MYFEEDS_DEBUG") in ("on", "True")

    if os.environ.get("MYFEEDS_ENV"):
        result["env"] = os.environ.get("MYFEEDS_ENV")

    return result


class Config(UpperDict, metaclass=Singleton):
    def __init__(self) -> None:
        super().__init__({})
        self.setdefault()
        # read config from file
        self.import_from_file()
        # read config from environ
        self.update(_import_environ())

    @property
    def path(self) -> str:
        """return os.getcwd()"""
        return os.getcwd()

    def import_from_file(self) -> None:
        with open(os.path.join(BASE_DIR, "config.yml"), "rb") as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            raise ConfigError(f"config must be a dictionary.")
        self.update(data)

    def setdefault(self) -> None:
        self["env"] = "dev"
        self["debug"] = True
        self["verbose"] = True

    def update(self, data: dict) -> None:
        for key in data.keys():
            self[key] = data[key]

    def __setattr__(self, name: str, value: typing.Any) -> None:
        if name == f"_UpperDict__dict":
            return super().__setattr__(name, value)
        raise ConfigError("Modifying the attribute value of Config is not allowed.")

    def __delattr__(self, name: str) -> None:
        raise ConfigError("Modifying the attribute value of Config is not allowed.")

    def __delitem__(self, key: str) -> None:
        raise ConfigError("Modifying the attribute value of Config is not allowed.")

    def __setitem__(self, key: str, value: typing.Any) -> None:
        key = key.upper()
        if key == "DEBUG":
            value = bool(value)
        super().__setitem__(key, value)

    def get(self, key, default=None) -> typing.Any:
        env = super().get(self["env"], {})
        value = env.get(key, ...)
        if value is ...:
            value = super().get(key, default)
        return value


config = Config()
