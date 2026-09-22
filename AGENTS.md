# AGENTS.md

约束 AI 在本仓库中的行为：结构清晰、命名一致、查询高效、可持续重构。

## 0. 核心原则

- 可维护性第一，代码极简，结构优先，先分层再实现，避免职责混乱；发现重复先抽取
- 建模简单稳定，公用枚举放 `models.py`；仅使用逻辑外键，关联字段命名规范 `[主表名单数]_id`。已有表追加列必须 `null=True`（迁库安全）；新表及业务必填列、唯一约束组成列不得无故可空。时间用 naive 本地时间，PostgreSQL 用 `timestamp` 不用 `timestamptz`
- `models.py` 全局共用。`modules/` 分四类：装配层、系统能力、业务共用、业务域。业务域只处理本域，禁止 import 其他业务域、调用其 service 或纳入同一事务。跨模块复用只允许依赖系统能力或业务共用；二者禁止反向依赖业务域
- 业务逻辑只进 service，禁止绕过 service 编排，事务一致性由应用层保证
- 查询严禁“N+1”，必须使用“查询主数据 + 批量查询关联数据 + 内存组装”模式
- `ruff check` 必须零警告（`pyproject.toml` 已 ignore 的不要再绕；其余改代码，禁止堆 noqa）
- 如无特殊说明，无需自行打开浏览器检查

## 1. 项目结构

- `app.py`：入口；装配在 `modules/application/registration.py`
- `deploy.py`：（可选）服务器侧部署编排，负责同步代码、执行迁移并重启进程；凭据从 `.env` 读取
- `remote_deploy.py`：（可选）本地远程部署入口，通过 SSH 调用服务器上的 `deploy.py`；SSH 凭据从 `.env` 读取
- `models.py`：ORM 模型定义
- `apis/`：装配层，对外 HTTP 入参/出参，不直接承载核心业务编排
- `static/`：静态资源
- `migrations/`：数据库迁移目录，不入库；develop 首次启动自动创建。AI 编码时不写迁移文件

### 1.1 模块分类

`modules/` 下按身份平铺，禁止再套 `common` / `shared` / `utils` 父包。子包 `__init__.py` 首句标明分类。

| 分类 | 命名 | 谁能引用 | 现有包 |
|---|---|---|---|
| 装配层 | 职责名 | 可引用业务域 | `application/`、`middleware/`、`cron_job/`、`routes.py`；仓库根目录 `apis/` |
| 系统能力 | 能力名，不加域前缀 | 业务域、业务共用可引用 | `layout/`、`ui/`、`permission/`、`password/`、`list_page/`、`table_column_setting/`、`filter_scheme/`、`keyword_search/`、`column_filter/`、`theme/`、`background_job/`、`excel/`、`message/`、`event_hub.py`、`log_audit.py` |
| 业务共用 | `biz_<业务概念>` | 业务域可引用其 service，禁止引用其 page | 按需新增，如 `biz_document` |
| 业务域 | `sys_*` 为框架管理域，其余用领域名 | 禁止被其他业务域引用 | `login/`、`sys_user/`、`sys_role/`、`sys_log/`、`sys_api/`、`example/` |

依赖方向：业务域 → 系统能力 / 业务共用；业务共用 → 系统能力；系统能力不依赖业务域或业务共用；装配层可编排业务域，并把系统能力挂到扩展点（如将消息通知注入后台壳）。

抽离：同一能力被两个及以上业务域需要，或无单一归属时才抽。平台手段 → 系统能力；跨域且稳定的业务概念 → `biz_*`。域内特化规则留在该域 service。包名用概念，不用动词。

### 1.2 目录职责

装配层：

- `modules/application/`：生命周期、日志初始化、运行期目录、中间件、API 路由和静态资源注册；启动时拉起 `cron_job` 调度器。`APP.env == "develop"` 时启动会建库、无迁移则生成、再执行迁移；生产不自动改库结构
- `modules/middleware/`：认证、日志、真实 IP 等请求链
- `modules/routes.py`：页面路由闭集注册
- `modules/cron_job/`：进程内定时任务闭集注册（对照 `routes.py`）。平台任务（库备份）实现放本包；业务任务只注册并调用所属域 service，不纳入同一事务、不依赖其 page。无管理页，不与 `background_job` 混用（后者是请求内进度任务）

系统能力：

- `modules/layout/`：页面框架、导航、页头、样式；页头右侧附加区由装配层注入
- `modules/ui/`：标题、分页表格、附件上传与展示
- `modules/list_page/`：列表页门面。业务域在 `page_table` 声明 `ListPageSpec`（列与筛选），由 `ListPageFacade` 接上模糊搜索、列筛选、过滤方案、列设置、导出按钮与分页。`attach_column_filters` 默认 `True`，`mount` / `bind_table` 时自动给可筛列挂表头筛选；关掉则只保留芯片与方案。域内按钮、表格 slot、导出权限仍由本域 page 负责
- `modules/theme/`：可切换界面主题；页头按钮在消息通知左侧，偏好绑定账号
- `modules/table_column_setting/`：表格列显示偏好
- `modules/filter_scheme/`：列表过滤方案；按账号保存个人结构化筛选组合（不含模糊搜索与分页），保存弹窗展示条件并命名，表格上方 teal 芯片套用（未选中为描边）；芯片编辑弹窗标题为「方案编辑」，方案名用表单输入，未启用筛选与启用筛选两列可互相拖拽（NiceGUI make_sortable）或点箭头/关闭移动，点击启用字段编辑条件（保存后若正在套用则同步刷表），并可删除方案；套用后完整替换当前筛选并展示列筛选芯片；业务域 opt-in，不可分享
- `modules/keyword_search/`：列表模糊搜索框；空格分隔多个关键词，按 OR 命中声明字段（含数字、时间、状态文案）
- `modules/column_filter/`：表格列头筛选；字符串列弹出关键词模糊搜索与空值勾选（空格分隔多个关键词，按 OR 命中），日期列弹出日期范围、快捷单选与空值，数字列弹出闭区间与空值（缺一端则为 ≥ 或 ≤），选择列（布尔与枚举同一套）下拉多选与空值勾选；关联展示列声明 `relation`（逻辑外键/中间表），交互复用字符串弹窗，按关联文本反查主表，空值表示无关联行；表格上方芯片展示；业务域 opt-in，会话内生效
- `modules/permission/`：权限定义、鉴权、菜单结构、权限上下文
- `modules/password/`：密码哈希与校验
- `modules/background_job/`：后台任务与进度条；按需创建实例，禁止做成进程单例
- `modules/excel/`：Excel 导出；业务域按当前筛选生成文件，在列表页直接下载。导出权限独立于查看和编辑，不落导出记录，不单独开个人中心或导出历史页
- `modules/message/`：站内消息与通知。业务域只调用 `MessageService` 发给指定用户或一批用户；页头组件由装配层注入 layout；在线推送走 `event_hub`，不轮询
- `modules/event_hub.py`：进程内事件总线；消息通知等系统能力使用。业务域不要直接发布站内消息
- `modules/log_audit.py`：操作日志审计

业务域：

- `modules/login/`：登录页、登录态与退出
- `modules/sys_user/`：用户账号
- `modules/sys_role/`：角色权限
- `modules/sys_log/`：系统日志查看；操作日志在线保留与归档策略由本域 service 负责，装配层按点触发
- `modules/sys_api/`：接口服务管理
- `modules/example/`：教学用 CRUD 模板，给 AI 对照复制；交付项目可整包删除
- `modules/<domain>/`：后续业务域，按领域组织（如 `profile_*`）

业务域内部分层：

- `page.py`：UI 层（NiceGUI 页面）
- `service.py`：业务层（唯一业务入口）
- `page_controller.py`：页面状态、事件编排、表格刷新
- `page_forms.py`：表单构建、输入归一化、初始值转换
- `page_table.py`：列定义、slot 模板、展示行转换

业务共用以 service 为入口，可以没有页面；若有管理页，其他模块只允许依赖 service。

### 1.3 新增业务域

本仓库是应用骨架，不是插件框架。新增带列表页的业务域按下面闭集改，不要加登记表、插件入口或脚手架。

对照实现：`modules/example/`（示例事项）。

1. 在 `models.py` 追加模型（仅逻辑外键；已有表追加列必须 `null=True`；新表必填列与唯一约束组成列不得无故可空）。
2. 在 `modules/permission/definitions.py`：如需新一级菜单则向 `PermissionCategories` 加分类并写入 `ORDER`；向 `PermissionItem` 追加 `query` / `edit`（导出按需）；在 `get_menu_structure()` 追加菜单项。
3. 复制 `modules/example/` 为 `modules/<domain>/`，改包名、路径、权限码、`ListPageSpec` 和 service。无表格的域可省略 `page_table.py`。
4. 在 `modules/routes.py` 的 `PAGE_MODULE_NAMES` 追加 `"modules.<domain>.page"`。
5. 模型变更后可执行 `tortoise makemigrations`。develop 首次无迁移目录时会自动生成并执行；AI 编码时不写迁移文件。

列表页在 `page_table` 声明 `ListPageSpec`，page 用 `ListPageFacade` 装配。不要在业务域再手写搜索/列筛选/方案/列设置/分页接线。`attach_column_filters` 默认自动挂表头筛选。导出权限与域内按钮仍由本域 page 负责。

交付时若不需要示例：删除 `modules/example/`，并去掉 `models.ExampleItem`、`PermissionItem` 中的 `EXAMPLE_*`、`PermissionCategories.EXAMPLE`、对应菜单项，以及 `PAGE_MODULE_NAMES` 里的 example。

### 1.4 新增定时任务

`modules/cron_job/` 是装配层，不是业务域，也不是插件入口。对照 `routes.py`：命令写在归属处，本包只做闭集注册。

1. 平台运维（库备份这类无业务归属的任务）实现放 `modules/cron_job/`。
2. 业务定时命令写在所属业务域 `service.py`，由本包调用；不要把业务规则写进 cron_job，不要为此新建一个「定时任务域」。
3. 在 `modules/cron_job/cron_jobs.py` 注册（触发时刻进 `settings.CRON`）。失败要自己吞掉，不影响调度器。
4. 不要和 `background_job` 混用：后者是请求内进度任务，按需创建实例，禁止做成进程单例。

## 2. 编码规范

- 遵循 PEP 8 和 PEP 257
- 涉及 ORM、网络请求、异步文件处理、事务等 I/O 操作的函数，优先使用 `async def`
- 应用日志统一使用 loguru

## 3. 命名规范

- 系统能力用能力名（`permission`、`password`、`list_page`、`table_column_setting`、`excel`、`message`）；业务共用用 `biz_<概念>`（`biz_document`）；业务域用 `sys_*` 或领域名（`sys_user`、`order`）
- 禁止 `shared`、`common`、`utils`；禁止用 `sys_` 表示系统能力（`sys_` 只表示框架管理业务域）
- 类名简洁明确（如 `UserService`）

## 4. 注释规范

- 模块、类、公开方法必须有中文 docstring，保持简洁、专业、可维护
- `modules/` 子包 `__init__.py` 与顶层模块文件首句标明分类：装配层 / 系统能力 / 业务共用 / 业务域
- 注释只说明职责、边界和必要上下文，不重复代码字面含义
- 修改代码时必须同步更新注释
