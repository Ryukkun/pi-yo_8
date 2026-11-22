import importlib.util
import logging
import os
from pathlib import Path

from pydantic import BaseModel

_log = logging.getLogger(__name__)


class GuildConfig(BaseModel):
    """ギルドごとの永続設定"""

    auto_join: bool = False
    empty_disconnect_delay: float = 5.0


class UserConfig(BaseModel):
    """ユーザーごとの永続設定"""

    default_speed: float = 1.0
    default_pitch: int = 0


class AppConfig(BaseModel):
    """アプリケーション全体の設定"""

    prefix: str = ":"
    token: str = ""
    guild_config: Path = Path("./guild_config/")
    user_config: Path = Path("./user_config/")


class ConfigFile[T: BaseModel]:
    """1つのJSON設定ファイルの読み込み・アトミック保存を管理する"""

    def __init__(self, path: Path, cls: type[T], default_factory: T | None = None) -> None:
        self.cls = cls
        self.path = path
        self._default_factory = default_factory
        self.data: T = self._read()

    def _create_default(self) -> T:
        if self._default_factory is not None:
            return self._default_factory.model_copy(deep=True)
        return self.cls()

    def _read(self) -> T:
        if not self.path.exists() or self.path.stat().st_size == 0:
            _log.info(f"Config file {self.path} not found or empty. Creating default.")
            default_data = self._create_default()
            self.write(default_data)
            return default_data

        try:
            content = self.path.read_text(encoding="utf-8")
            return self.cls.model_validate_json(content)
        except Exception as e:
            _log.warning(f"Warning: {self.path} is corrupted. Using default. Error: {e}")
            default_data = self._create_default()
            self.write(default_data)
            return default_data

    def write(self, data: T | None = None) -> None:
        """現在のデータ（または渡されたデータ）をアトミックにファイルへ保存"""
        target = data or self.data
        self.path.parent.mkdir(parents=True, exist_ok=True)
        json_str = target.model_dump_json(indent=2)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json_str, encoding="utf-8")
        os.replace(temp_path, self.path)


class ConfigStore[T: BaseModel]:
    """IDごとにJSON設定ファイルをキャッシュ・管理するストア"""

    def __init__(self, folder_path: Path, data_cls: type[T]) -> None:
        self.cache: dict[int, ConfigFile[T]] = {}
        self.folder_path = folder_path
        self.data_cls = data_cls

    def get(self, key: int = 0) -> ConfigFile[T]:
        if key not in self.cache:
            file_path = self.folder_path / f"{key}.json"
            self.cache[key] = ConfigFile(file_path, self.data_cls)
        return self.cache[key]


def _load_legacy_py_config(legacy_path: Path) -> AppConfig | None:
    """旧 pi_yo_8/config.py が存在する場合に Prefix / Token を読み取る"""
    if not legacy_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_legacy_pi_yo_8_config", legacy_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prefix = getattr(module, "Prefix", ":")
        token = getattr(module, "Token", "")
        _log.info(f"Migrated legacy config from {legacy_path}")
        return AppConfig(prefix=str(prefix), token=str(token))
    except Exception as e:
        _log.warning(f"Failed to migrate legacy config from {legacy_path}: {e}")
        return None


def load_app_config(
    config_path: Path = Path("./config.json"),
    legacy_path: Path = Path("./pi_yo_8/config.py"),
) -> ConfigFile[AppConfig]:
    """AppConfigを読み込む。config.json未作成時は旧config.pyからの移行を試みる。"""
    initial_default: AppConfig | None = None
    if not config_path.exists() or config_path.stat().st_size == 0:
        initial_default = _load_legacy_py_config(legacy_path)
    return ConfigFile(config_path, AppConfig, default_factory=initial_default)


_app_config_file = load_app_config()
app_config = _app_config_file.data
guild_configs = ConfigStore(app_config.guild_config, GuildConfig)
user_configs = ConfigStore(app_config.user_config, UserConfig)
