"""布局装配入口。

业务模块通过 ``create_layout`` 注册主内容页；后台壳由 ``register_admin_shell`` 统一挂载。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ContentPage:
    """后台壳中的主内容页注册项。"""

    path: str
    builder: Callable
    expand_left_drawer: bool = True


_CONTENT_PAGES: dict[str, ContentPage] = {}


def create_layout(
    func: Callable,
    path: str | None = None,
    default_expand_left_drawer: bool = True,
) -> Callable:
    """注册后台主内容页，不创建独立的整页路由。"""
    page_path = _resolve_page_path(func, path)
    _CONTENT_PAGES[page_path] = ContentPage(
        path=page_path,
        builder=func,
        expand_left_drawer=default_expand_left_drawer,
    )
    return func


def get_content_pages() -> dict[str, ContentPage]:
    """返回已注册的后台主内容页。"""
    return dict(_CONTENT_PAGES)


def get_content_routes() -> dict[str, Callable]:
    """返回路径到内容构建函数的映射，供 ``ui.sub_pages`` 使用。"""
    return {path: page.builder for path, page in _CONTENT_PAGES.items()}


def _resolve_page_path(func: Callable, path: str | None) -> str:
    """解析页面路径。"""
    if path is not None:
        return path
    if func.__name__ == "home_page":
        return "/"
    return "/" + func.__name__.removesuffix("_page")
