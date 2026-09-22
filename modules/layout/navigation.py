"""布局导航组件。"""

from __future__ import annotations

from dataclasses import dataclass, field

from nicegui import ui

from modules.permission.definitions import PermissionItem

DRAWER_WIDTH = 210


@dataclass(frozen=True)
class LayoutMenuCategory:
    """布局一级菜单数据。"""

    title: str
    icon: str
    items: list[dict]
    default_link: str


@dataclass
class LeftDrawerNav:
    """左侧菜单状态，同分类切页只改高亮，跨分类才重建菜单项。"""

    drawer: ui.left_drawer
    container: ui.column
    item_refs: dict[str, tuple[ui.item, ui.label]] = field(default_factory=dict)
    active_category: LayoutMenuCategory | None = None
    current_path: str = ""

    def sync(self, page_path: str, active_category: LayoutMenuCategory | None) -> None:
        """按当前路径同步左侧菜单。"""
        if _is_same_category(self.active_category, active_category):
            self._highlight(page_path)
            return
        self._rebuild(page_path, active_category)

    def _rebuild(self, page_path: str, active_category: LayoutMenuCategory | None) -> None:
        """重建左侧菜单内容。"""
        self.container.clear()
        self.item_refs = {}
        self.active_category = active_category
        self.current_path = page_path
        if active_category is None:
            self.drawer.classes(add="ng-left-drawer-empty")
            with self.container:
                _render_empty_placeholder()
            return
        self.drawer.classes(remove="ng-left-drawer-empty")
        with self.container:
            for item in active_category.items:
                _render_nav_item(item=item, page_path=page_path, item_refs=self.item_refs)

    def _highlight(self, page_path: str) -> None:
        """更新当前分类内的选中项。"""
        if page_path == self.current_path:
            return
        previous_path = self.current_path
        self.current_path = page_path
        if previous_path in self.item_refs:
            item, label = self.item_refs[previous_path]
            _set_nav_item_active(item, label, False)
        if page_path in self.item_refs:
            item, label = self.item_refs[page_path]
            _set_nav_item_active(item, label, True)


def build_navigation_context(
    page_path: str,
    user_permissions: list[str],
) -> tuple[list[LayoutMenuCategory], LayoutMenuCategory | None, LayoutMenuCategory | None]:
    """按权限构建顶部菜单和左侧菜单上下文。"""
    permission_set = set(user_permissions)
    categories: list[LayoutMenuCategory] = []
    active_category: LayoutMenuCategory | None = None

    for category in PermissionItem.get_menu_structure():
        raw_items = category.get("items", [])
        if not isinstance(raw_items, list):
            continue
        items = _filter_menu_items(raw_items, permission_set)
        if not items:
            continue
        default_link = _find_first_link(items[0])
        if not default_link:
            continue
        layout_category = LayoutMenuCategory(
            title=str(category["title"]),
            icon=str(category["icon"]),
            items=items,
            default_link=default_link,
        )
        categories.append(layout_category)
        if any(_menu_item_contains_path(item, page_path) for item in items):
            active_category = layout_category

    if active_category is None and categories:
        active_category = categories[0]
    return categories, active_category, active_category


def find_active_category(
    categories: list[LayoutMenuCategory],
    page_path: str,
) -> LayoutMenuCategory | None:
    """按路径查找当前一级分类。"""
    for category in categories:
        if any(_menu_item_contains_path(item, page_path) for item in category.items):
            return category
    return categories[0] if categories else None


def category_contains_path(category: LayoutMenuCategory, page_path: str) -> bool:
    """判断一级分类是否包含指定路径。"""
    return any(_menu_item_contains_path(item, page_path) for item in category.items)


def build_left_drawer(
    page_path: str,
    active_category: LayoutMenuCategory | None,
    expanded: bool = True,
) -> LeftDrawerNav:
    """构建左侧导航抽屉。"""
    drawer_classes = "ng-left-drawer"
    if active_category is None:
        drawer_classes += " ng-left-drawer-empty"

    with ui.left_drawer(value=expanded).props(f"width={DRAWER_WIDTH}").classes(drawer_classes) as left_drawer:
        container = ui.column().classes("w-full mt-4 px-2 pb-4 gap-1")
        nav = LeftDrawerNav(
            drawer=left_drawer,
            container=container,
            active_category=active_category,
            current_path=page_path,
        )
        with container:
            if active_category is None:
                _render_empty_placeholder()
            else:
                for item in active_category.items:
                    _render_nav_item(item=item, page_path=page_path, item_refs=nav.item_refs)
    return nav


def _is_same_category(
    current: LayoutMenuCategory | None,
    incoming: LayoutMenuCategory | None,
) -> bool:
    """判断两个一级分类是否为同一分类。"""
    if current is None or incoming is None:
        return current is incoming
    return current.title == incoming.title


def _render_empty_placeholder() -> None:
    """渲染无菜单占位。"""
    with ui.column().classes("ng-drawer-placeholder rounded-xl p-4 gap-2"):
        ui.icon("menu_open").classes("text-2xl text-primary")
        ui.label("暂无可展示菜单").classes("text-base font-semibold")
        ui.label("当前账号没有可访问的模块入口。").classes("ng-muted-text text-sm")


def _filter_menu_items(items: list[dict], permission_set: set[str]) -> list[dict]:
    """按权限过滤菜单项。"""
    result: list[dict] = []
    for item in items:
        permission = str(item.get("permission") or "").strip()
        if permission and permission not in permission_set:
            continue
        copied = dict(item)
        children = item.get("children", [])
        if isinstance(children, list) and children:
            copied["children"] = _filter_menu_items(children, permission_set)
        result.append(copied)
    return result


def _find_first_link(item: dict) -> str:
    """查找菜单项中的首个可跳转路径。"""
    link = str(item.get("link") or "").strip()
    if link:
        return link
    children = item.get("children", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                child_link = _find_first_link(child)
                if child_link:
                    return child_link
    return ""


def _menu_item_contains_path(item: dict, page_path: str) -> bool:
    """判断菜单项是否命中当前路径。"""
    if page_path == str(item.get("link") or "").strip():
        return True
    children = item.get("children", [])
    return isinstance(children, list) and any(
        _menu_item_contains_path(child, page_path)
        for child in children
        if isinstance(child, dict)
    )


def _render_nav_item(*, item: dict, page_path: str, item_refs: dict[str, tuple[ui.item, ui.label]]) -> None:
    """渲染左侧导航项。"""
    children = item.get("children", [])
    if isinstance(children, list) and children:
        has_active_child = any(_menu_item_contains_path(child, page_path) for child in children if isinstance(child, dict))
        with ui.expansion(item["label"], icon=item.get("icon", "")).classes(
            "ng-nav-expansion w-full rounded-[18px] px-1 py-1"
        ) as expansion:
            with ui.column().classes("w-full gap-1 pb-1"):
                for child in children:
                    if isinstance(child, dict):
                        _render_nav_item(item=child, page_path=page_path, item_refs=item_refs)
            if has_active_child:
                expansion.open()
        return

    is_active = page_path == item["link"]
    item_classes = "ng-nav-item w-full items-center rounded-xl px-3 py-2.5"
    if is_active:
        item_classes += " ng-nav-item-active"
    with ui.item(on_click=lambda link=item["link"]: ui.navigate.to(link)).classes(item_classes) as nav_item:
        with ui.row().classes("w-full no-wrap items-center justify-between gap-2"):
            with ui.row().classes("items-center no-wrap min-w-0 gap-3"):
                with ui.element("div").classes("ng-nav-icon-shell"):
                    ui.icon(item.get("icon", "")).classes("ng-nav-icon")
                text_classes = "ng-nav-text text-[1rem] font-bold" if is_active else "ng-nav-text text-[1rem] font-semibold"
                label = ui.label(item["label"]).classes(text_classes)
    item_refs[str(item["link"])] = (nav_item, label)


def _set_nav_item_active(nav_item: ui.item, label: ui.label, is_active: bool) -> None:
    """更新左侧菜单项高亮。"""
    if is_active:
        nav_item.classes(add="ng-nav-item-active")
        label.classes(add="font-bold", remove="font-semibold")
        return
    nav_item.classes(remove="ng-nav-item-active")
    label.classes(add="font-semibold", remove="font-bold")
