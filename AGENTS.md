# AGENTS.md

约束 AI 在本仓库中的行为：结构清晰、命名一致、查询高效、可持续重构。

## 0. 核心原则

- 可维护性第一，代码极简，结构优先，先分层再实现，避免职责混乱
- 查询严禁“N+1”，必须使用“查询主数据 + 批量查询关联数据 + 内存组装”模式
- `models.py` 全局共用，建模简单稳定，仅使用逻辑外键。字段说明写在 `Field(description=...)`，不要写 `#:` 源码注释（导入时已跳过源码扫描，避免模型变多后启动按平方变慢）。已有表追加列必须 `null=True`（迁库安全）
- 业务域只处理本域，一文件 = 一用例 = 一事务；跨模块复用只允许依赖系统能力或业务共用

## 1. 项目结构

```text
GenFDE-Admin-Kit/
├── app.py                       # 入口，只装配并启动
├── models.py                    # 全局 ORM
├── settings.py                  # 运行配置
├── deploy.py                    # 服务器部署
├── remote_deploy.py             # 本地经 SSH 调 deploy.py
├── apis/                        # 装配层：对外 HTTP，不编排业务
│   ├── auth.py
│   └── health.py
├── static/                      # 静态资源
├── migrations/                  # 模型迁移记录（自动生成）
├── modules/                     # 模块包，禁止再套父包
│   ├── application/             # 装配层：生命周期与注册
│   ├── middleware/              # 装配层：认证、日志、真实 IP
│   ├── routes.py                # 装配层：页面路由闭集
│   ├── cron_job/                # 装配层：定时任务闭集
│   ├── layout/                  # 系统能力：页面框架
│   ├── ui/                      # 系统能力：标题、表格、附件
│   ├── list_page/               # 系统能力：列表页门面
│   ├── permission/              # 系统能力：权限、菜单、鉴权
│   ├── password/                # 系统能力：密码哈希
│   ├── excel/                   # 系统能力：Excel 导出
│   ├── message/                 # 系统能力：站内消息
│   ├── event_hub.py             # 系统能力：进程内事件总线
│   ├── log_audit.py             # 系统能力：操作日志审计
│   ├── theme/                   # 系统能力：界面主题
│   ├── background_job/          # 系统能力：请求内进度任务
│   ├── keyword_search/          # 系统能力：模糊搜索
│   ├── column_filter/           # 系统能力：列头筛选
│   ├── filter_scheme/           # 系统能力：个人过滤方案
│   ├── table_column_setting/    # 系统能力：列显示偏好
│   ├── login/                   # 系统能力：登录
│   ├── sys_user/                # 框架管理域：用户账号
│   ├── sys_role/                # 框架管理域：角色权限
│   ├── sys_log/                 # 框架管理域：系统日志
│   ├── sys_api/                 # 框架管理域：开放 API
│   └── example/                 # 业务域模板，可删
│       ├── page.py              # UI
│       ├── page_controller.py   # 状态、事件、刷新
│       ├── page_forms.py        # 表单与输入归一化
│       ├── page_table.py        # 列、筛选、展示行
│       └── services/            # 业务唯一入口
│           ├── __init__.py      # 只再导出，__all__ 注明每个事务的功能
│           ├── search_items.py  # 一文件 = 一用例 = 一事务
│           ├── get_item.py
│           ├── create_item.py
│           ├── update_item.py
│           └── delete_item.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 2. 编码规范

- 遵循 PEP 8 和 PEP 257
- 涉及 ORM、网络请求、异步文件处理、事务等 I/O 操作的函数，优先使用 `async def`
- 应用日志统一使用 loguru
- `ruff check` 必须零警告（`pyproject.toml` 已 ignore 的不要再绕）

## 3. 命名规范

- 系统能力用能力名（如`permission`、`list_page`、`table_column_setting`、`excel`、`message`等）
- 业务域用 `biz_<领域>`；框架管理域用 `sys_*`
- 禁止 `shared`、`common`、`utils`等没有明确功能的命名
- 命名简洁明确，业务用例用模块级函数，不要在 `services/__init__.py` 里堆服务类

## 4. 注释规范

- 模块、类、公开方法必须有中文 docstring，保持简洁、专业、可维护
- `modules/` 子包 `__init__.py` 与顶层模块文件首句标明分类：装配层 / 系统能力 / 业务共用 / 业务域
- 注释只说明职责、边界和必要上下文，不重复代码字面含义
- 修改代码时必须同步更新注释
