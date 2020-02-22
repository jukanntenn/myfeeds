import logging
import logging.config
from pathlib import Path

from myfeeds.config import BASE_DIR, LOG_LEVELS, config

DEFAULT_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "myfeeds.log.RequireDebugFalse"},
        "require_debug_true": {"()": "myfeeds.log.RequireDebugTrue"},
    },
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "default": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": logging.DEBUG if config.debug else LOG_LEVELS[config.log_level],
            "class": "logging.StreamHandler",
            "formatter": "default" if config.debug else "simple",
        },
        "file": {
            "level": logging.DEBUG,
            "filters": ["require_debug_false"],
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(Path(BASE_DIR).joinpath(".logs", "myfeeds.log")),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 60,
            "encoding": "utf-8",
        },
    },
    "loggers": {"feeder": {"handlers": ["console", "file"], "level": logging.DEBUG}},
}


def config_logging():
    Path(BASE_DIR).joinpath(".logs").mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(DEFAULT_LOGGING)


class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not config.debug


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return config.debug
