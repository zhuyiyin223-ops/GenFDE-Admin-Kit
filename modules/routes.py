"""装配层：NiceGUI 页面路由注册。

登录等独立页通过 `@ui.page` 挂载；后台业务页先收入布局注册表，
再由公共壳统一挂载，使切页只刷新主内容区。
新增业务域时在 ``PAGE_MODULE_NAMES`` 追加对应 ``page`` 模块。
"""

from __future__ import annotations

from importlib import import_module

from modules.layout.shell import register_admin_shell
from modules.layout.side_chrome import register_side_chrome
from modules.message.page_component import MessageSideChrome

PAGE_MODULE_NAMES = (
    "modules.login.page",
    "modules.sys_user.page",
    "modules.sys_role.page",
    "modules.sys_log.page",
    "modules.sys_api.page",
    "modules.example.page",
)


def register_page_routes() -> None:
    """导入全部页面模块，注入壳扩展点，并挂载后台公共壳。"""
    for module_name in PAGE_MODULE_NAMES:
        import_module(module_name)
    register_side_chrome(MessageSideChrome())
    register_admin_shell()
