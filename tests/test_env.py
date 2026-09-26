import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import allowed_hosts, env_bool, env_list, env_str


def test_env_str_missing_without_default_fails(monkeypatch):
    monkeypatch.delenv("MYMVZ_TEST", raising=False)
    with pytest.raises(ImproperlyConfigured, match="MYMVZ_TEST"):
        env_str("MYMVZ_TEST")


def test_env_str_default_and_value(monkeypatch):
    monkeypatch.delenv("MYMVZ_TEST", raising=False)
    assert env_str("MYMVZ_TEST", "fallback") == "fallback"
    monkeypatch.setenv("MYMVZ_TEST", "set")
    assert env_str("MYMVZ_TEST", "fallback") == "set"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("True", True),
        (" yes ", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("No", False),
        ("", False),
    ],
)
def test_env_bool_values(monkeypatch, raw, expected):
    monkeypatch.setenv("MYMVZ_TEST", raw)
    assert env_bool("MYMVZ_TEST", default=not expected) is expected


def test_env_bool_missing_uses_default(monkeypatch):
    monkeypatch.delenv("MYMVZ_TEST", raising=False)
    assert env_bool("MYMVZ_TEST") is False
    assert env_bool("MYMVZ_TEST", default=True) is True


def test_env_bool_typo_fails(monkeypatch):
    monkeypatch.setenv("MYMVZ_TEST", "ture")
    with pytest.raises(ImproperlyConfigured, match="ture"):
        env_bool("MYMVZ_TEST")


def test_env_list_drops_blanks(monkeypatch):
    monkeypatch.setenv("MYMVZ_TEST", " a.example , ,b.example,")
    assert env_list("MYMVZ_TEST") == ["a.example", "b.example"]
    monkeypatch.delenv("MYMVZ_TEST")
    assert env_list("MYMVZ_TEST") == []


def test_allowed_hosts_local_only_in_debug():
    assert allowed_hosts("mymvz.jnsw.de", [], debug=False) == ["mymvz.jnsw.de"]
    hosts = allowed_hosts("mymvz.jnsw.de", ["www.mymvz.de"], debug=True)
    assert hosts[:2] == ["mymvz.jnsw.de", "www.mymvz.de"]
    assert "localhost" in hosts


def test_allowed_hosts_without_duplicates():
    assert allowed_hosts("localhost", ["localhost"], debug=True).count("localhost") == 1


def test_env_str_empty_counts_as_missing(monkeypatch):
    monkeypatch.setenv("MYMVZ_TEST", "")
    assert env_str("MYMVZ_TEST", "fallback") == "fallback"
    with pytest.raises(ImproperlyConfigured, match="MYMVZ_TEST"):
        env_str("MYMVZ_TEST")
