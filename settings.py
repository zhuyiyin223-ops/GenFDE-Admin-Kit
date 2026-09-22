"""项目配置。

职责边界：
- 本文件是非敏感运行配置的唯一来源，直接改各 Settings 实例的字段即可。
- `.env` 只存放密钥与凭据，不放产品标识、主题、监听地址等非敏感项。
- 已存在的进程环境变量优先于 `.env`，便于部署时注入密钥。

按领域拆成 frozen dataclass，避免多维度配置挤在一组扁平常量里。
框架需要的 dict（如 Tortoise、NiceGUI ui.run）在文件底部由这些对象派生。

本模块不承载 UI、持久化或业务逻辑。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tortoise.fields.data import DatetimeField as _DatetimeField
from tortoise.migrations.recorder import MigrationRecorder as _MigrationRecorder

# 仓库根目录。相对路径（如 .env）均基于此解析。
PROJECT_ROOT = Path(__file__).resolve().parent

# 允许 #RGB / #RRGGBB；读取后统一展开为小写 #RRGGBB。
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
# 每日时刻：H:MM 或 HH:MM，读取后统一为 HH:MM。
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def load_env_file(path: str = ".env") -> None:
    """将 .env 载入进程环境。

    已存在的环境变量优先生效，文件中的同名项不会覆盖。
    文件不存在时静默跳过，便于未配置本地密钥时使用代码内开发默认值。
    应用启动与部署脚本共用此函数，避免各入口各自解析 .env。
    """
    env_path = Path(path)
    if not env_path.is_absolute():
        env_path = PROJECT_ROOT / env_path
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _env_str(name: str, default: str = "") -> str:
    """读取敏感配置对应的环境变量；空白值回退到默认值。"""
    return os.getenv(name, default).strip() or default


def _hex_color(value: str) -> str:
    """校验并规范化十六进制颜色，统一为小写 #RRGGBB。"""
    normalized = value.strip()
    if normalized and not normalized.startswith("#"):
        normalized = f"#{normalized}"
    if _HEX_COLOR_RE.fullmatch(normalized) is None:
        raise RuntimeError(f"颜色必须是 #RGB 或 #RRGGBB，当前值为：{value}")
    if len(normalized) == 4:
        normalized = "#" + "".join(ch * 2 for ch in normalized[1:])
    return normalized.lower()


def _hhmm(value: str) -> str:
    """校验并规范化每日时刻，统一为 HH:MM。"""
    matched = _HHMM_RE.fullmatch(value.strip())
    if matched is None:
        raise RuntimeError(f"时刻必须是 HH:MM，当前值为：{value}")
    hour = int(matched.group(1))
    minute = int(matched.group(2))
    if hour > 23 or minute > 59:
        raise RuntimeError(f"时刻必须是 00:00–23:59，当前值为：{value}")
    return f"{hour:02d}:{minute:02d}"


load_env_file()


# ---------------------------------------------------------------------------
# 非敏感配置：改字段默认值即可
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class AppSettings:
    """应用本体与 NiceGUI 启动参数。"""

    env: str = "develop"
    version: str = "1.0.0"
    title: str = "GenFDE-Admin-Kit"
    favicon: str = "️🛠️"
    host: str = "127.0.0.1"
    port: int = 8899
    show: bool = False
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"

    @property
    def reload(self) -> bool:
        """develop 环境下默认开启热重载。"""
        return self.env == "develop"

    def ui_run_kwargs(self) -> dict[str, Any]:
        """NiceGUI ui.run 可识别的启动参数，不含密钥。"""
        return {
            "title": self.title,
            "favicon": self.favicon,
            "host": self.host,
            "port": self.port,
            "reload": self.reload,
            "show": self.show,
            "language": self.language,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class UiSettings:
    """默认界面配色（牛油果主题）。运行时由 ``modules.theme`` 按账号覆盖。"""

    primary: str = "#356859"
    secondary: str = "#5898d4"
    background: str = "#fffbe6"

    def __post_init__(self) -> None:
        object.__setattr__(self, "primary", _hex_color(self.primary))
        object.__setattr__(self, "secondary", _hex_color(self.secondary))
        object.__setattr__(self, "background", _hex_color(self.background))

    def as_colors(self) -> dict[str, str]:
        """供 app.colors / ui.colors 使用。"""
        return {"primary": self.primary, "secondary": self.secondary}


@dataclass(frozen=True, slots=True, kw_only=True)
class LogSettings:
    """loguru 输出配置。"""

    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "14 days"
    directory: Path = PROJECT_ROOT / "logs"

    @property
    def app_file(self) -> Path:
        """全量日志文件。"""
        return self.directory / "app.log"

    @property
    def error_file(self) -> Path:
        """ERROR 及以上日志文件。"""
        return self.directory / "error.log"

    @property
    def backup_file(self) -> Path:
        """数据库备份任务专用日志。"""
        return self.directory / "database_backup.log"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiAuthSettings:
    """对外 API JWT 鉴权参数，与页面登录态相互独立。"""

    issuer: str = "genfde-admin-kit"
    audience: str = "external-client"
    algorithm: str = "HS256"
    access_ttl_minutes: int = 30
    refresh_ttl_days: int = 7


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminSettings:
    """启动时自动创建的默认管理员（不含密码）。"""

    userid: str = "admin"
    name: str = "系统管理员"


@dataclass(frozen=True, slots=True, kw_only=True)
class CronSettings:
    """定时任务每日触发时刻，按 APP.timezone。"""

    database_backup_at: str = "02:00"
    user_log_archive_at: str = "03:00"

    def __post_init__(self) -> None:
        object.__setattr__(self, "database_backup_at", _hhmm(self.database_backup_at))
        object.__setattr__(self, "user_log_archive_at", _hhmm(self.user_log_archive_at))


APP = AppSettings()
UI = UiSettings()
LOG = LogSettings()
API_AUTH = ApiAuthSettings()
ADMIN = AdminSettings()
CRON = CronSettings()


# ---------------------------------------------------------------------------
# 敏感配置：只从环境 / .env 读取。以下默认值仅供本地开发。
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SecretSettings:
    """密钥与凭据。生产环境必须通过环境变量覆盖。"""

    database_url: str
    storage_secret: str
    jwt_secret: str
    admin_password: str

    @classmethod
    def from_env(cls) -> SecretSettings:
        """从环境读取密钥；JWT 未单独配置时复用 storage_secret。"""
        storage_secret = _env_str("STORAGE_SECRET", "change-me-in-production")
        return cls(
            database_url=_env_str(
                "DATABASE_URL",
                "postgres://postgres:postgres@127.0.0.1:5432/genfde_admin_kit",
            ),
            storage_secret=storage_secret,
            jwt_secret=_env_str("JWT_SECRET", storage_secret),
            admin_password=_env_str("DEFAULT_ADMIN_PASSWORD", "admin"),
        )


SECRETS = SecretSettings.from_env()

# ---------------------------------------------------------------------------
# 派生：给框架 / CLI 的装配产物，不要在这里改业务默认值
# ---------------------------------------------------------------------------

# tortoise CLI 通过 pyproject.toml 读取该对象，必须保持模块级 dict。
TORTOISE_ORM = {
    "connections": {"default": SECRETS.database_url},
    "apps": {
        "models": {
            "models": ["models"],
            "default_connection": "default",
            "migrations": "migrations.models",
        },
    },
    "use_tz": False,
    "timezone": APP.timezone,
}

# Postgres 时间列用 timestamp。Tortoise 迁移记录默认写 UTC aware，改为 naive。
_DatetimeField._db_postgres.SQL_TYPE = "TIMESTAMP"


async def _record_applied(self, app: str, name: str) -> None:
    query = (
        f"INSERT INTO {self._quote(self.table_name)} "
        f"({self._quote('app')}, {self._quote('name')}, {self._quote('applied_at')}) "
        f"VALUES ({self._placeholder(1)}, {self._placeholder(2)}, {self._placeholder(3)})"
    )
    await self.connection.execute_insert(query, [app, name, datetime.now()])


_MigrationRecorder.record_applied = _record_applied
