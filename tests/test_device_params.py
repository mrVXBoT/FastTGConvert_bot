"""Tests for device_params service."""
import sqlite3
import tempfile
from pathlib import Path

from app.services.device_params import (
    get_device_params_store,
    get_random_device_params,
    get_stable_device_params,
)


def test_get_device_params_store():
    store = get_device_params_store()
    assert isinstance(store, dict)
    assert "device_model" in store or len(store) == 0


def test_get_random_device_params():
    params = get_random_device_params()
    assert isinstance(params, dict)
    required_keys = {"device_model", "system_version", "app_version", "lang_code", "system_lang_code"}
    assert required_keys.issubset(params.keys())
    for key in required_keys:
        assert isinstance(params[key], str)
        assert len(params[key]) > 0


def test_get_stable_device_params_determinism():
    res1 = get_stable_device_params("test_seed_alpha")
    res2 = get_stable_device_params("test_seed_alpha")
    assert res1 == res2


def test_get_stable_device_params_distinctness():
    res1 = get_stable_device_params("seed_foo_123")
    res2 = get_stable_device_params("seed_bar_456")
    # At least some of the parameter values should differ for distinct seeds
    assert res1 != res2


def test_get_stable_device_params_key_coverage():
    params = get_stable_device_params("any_seed_value")
    required_keys = {"device_model", "system_version", "app_version", "lang_code", "system_lang_code"}
    assert required_keys.issubset(params.keys())
    for key in required_keys:
        assert isinstance(params[key], str)
        assert len(params[key]) > 0


def test_get_stable_device_params_content_based_auth_key():
    fake_auth_key = b"\x01" * 256
    with tempfile.TemporaryDirectory(prefix="ftgc_test_seed1_") as tmp1, tempfile.TemporaryDirectory(prefix="ftgc_test_seed2_") as tmp2:
        path1 = Path(tmp1) / "session_0_acc.session"
        path2 = Path(tmp2) / "session_99_acc.session"

        for p in (path1, path2):
            with sqlite3.connect(p) as conn:
                conn.execute("CREATE TABLE sessions (dc_id INTEGER PRIMARY KEY, auth_key BLOB)")
                conn.execute("INSERT INTO sessions (dc_id, auth_key) VALUES (2, ?)", (fake_auth_key,))

        params1 = get_stable_device_params(path1)
        params2 = get_stable_device_params(path2)
        assert params1 == params2

        # Also test passing stem without .session extension (e.g. session_str used in Telethon)
        stem_path = path1.with_suffix("")
        params_stem = get_stable_device_params(stem_path)
        assert params_stem == params1


