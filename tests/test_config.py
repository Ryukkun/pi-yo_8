from pathlib import Path

from pi_yo_8.core.config import ConfigFile, ConfigStore, GuildConfig, load_app_config


def test_config_file_create_and_reload(tmp_path: Path) -> None:
    cfg_path = tmp_path / "guild.json"
    cf = ConfigFile(cfg_path, GuildConfig)
    assert cfg_path.exists()
    assert cf.data.auto_join is False
    assert cf.data.empty_disconnect_delay == 5.0

    cf.data.auto_join = True
    cf.data.empty_disconnect_delay = 10.0
    cf.write()

    reloaded = ConfigFile(cfg_path, GuildConfig)
    assert reloaded.data.auto_join is True
    assert reloaded.data.empty_disconnect_delay == 10.0


def test_config_file_corrupted_fallback(tmp_path: Path) -> None:
    cfg_path = tmp_path / "broken.json"
    cfg_path.write_text("{invalid json", encoding="utf-8")

    cf = ConfigFile(cfg_path, GuildConfig)
    assert cf.data.auto_join is False
    assert cf.data.empty_disconnect_delay == 5.0


def test_config_store_cache(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path, GuildConfig)
    c1 = store.get(12345)
    c2 = store.get(12345)
    assert c1 is c2
    assert (tmp_path / "12345.json").exists()


def test_load_app_config_migrates_legacy_py(tmp_path: Path) -> None:
    legacy = tmp_path / "config.py"
    legacy.write_text("Prefix = '!'\nToken = 'test-token-123'\n", encoding="utf-8")
    json_path = tmp_path / "config.json"

    cf = load_app_config(config_path=json_path, legacy_path=legacy)
    assert json_path.exists()
    assert cf.data.prefix == "!"
    assert cf.data.token == "test-token-123"
