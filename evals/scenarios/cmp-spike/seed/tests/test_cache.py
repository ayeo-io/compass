from src.cache import Cache


def test_set_then_get_returns_the_stored_value():
    cache = Cache()
    cache.set("total", 42)
    assert cache.get("total") == 42


def test_get_returns_the_default_for_a_missing_key():
    cache = Cache()
    assert cache.get("missing", "fallback") == "fallback"


def test_drop_removes_a_key():
    cache = Cache()
    cache.set("total", 42)
    cache.drop("total")
    assert cache.get("total") is None
