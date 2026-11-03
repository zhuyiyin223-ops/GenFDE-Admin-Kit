"""系统能力：当前用户主题的读写与即时应用。

会话侧写入 ``app.storage.user``；浏览器侧写入 ``app.storage.browser``，
供登录页在未登录时沿用上次选择；账号绑定写入 ``app.storage.general``。
"""

from __future__ import annotations

import json

from nicegui import app, ui

from modules.theme.catalog import DEFAULT_THEME, THEMES, Theme, get_theme

STORAGE_USER_KEY = "theme_key"
STORAGE_GENERAL_KEY = "user_theme_keys"


class ThemeService:
    """主题偏好的读取、账号绑定与页面应用。"""

    @staticmethod
    def resolve(user_id: int | None = None) -> Theme:
        """解析当前应生效的主题：账号记录优先，其次会话 / 浏览器，最后默认。"""
        uid = user_id if isinstance(user_id, int) else _session_user_id()
        theme_key = None
        if isinstance(uid, int):
            theme_key = _account_theme_map().get(str(uid))
        if not theme_key:
            theme_key = _session_theme_key() or _browser_theme_key()
        return get_theme(theme_key)

    @staticmethod
    def save(theme_key: str, *, user_id: int | None = None) -> Theme:
        """保存主题到当前会话和浏览器，并在已登录时绑定到账号。"""
        theme = get_theme(theme_key)
        _write_session_theme_key(theme.key)
        _write_browser_theme_key(theme.key)
        uid = user_id if isinstance(user_id, int) else _session_user_id()
        if isinstance(uid, int):
            mapping = dict(_account_theme_map())
            mapping[str(uid)] = theme.key
            try:
                app.storage.general[STORAGE_GENERAL_KEY] = mapping
            except RuntimeError:
                pass
        return theme

    @staticmethod
    def bind_to_user(user_id: int) -> Theme:
        """登录后把主题绑定到账号。

        账号已有记录则用之；否则沿用登录页上的会话选择并写入账号。
        """
        account_key = _account_theme_map().get(str(int(user_id)))
        session_key = _session_theme_key() or _browser_theme_key()
        return ThemeService.save(
            account_key or session_key or DEFAULT_THEME.key,
            user_id=int(user_id),
        )

    @staticmethod
    def clear_session_keep_theme() -> None:
        """清空登录态，保留当前主题供登录页继续使用。"""
        theme_key = ThemeService.resolve().key
        try:
            app.storage.user.clear()
        except RuntimeError:
            return
        _write_session_theme_key(theme_key)
        _write_browser_theme_key(theme_key)

    @staticmethod
    def apply(theme: Theme, *, live: bool = False) -> None:
        """将主题色应用到当前页面。

        ``live=False`` 时写入 ``<head>``，供首屏使用；
        ``live=True`` 时同步改 ``:root`` / ``body`` 变量，立即生效。
        """
        ui.colors(**theme.as_colors())
        if live:
            ui.run_javascript(_live_update_script(theme))
            return
        ui.add_head_html(f"<style id='ng-theme-vars'>{_root_css(theme)}</style>")

    @staticmethod
    def apply_current(*, live: bool = False) -> Theme:
        """解析并应用当前用户主题，同时把结果镜像进会话存储。"""
        theme = ThemeService.resolve()
        _write_session_theme_key(theme.key)
        _write_browser_theme_key(theme.key)
        ThemeService.apply(theme, live=live)
        return theme


def _session_user_id() -> int | None:
    """读取当前会话中的账号 ID。"""
    try:
        user_id = app.storage.user.get("user_id")
    except RuntimeError:
        return None
    return user_id if isinstance(user_id, int) else None


def _session_theme_key() -> str | None:
    """读取当前会话中的主题编码。"""
    try:
        raw = app.storage.user.get(STORAGE_USER_KEY)
    except RuntimeError:
        return None
    key = str(raw or "").strip()
    return key or None


def _write_session_theme_key(theme_key: str) -> None:
    """把主题编码写入当前会话。"""
    try:
        app.storage.user[STORAGE_USER_KEY] = theme_key
    except RuntimeError:
        pass


def _browser_theme_key() -> str | None:
    """读取浏览器中保存的主题编码。"""
    try:
        raw = app.storage.browser.get(STORAGE_USER_KEY)
    except RuntimeError:
        return None
    key = str(raw or "").strip()
    return key if key in THEMES else None


def _write_browser_theme_key(theme_key: str) -> None:
    """把主题编码写入浏览器存储；页面事件中不可写时静默跳过。"""
    try:
        app.storage.browser[STORAGE_USER_KEY] = theme_key
    except (RuntimeError, TypeError, ValueError):
        pass


def _account_theme_map() -> dict[str, str]:
    """读取账号到主题编码的映射。"""
    try:
        raw = app.storage.general.get(STORAGE_GENERAL_KEY, {})
    except RuntimeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    mapping: dict[str, str] = {}
    for raw_user_id, raw_theme_key in raw.items():
        user_id = str(raw_user_id or "").strip()
        theme_key = str(raw_theme_key or "").strip()
        if user_id and theme_key in THEMES:
            mapping[user_id] = theme_key
    return mapping


def _hex_to_rgb_csv(color: str) -> str:
    """将 #RRGGBB 转为 CSS rgba() 可用的 'r, g, b'。"""
    hex_value = color.removeprefix("#")
    if len(hex_value) == 3:
        hex_value = "".join(ch * 2 for ch in hex_value)
    red = int(hex_value[0:2], 16)
    green = int(hex_value[2:4], 16)
    blue = int(hex_value[4:6], 16)
    return f"{red}, {green}, {blue}"


def _root_vars(theme: Theme) -> dict[str, str]:
    """主题对应的 CSS 自定义属性。"""
    return {
        "--q-primary": theme.primary,
        "--q-secondary": theme.secondary,
        "--ng-primary-rgb": _hex_to_rgb_csv(theme.primary),
        "--ng-secondary-rgb": _hex_to_rgb_csv(theme.secondary),
        "--ng-page-bg": theme.background,
        "--ng-surface": theme.background,
    }


def _root_css(theme: Theme) -> str:
    """生成写入 ``:root`` 的主题变量样式。"""
    declarations = " ".join(f"{name}: {value};" for name, value in _root_vars(theme).items())
    return f":root {{ {declarations} }}"


def _live_update_script(theme: Theme) -> str:
    """生成立即更新页面主题变量的脚本。"""
    payload = json.dumps(_root_vars(theme), ensure_ascii=True)
    css = json.dumps(_root_css(theme), ensure_ascii=True)
    return (
        "(() => {"
        f" const vars = {payload};"
        " const root = document.documentElement;"
        " const body = document.body;"
        " for (const [key, value] of Object.entries(vars)) {"
        "   root.style.setProperty(key, value);"
        "   if (body) body.style.setProperty(key, value);"
        " }"
        " const el = document.getElementById('ng-theme-vars');"
        f" if (el) el.textContent = {css};"
        "})();"
    )
