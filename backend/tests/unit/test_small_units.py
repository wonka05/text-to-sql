from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.services.catalog import CatalogProvider
from app.services.executor import infer_type, to_json_value
from app.services.rate_limit import RateLimiter
from tests.conftest import make_catalog


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class TestRateLimiter:
    def test_limits_per_client_within_the_window(self):
        clock = FakeClock()
        limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
        assert limiter.check("a") is None
        assert limiter.check("a") is None
        assert limiter.check("a") == 60
        assert limiter.check("b") is None

        clock.now += 30
        assert limiter.check("a") == 30
        clock.now += 30
        assert limiter.check("a") is None

    def test_zero_disables_it(self):
        limiter = RateLimiter(limit=0)
        assert all(limiter.check("a") is None for _ in range(100))


@pytest.mark.parametrize("value, expected", [
    (Decimal("71000.00"), 71000),
    (Decimal("120114.29"), 120114.29),
    (date(2024, 1, 2), "2024-01-02"),
    (datetime(2024, 1, 2, 10, 30), "2024-01-02 10:30:00"),
    (timedelta(hours=10, minutes=5), "10:05:00"),
    (timedelta(hours=-1), "-01:00:00"),
    (b"\x00\x01", "<2 bytes>"),
    (None, None),
    ("text", "text"),
])
def test_values_become_json_friendly(value, expected):
    assert to_json_value(value) == expected


@pytest.mark.parametrize("values, expected", [
    ([1, Decimal("2.5"), None], "number"),
    (["a", None], "text"),
    ([date(2024, 1, 1)], "date"),
    ([datetime(2024, 1, 1)], "datetime"),
    ([None, None], "text"),
    ([1, "a"], "text"),
])
def test_column_types_are_inferred_from_values(values, expected):
    assert infer_type(values) == expected


class TestCatalogProvider:
    def test_caches_until_the_ttl_expires(self):
        clock, loads = FakeClock(), []

        def load():
            loads.append(1)
            return make_catalog()

        provider = CatalogProvider(load, ttl_seconds=60, clock=clock)
        provider.get()
        provider.get()
        assert len(loads) == 1
        clock.now += 61
        provider.get()
        assert len(loads) == 2

    def test_invalidate_forces_a_reload(self):
        loads = []
        provider = CatalogProvider(lambda: loads.append(1) or make_catalog(), ttl_seconds=3600)
        provider.get()
        provider.invalidate()
        provider.get()
        assert len(loads) == 2


def test_fingerprint_changes_with_the_schema():
    assert make_catalog().fingerprint == make_catalog().fingerprint
    assert make_catalog().fingerprint != make_catalog(frozenset({("employees", "email")})).fingerprint


class TestSettings:
    def base(self, **extra):
        return Settings(_env_file=None, gemini_api_key="k", db_name="d", db_user="u",
                        db_password="p", **extra)

    def test_restricted_columns_parse(self):
        settings = self.base(restricted_columns=" Employees.Salary, customers.phone ,")
        assert settings.restricted_column_set == {("employees", "salary"), ("customers", "phone")}

    def test_restricted_columns_must_name_a_table(self):
        with pytest.raises(ValueError):
            _ = self.base(restricted_columns="salary").restricted_column_set

    def test_no_ca_means_no_tls_arguments(self):
        from app.database.connection import ssl_connect_args

        assert ssl_connect_args(self.base()) == {}

    def test_ca_given_as_pem_text_is_written_to_a_file(self):
        from pathlib import Path

        from app.database.connection import ssl_connect_args

        pem = "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----"
        args = ssl_connect_args(self.base(db_ssl_ca=pem))
        assert Path(args["ssl_ca"]).read_text().strip() == pem
        assert args["ssl_verify_cert"] is True and args["ssl_verify_identity"] is True

    def test_ca_given_as_a_path_is_used_directly(self):
        from app.database.connection import ssl_connect_args

        args = ssl_connect_args(self.base(db_ssl_ca="/etc/ca.pem", db_ssl_verify_hostname=False))
        assert args == {"ssl_ca": "/etc/ca.pem", "ssl_verify_cert": True, "ssl_verify_identity": False}

    def test_cors_origins_split(self):
        assert self.base(allowed_origins="http://a, http://b").cors_origins == ["http://a", "http://b"]
