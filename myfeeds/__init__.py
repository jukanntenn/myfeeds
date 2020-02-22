from myfeeds.log import config_logging
from jinja2 import Environment, PackageLoader
import sentry_sdk
from myfeeds.config import config

config_logging()

# sentry
if not config.debug and config.sentry_dsn:
    sentry_sdk.init(config.sentry_dsn)

# jinja2 Environment
env = Environment(loader=PackageLoader("myfeeds", "templates"),)
