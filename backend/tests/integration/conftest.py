"""Fixtures for tests against a real MySQL server.

Set QG_TEST_MYSQL_ADMIN_URL to an account that may create databases and
users, for example:

    QG_TEST_MYSQL_ADMIN_URL=mysql+pymysql://root:password@127.0.0.1:3306

The fixture (re)creates the database QG_TEST_MYSQL_DATABASE (default
querygenie_test), fills it with the deterministic sample data, and creates a
read-only user for it. It refuses to touch a database whose name does not end
in "_test". Without the variable, these tests are skipped.
"""
import os
import secrets

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.database.connection import create_query_engine

ADMIN_URL = os.environ.get("QG_TEST_MYSQL_ADMIN_URL")
TEST_DATABASE = os.environ.get("QG_TEST_MYSQL_DATABASE", "querygenie_test")
# Separate from any account set up by hand, whose password the fixture would reset
TEST_USER = "querygenie_pytest_ro"


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in str(item.path):
            item.add_marker(pytest.mark.mysql)
            if not ADMIN_URL:
                item.add_marker(pytest.mark.skip(reason="QG_TEST_MYSQL_ADMIN_URL is not set"))


@pytest.fixture(scope="session")
def admin_url():
    if not TEST_DATABASE.endswith("_test"):
        pytest.exit(f"Refusing to use database {TEST_DATABASE!r}: its name must end in _test")
    return make_url(ADMIN_URL)


@pytest.fixture(scope="session")
def mysql_settings(admin_url):
    # Imported here so the unit tests don't need Faker installed
    from scripts.setup_db import create_read_only_user, create_tables_and_data

    server = create_engine(admin_url.set(database=None))
    with server.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{TEST_DATABASE}`"))
    server.dispose()

    admin = create_engine(admin_url.set(database=TEST_DATABASE))
    create_tables_and_data(admin, reset=True)
    password = secrets.token_urlsafe(18)
    create_read_only_user(admin, TEST_DATABASE, TEST_USER, password)
    admin.dispose()

    return Settings(
        _env_file=None,
        gemini_api_key="not-used",
        db_host=admin_url.host,
        db_port=admin_url.port or 3306,
        db_name=TEST_DATABASE,
        db_user=TEST_USER,
        db_password=password,
        max_result_rows=50,
        query_timeout_seconds=1,
    )


@pytest.fixture(scope="session")
def engine(mysql_settings):
    engine = create_query_engine(mysql_settings)
    yield engine
    engine.dispose()
