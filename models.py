"""框架级数据模型。

公用枚举与全部 ORM 模型放在本文件。新增业务域时在此追加模型类。
"""

from __future__ import annotations

from enum import IntEnum

from tortoise import fields
from tortoise.models import Model


class OperationType(IntEnum):
    """系统操作类型。"""

    CREATE = 1
    READ = 2
    UPDATE = 3
    DELETE = 4
    LOGIN = 5
    LOGOUT = 6
    EXPORT = 7
    IMPORT = 8
    ENABLE = 9
    DISABLE = 10
    UPLOAD = 11
    OTHER = 99


class User(Model):
    """用户信息模型。

    仅保留模板登录所需字段；用户管理、角色权限和数据范围不放在登录骨架中。
    """

    class Meta:
        table = "users"
        table_description = "用户信息表"

    id = fields.BigIntField(pk=True)
    userid = fields.CharField(max_length=32, unique=True, db_index=True, description="账号")
    password_hash = fields.CharField(max_length=256, description="密码哈希值")
    name = fields.CharField(max_length=32, db_index=True, description="姓名")
    is_active = fields.BooleanField(default=True, description="是否激活")
    is_admin = fields.BooleanField(default=False, description="是否管理员")
    alternative_id = fields.CharField(max_length=128, unique=True, description="登录会话替代标识")
    login_count = fields.IntField(default=0, description="登录次数")
    last_active_at = fields.DatetimeField(null=True, description="最近活跃时间")
    ip_addr = fields.CharField(max_length=32, null=True, description="登录IP")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    disabled_at = fields.DatetimeField(null=True, description="禁用时间")

    def __str__(self) -> str:
        return self.userid


class Role(Model):
    """角色模型。"""

    class Meta:
        table = "roles"
        table_description = "角色表"

    id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=64, db_index=True, description="角色名称")
    code = fields.CharField(max_length=64, unique=True, db_index=True, description="角色编码")
    description = fields.CharField(max_length=255, null=True, description="角色说明")
    is_active = fields.BooleanField(default=True, description="是否启用")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    def __str__(self) -> str:
        return self.name


class RolePermission(Model):
    """角色权限关系。"""

    class Meta:
        table = "role_permissions"
        table_description = "角色权限关系表"
        unique_together = (("role_id", "permission_code"),)

    id = fields.BigIntField(pk=True)
    role_id = fields.BigIntField(db_index=True, description="角色ID")
    permission_code = fields.CharField(max_length=128, db_index=True, description="权限编码")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class UserRole(Model):
    """用户角色关系。"""

    class Meta:
        table = "user_roles"
        table_description = "用户角色关系表"
        unique_together = (("user_id", "role_id"),)

    id = fields.BigIntField(pk=True)
    user_id = fields.BigIntField(db_index=True, description="用户ID")
    role_id = fields.BigIntField(db_index=True, description="角色ID")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class UserAttachment(Model):
    """用户附件模型。"""

    class Meta:
        table = "user_attachments"
        table_description = "用户附件表"

    id = fields.BigIntField(pk=True)
    original_name = fields.CharField(max_length=255, description="原文件名")
    storage_name = fields.CharField(max_length=64, description="UUID存储文件名")
    content_type = fields.CharField(max_length=128, description="文件类型")
    file_size = fields.BigIntField(description="文件大小")
    storage_path = fields.CharField(max_length=512, description="存储路径")
    user_id = fields.BigIntField(db_index=True, description="用户ID")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class UserMessage(Model):
    """用户消息模型。"""

    class Meta:
        table = "user_messages"
        table_description = "用户消息表"

    id = fields.BigIntField(pk=True)
    content = fields.TextField(description="消息内容")
    user_id = fields.BigIntField(db_index=True, description="用户ID")
    read = fields.BooleanField(default=False, db_index=True, description="是否已读")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class UserLog(Model):
    """用户操作日志模型。"""

    class Meta:
        table = "user_logs"
        table_description = "操作日志表"
        indexes = [("user_id", "created_at")]

    id = fields.BigIntField(pk=True, description="主键ID")
    operation_type = fields.IntEnumField(OperationType, description="操作类型")
    module = fields.CharField(max_length=128, description="所属模块")
    action = fields.CharField(max_length=128, description="具体操作")
    execution_time = fields.DecimalField(max_digits=10, decimal_places=4, description="执行时间（秒）")
    before_change = fields.JSONField(description="修改前的数据", null=True)
    after_change = fields.JSONField(description="修改后的数据", null=True)
    note = fields.JSONField(description="其他信息", null=True)
    user_id = fields.BigIntField(description="操作用户ID", db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True, description="创建时间")


class ApiClient(Model):
    """API 客户端账号模型。"""

    class Meta:
        table = "api_clients"
        table_description = "API客户端账号表"

    id = fields.BigIntField(pk=True)
    client_id = fields.CharField(max_length=64, unique=True, db_index=True, description="客户端账号")
    password_hash = fields.CharField(max_length=256, description="客户端密码哈希值")
    name = fields.CharField(max_length=64, null=True, description="客户端名称")
    ip_whitelist = fields.TextField(null=True, description="IP白名单")
    last_ip = fields.CharField(max_length=64, null=True, description="最后登录IP")
    is_active = fields.BooleanField(default=True, description="是否激活")
    last_login_at = fields.DatetimeField(null=True, description="最后登录时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(null=True, description="更新时间")


class ApiToken(Model):
    """API 令牌模型。"""

    class Meta:
        table = "api_tokens"
        table_description = "API刷新令牌表"
        indexes = [("client_id", "expires_at")]

    id = fields.BigIntField(pk=True)
    jti = fields.CharField(max_length=64, unique=True, db_index=True, description="令牌ID")
    token_type = fields.CharField(max_length=16, description="令牌类型")
    token_hash = fields.CharField(max_length=256, description="刷新令牌哈希")
    expires_at = fields.DatetimeField(description="过期时间")
    client_id = fields.BigIntField(db_index=True, description="客户端ID")
    revoked_at = fields.DatetimeField(null=True, description="撤销时间")
    last_used_at = fields.DatetimeField(null=True, description="最近使用时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class ApiRequestLog(Model):
    """API 请求日志模型。"""

    class Meta:
        table = "api_request_logs"
        table_description = "API请求日志表"
        indexes = [("client_id", "created_at")]

    id = fields.BigIntField(pk=True)
    method = fields.CharField(max_length=8, description="请求方法")
    path = fields.CharField(max_length=256, description="请求路径")
    status_code = fields.IntField(description="响应状态码")
    process_ms = fields.IntField(null=True, description="处理耗时(ms)")
    client_id_text = fields.CharField(max_length=64, null=True, description="客户端账号")
    ip_addr = fields.CharField(max_length=64, null=True, description="客户端IP")
    user_agent = fields.CharField(max_length=512, null=True, description="User-Agent")
    request_body = fields.TextField(null=True, description="请求内容")
    response_body = fields.TextField(null=True, description="响应内容")
    client_id = fields.BigIntField(null=True, db_index=True, description="客户端ID")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")


class UserTablePreference(Model):
    """用户表格偏好模型。

    负责按账号保存指定页面表格的列显示配置。
    """

    class Meta:
        table = "user_table_preferences"
        table_description = "用户表格偏好配置表"
        unique_together = (("user_id", "page_code", "table_key"),)

    id = fields.BigIntField(pk=True)
    user_id = fields.BigIntField(db_index=True, description="用户ID")
    page_code = fields.CharField(max_length=64, description="页面编码")
    table_key = fields.CharField(max_length=64, description="表格标识")
    visible_column_names = fields.JSONField(description="可见列编码列表")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")


class FilterSchemeVisibility:
    """过滤方案可见性。存字符串，不是 IntEnum。"""

    PERSONAL = "personal"
    PUBLIC = "public"


class UserFilterScheme(Model):
    """用户过滤方案。

    按账号保存指定页面、指定列表上的多条命名结构化筛选快照。
    visibility=public 时 user_id 仍表示创建者，全员可见、仅创建者可改。
    """

    class Meta:
        table = "user_filter_schemes"
        table_description = "用户过滤方案表"
        indexes = (
            ("user_id", "page_code", "list_key"),
            ("page_code", "list_key", "visibility"),
        )

    id = fields.BigIntField(pk=True)
    user_id = fields.BigIntField(db_index=True, description="创建者用户ID")
    page_code = fields.CharField(max_length=64, description="页面编码")
    list_key = fields.CharField(max_length=64, description="列表标识")
    name = fields.CharField(max_length=32, description="方案名称")
    visibility = fields.CharField(
        max_length=16,
        default=FilterSchemeVisibility.PERSONAL,
        description="可见性 personal|public",
    )
    filter_values = fields.JSONField(description="结构化筛选取值（存储形态）")
    sort_order = fields.IntField(default=0, description="个人方案显示顺序")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")


class UserFilterSchemePref(Model):
    """用户在某一列表上的过滤方案偏好（默认方案）。

    每用户每列表一行。default_scheme_id 为空表示进入页面不套用方案。
    不得把默认方案做成方案表上的布尔列（公共方案会变成全局指针）。
    """

    class Meta:
        table = "user_filter_scheme_prefs"
        table_description = "用户过滤方案偏好表"
        unique_together = (("user_id", "page_code", "list_key"),)

    id = fields.BigIntField(pk=True)
    user_id = fields.BigIntField(db_index=True, description="用户ID")
    page_code = fields.CharField(max_length=64, description="页面编码")
    list_key = fields.CharField(max_length=64, description="列表标识")
    default_scheme_id = fields.BigIntField(null=True, description="默认方案ID")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")


class ExampleItem(Model):
    """示例事项。教学用，交付项目可删除本类及 example 域相关权限、菜单、路由。"""

    class Meta:
        table = "example_items"
        table_description = "示例事项表"

    id = fields.BigIntField(pk=True)
    title = fields.CharField(max_length=128, db_index=True, description="标题")
    content = fields.TextField(null=True, description="内容")
    is_done = fields.BooleanField(default=False, db_index=True, description="是否完成")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    def __str__(self) -> str:
        return self.title
