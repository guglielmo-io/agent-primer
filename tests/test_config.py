import os
from pathlib import Path

from agent_primer.config import AppConfig, ConfigStore


def test_config_is_written_with_private_permissions(tmp_path: Path):
    store = ConfigStore(tmp_path / "config.json")

    store.save(AppConfig(openrouter_api_key="secret", last_model="model"))

    if os.name == "nt":
        assert (tmp_path / "config.json").exists()
        return

    mode = oct((tmp_path / "config.json").stat().st_mode & 0o777)
    assert mode == "0o600"


def test_env_key_overrides_config(tmp_path: Path, monkeypatch):
    store = ConfigStore(tmp_path / "config.json")
    store.save(AppConfig(openrouter_api_key="stored", last_model="model"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")

    assert store.get_api_key() == "env-key"


def test_config_round_trip_preserves_recent_paths(tmp_path: Path):
    store = ConfigStore(tmp_path / "config.json")
    expected = AppConfig(
        openrouter_api_key="secret",
        last_model="google/gemini-3.5-flash",
        recent_paths=["/repo"],
    )

    store.save(expected)

    assert store.load() == expected


def test_default_config_store_uses_agent_primer_config_path(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    store = ConfigStore()

    assert store.load() == AppConfig()
    assert store.path == home / ".config" / "agent-primer" / "config.json"
