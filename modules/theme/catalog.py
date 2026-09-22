"""系统能力：可切换主题的目录。

当前收录「牛油果」「黑白配」「勃艮第」「深海蓝」；后续主题在此追加即可被页头圆点选择。
"""

from __future__ import annotations

from dataclasses import dataclass

from settings import UI


@dataclass(frozen=True, slots=True)
class Theme:
    """一套可切换的界面配色。"""

    key: str
    name: str
    primary: str
    secondary: str
    background: str

    def as_colors(self) -> dict[str, str]:
        """供 ``ui.colors`` 使用的品牌色。"""
        return {"primary": self.primary, "secondary": self.secondary}


AVOCADO = Theme(
    key="avocado",
    name="牛油果",
    primary=UI.primary,
    secondary=UI.secondary,
    background=UI.background,
)

BLACK_WHITE = Theme(
    key="black_white",
    name="黑白配",
    primary="#000000",
    secondary=UI.secondary,
    background="#ffffff",
)

CINNABAR = Theme(
    key="cinnabar",
    name="勃艮第",
    primary="#800020",
    secondary=UI.secondary,
    background="#ffffff",
)

DEEP_SEA = Theme(
    key="deep_sea",
    name="深海蓝",
    primary="#003366",
    secondary="#26a69a",
    background="#ffffff",
)

THEMES: dict[str, Theme] = {
    AVOCADO.key: AVOCADO,
    BLACK_WHITE.key: BLACK_WHITE,
    CINNABAR.key: CINNABAR,
    DEEP_SEA.key: DEEP_SEA,
}
DEFAULT_THEME = AVOCADO


def get_theme(theme_key: str | None) -> Theme:
    """按编码取主题；未知或空值回退到默认主题。"""
    if not theme_key:
        return DEFAULT_THEME
    return THEMES.get(str(theme_key).strip(), DEFAULT_THEME)


def list_themes() -> list[Theme]:
    """返回可选主题，顺序稳定。"""
    return list(THEMES.values())
