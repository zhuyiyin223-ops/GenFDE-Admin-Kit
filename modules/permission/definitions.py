"""权限与菜单定义。

本模块只声明模板框架的页面/功能权限和菜单结构，不负责数据库存储和页面渲染。
新增业务域时在此追加权限项和菜单项，步骤见 AGENTS.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any


@dataclass(frozen=True)
class PermissionCategory:
    """权限分类。"""

    key: str
    title: str
    icon: str


@dataclass(frozen=True)
class MenuItem:
    """菜单项。"""

    label: str
    icon: str
    link: str
    permission: str | None = None
    children: tuple[MenuItem, ...] = ()
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "label": self.label,
            "icon": self.icon,
            "link": self.link,
        }
        if self.permission:
            result["permission"] = self.permission
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        if self.disabled:
            result["disabled"] = True
        return result


class PermissionCategories:
    """权限分类常量。"""

    SYSTEM = PermissionCategory("system", "系统设置", "settings")
    EXAMPLE = PermissionCategory("example", "示例", "science")
    ORDER = (SYSTEM, EXAMPLE)


class PermissionType(IntEnum):
    """权限类型。"""

    MENU = 1
    FUNCTION = 2


# 已废弃的细分权限，读取时归一到对应模块的编辑权限。
_LEGACY_PERMISSION_ALIASES = {
    "sys_user:add": "sys_user:edit",
    "sys_user:delete": "sys_user:edit",
    "sys_user:reset_password": "sys_user:edit",
    "sys_role:add": "sys_role:edit",
    "sys_role:delete": "sys_role:edit",
    "sys_api:add": "sys_api:edit",
}


class PermissionItem(Enum):
    """权限项枚举。写操作统一使用编辑权限；导出权限独立于查看和编辑。"""

    SYS_USER_QUERY = ("sys_user:query", "用户账号查看", PermissionType.MENU, PermissionCategories.SYSTEM)
    SYS_USER_EDIT = ("sys_user:edit", "用户账号编辑", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    SYS_USER_EXPORT = ("sys_user:export", "用户账号导出", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    SYS_ROLE_QUERY = ("sys_role:query", "角色权限查看", PermissionType.MENU, PermissionCategories.SYSTEM)
    SYS_ROLE_EDIT = ("sys_role:edit", "角色权限编辑", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    SYS_ROLE_EXPORT = ("sys_role:export", "角色权限导出", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    SYS_LOG_QUERY = ("sys_log:query", "系统日志查看", PermissionType.MENU, PermissionCategories.SYSTEM)
    SYS_LOG_EXPORT = ("sys_log:export", "系统日志导出", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    SYS_API_QUERY = ("sys_api:query", "接口服务查看", PermissionType.MENU, PermissionCategories.SYSTEM)
    SYS_API_EDIT = ("sys_api:edit", "接口服务编辑", PermissionType.FUNCTION, PermissionCategories.SYSTEM)
    EXAMPLE_QUERY = ("example:query", "示例事项查看", PermissionType.MENU, PermissionCategories.EXAMPLE)
    EXAMPLE_EDIT = ("example:edit", "示例事项编辑", PermissionType.FUNCTION, PermissionCategories.EXAMPLE)

    def __init__(
        self,
        code: str,
        title: str,
        permission_type: PermissionType,
        category: PermissionCategory,
    ) -> None:
        self.code = code
        self.title = title
        self.permission_type = permission_type
        self.category = category

    @classmethod
    def all_codes(cls) -> list[str]:
        """返回全部权限编码。"""
        return [item.code for item in cls]

    @classmethod
    def normalize_codes(cls, codes: list[str] | tuple[str, ...] | None) -> list[str]:
        """将权限编码归一化为当前有效编码，兼容已废弃的细分权限。"""
        valid_codes = set(cls.all_codes())
        result: list[str] = []
        for code in codes or []:
            code_text = str(code or "").strip()
            code_text = _LEGACY_PERMISSION_ALIASES.get(code_text, code_text)
            if code_text in valid_codes and code_text not in result:
                result.append(code_text)
        return result

    @classmethod
    def get_name_map(cls) -> dict[str, str]:
        """返回权限编码到名称的映射。"""
        return {item.code: item.title for item in cls}

    @classmethod
    def get_grouped_options(cls) -> dict[str, list[dict[str, str]]]:
        """返回按分类分组的权限选项，供角色页展示。"""
        grouped: dict[str, list[dict[str, str]]] = {}
        for item in cls:
            grouped.setdefault(item.category.title, []).append(
                {"code": item.code, "title": item.title}
            )
        return grouped

    @classmethod
    def get_menu_structure(cls) -> list[dict[str, Any]]:
        """返回布局菜单结构。"""
        return [
            {
                "title": PermissionCategories.SYSTEM.title,
                "icon": PermissionCategories.SYSTEM.icon,
                "items": [
                    MenuItem(
                        label="用户账号",
                        icon="person",
                        link="/sys/user",
                        permission=cls.SYS_USER_QUERY.code,
                    ).to_dict(),
                    MenuItem(
                        label="角色权限",
                        icon="manage_accounts",
                        link="/sys/role",
                        permission=cls.SYS_ROLE_QUERY.code,
                    ).to_dict(),
                    MenuItem(
                        label="系统日志",
                        icon="description",
                        link="/sys/log",
                        permission=cls.SYS_LOG_QUERY.code,
                    ).to_dict(),
                    MenuItem(
                        label="接口服务",
                        icon="api",
                        link="/sys/api",
                        permission=cls.SYS_API_QUERY.code,
                    ).to_dict(),
                ],
            },
            {
                "title": PermissionCategories.EXAMPLE.title,
                "icon": PermissionCategories.EXAMPLE.icon,
                "items": [
                    MenuItem(
                        label="示例事项",
                        icon="task_alt",
                        link="/example/item",
                        permission=cls.EXAMPLE_QUERY.code,
                    ).to_dict(),
                ],
            },
        ]
