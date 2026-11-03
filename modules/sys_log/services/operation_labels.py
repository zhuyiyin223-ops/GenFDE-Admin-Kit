"""业务域：操作类型文案。非事务。"""

from __future__ import annotations

from models import OperationType

OPERATION_TYPE_LABELS: dict[int, str] = {
    OperationType.CREATE.value: "新增",
    OperationType.READ.value: "查询",
    OperationType.UPDATE.value: "修改",
    OperationType.DELETE.value: "删除",
    OperationType.LOGIN.value: "登录",
    OperationType.LOGOUT.value: "登出",
    OperationType.EXPORT.value: "导出",
    OperationType.IMPORT.value: "导入",
    OperationType.ENABLE.value: "启用",
    OperationType.DISABLE.value: "禁用",
    OperationType.UPLOAD.value: "上传",
    OperationType.OTHER.value: "其他",
}


def get_operation_type_options() -> dict[int | None, str]:
    """返回操作类型筛选选项。"""
    return {
        None: "全部",
        OperationType.CREATE.value: "新增",
        OperationType.READ.value: "查询",
        OperationType.UPDATE.value: "修改",
        OperationType.DELETE.value: "删除",
        OperationType.LOGIN.value: "登录",
        OperationType.LOGOUT.value: "登出",
        OperationType.EXPORT.value: "导出",
        OperationType.IMPORT.value: "导入",
        OperationType.ENABLE.value: "启用",
        OperationType.DISABLE.value: "禁用",
        OperationType.UPLOAD.value: "上传",
        OperationType.OTHER.value: "其他",
    }
