"""业务域：示例事项。给 AI 对照的新增模块模板，禁止被其他业务域 import。

新增业务域时复制本目录，再按 AGENTS.md 项目结构约定改：
``models.py``、``PermissionItem``、菜单、``PAGE_MODULE_NAMES``。
列表页在 ``page_table`` 声明 ``ListPageSpec``，由 ``ListPageFacade`` 装配。
事务用例放在 ``services/``，每个文件只承载一个事务。
交付项目可整包删除，并去掉上述四处中的 example 条目。
"""
