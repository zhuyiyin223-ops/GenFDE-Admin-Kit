"""系统能力用例：解析登录后首个可访问页面。"""

from __future__ import annotations

from .permission_context import accessible_menu_links, load_user_permission_context


async def get_first_accessible_path(user_id: int, preferred_path: str | None = None) -> str:
    """返回登录后首个可访问页面。"""
    context = await load_user_permission_context(int(user_id))
    links = accessible_menu_links(list(context.permission_codes))
    normalized_preferred_path = str(preferred_path or "").strip()
    if normalized_preferred_path in links:
        return normalized_preferred_path
    return links[0] if links else "/"
