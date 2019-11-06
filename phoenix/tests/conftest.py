import os

from django.conf import settings
from django.db import connections
from environ import Env
import pytest
import testing.postgresql


@pytest.fixture(scope="session")
def db_url():
    db_uri_var = "TEST_DATABASE_URL"

    if os.getenv(db_uri_var):
        os.environ[db_uri_var] = os.path.expandvars(os.environ[db_uri_var])

    try:
        yield os.environ["TEST_DATABASE_URL"]

    except KeyError:
        with testing.postgresql.Postgresql() as db:
            yield db.url()


@pytest.fixture(scope="session")
def django_db_modify_db_settings(db_url):  # pylint: disable=redefined-outer-name

    settings.DATABASES["default"] = Env.db_url_config(db_url)
    del connections["default"]  # have Django recreate the connection later


@pytest.fixture(scope="session", autouse=True)
def django_modify_slack_settings():
    """Change slack settings to non-usable.

    Just to make sure unittests don't make requests to
    slack API.
    """
    settings.SLACK_TOKEN = "unittest"
    settings.SLACK_BOT_ID = "unittest-bot-id"
    settings.SLACK_BOT_TOKEN = "unittest"
    settings.SLACK_ANNOUNCE_CHANNEL_ID = "unittest"
    settings.SLACK_VERIFICATION_TOKEN = "unittest-token"
    settings.DATADOG_API_KEY = "unittest"
    settings.DATADOG_APP_KEY = "unittest"


@pytest.fixture(scope="session", autouse=True)
def django_modify_redis_settings():
    redis_uri_var = "REDIS_URL"

    if os.getenv(redis_uri_var):
        settings.REDIS_URL = os.path.expandvars(os.environ[redis_uri_var])
        settings.CELERY_BROKER_URL = settings.REDIS_URL
