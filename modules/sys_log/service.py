"""系统日志服务层。"""

from __future__ import annotations

import asyncio
import gzip
import json
from collections import deque
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from tortoise.expressions import Q

from models import OperationType, User, UserLog
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.excel.service import ExcelExportService, ExcelFile
from modules.keyword_search.service import build_keyword_q, or_q
from settings import LOG, PROJECT_ROOT

USER_LOG_EXPORT_HEADERS = {
    "user_name": "姓名",
    "user_id": "账号",
    "operation_type": "操作类型",
    "module": "模块",
    "action": "动作",
    "execution_time": "耗时",
    "created_at": "时间",
}


class LogService:
    """系统日志查询与归档服务。"""

    USER_LOG_ONLINE_RETENTION_DAYS = 90
    USER_LOG_ARCHIVE_RETENTION_DAYS = 365
    USER_LOG_ARCHIVE_BATCH_SIZE = 500
    USER_LOG_ARCHIVE_DIR = PROJECT_ROOT / "data" / "archives" / "user_logs"

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

    @staticmethod
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

    @classmethod
    async def archive_and_cleanup_user_logs(cls) -> dict[str, int]:
        """归档超过在线保留期的操作日志，并清理超过归档保留期的文件。"""
        archive_dir = cls.USER_LOG_ARCHIVE_DIR
        archive_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        archive_before = now - timedelta(days=cls.USER_LOG_ONLINE_RETENTION_DAYS)
        archive_path = archive_dir / f"user_logs_{now:%Y-%m-%d}.jsonl.gz"
        archived_count = 0

        while True:
            rows = await UserLog.filter(created_at__lt=archive_before).order_by("id").limit(
                cls.USER_LOG_ARCHIVE_BATCH_SIZE
            ).values(
                "id",
                "operation_type",
                "module",
                "action",
                "execution_time",
                "before_change",
                "after_change",
                "note",
                "user_id",
                "created_at",
            )
            if not rows:
                break

            with gzip.open(archive_path, "at", encoding="utf-8") as archive_file:
                for row in rows:
                    archive_file.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

            deleted_count = await UserLog.filter(id__in=[row["id"] for row in rows]).delete()
            if deleted_count <= 0:
                raise RuntimeError("操作日志归档完成但数据库记录未删除")
            archived_count += int(deleted_count)
            if len(rows) < cls.USER_LOG_ARCHIVE_BATCH_SIZE:
                break

        archive_expire_at = now - timedelta(days=cls.USER_LOG_ARCHIVE_RETENTION_DAYS)
        deleted_archive_count = 0
        for archive_file in archive_dir.glob("user_logs_*.jsonl.gz"):
            if archive_file.stat().st_mtime < archive_expire_at.timestamp():
                archive_file.unlink()
                deleted_archive_count += 1

        logger.info(
            "操作日志归档清理完成：归档并删除 {} 条，清理归档文件 {} 个",
            archived_count,
            deleted_archive_count,
        )
        return {
            "archived_count": archived_count,
            "deleted_archive_count": deleted_archive_count,
        }

    @staticmethod
    async def _user_log_q_by_user_keyword(keyword: str | None) -> Q | None:
        """按操作用户账号或姓名关键词反查日志。"""
        user_q = build_keyword_q(("userid", "name"), keyword, model=User)
        if user_q is None:
            return None
        user_ids = [int(pk) for pk in await User.filter(user_q).values_list("id", flat=True)]
        if not user_ids:
            return None
        return Q(user_id__in=user_ids)

    @staticmethod
    async def query_user_logs(
        page: int = 1,
        page_size: int = 10,
        keyword: str = "",
        date_range: str = "",
        operation_type: int | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        """分页查询操作日志。"""
        query = Q()
        keyword_q = or_q(
            build_keyword_q(
                ("module", "action", "execution_time", "created_at"),
                keyword,
                model=UserLog,
                labels={"operation_type": LogService.OPERATION_TYPE_LABELS},
            ),
            await LogService._user_log_q_by_user_keyword(keyword),
        )
        if keyword_q:
            query &= keyword_q
        query = apply_column_filter_q(query, column_filter_specs, column_filters)

        date_range_text = str(date_range or "").strip()
        if date_range_text and " - " in date_range_text:
            start_text, end_text = date_range_text.split(" - ", 1)
            start_dt = LogService._parse_date(start_text)
            end_dt = LogService._parse_date(end_text)
            if start_dt is not None:
                query &= Q(created_at__gte=start_dt)
            if end_dt is not None:
                query &= Q(created_at__lt=end_dt + timedelta(days=1))

        if operation_type is not None:
            query &= Q(operation_type=operation_type)

        current_page = max(1, int(page))
        current_page_size = max(1, int(page_size))
        total = await UserLog.filter(query).count()
        logs = await UserLog.filter(query).offset((current_page - 1) * current_page_size).limit(
            current_page_size
        ).order_by("-created_at", "-id")

        user_ids = list({int(item.user_id) for item in logs if item.user_id})
        users = await User.filter(id__in=user_ids).values("id", "name", "userid") if user_ids else []
        user_map = {int(row["id"]): row for row in users if row.get("id") is not None}

        rows = []
        for index, item in enumerate(logs, start=(current_page - 1) * current_page_size + 1):
            user_row = user_map.get(int(item.user_id)) if item.user_id else None
            operation_type_value = int(item.operation_type) if item.operation_type is not None else -1
            rows.append(
                {
                    "id": int(item.id),
                    "index": index,
                    "user_name": str(user_row.get("name")) if user_row else "-",
                    "user_id": str(user_row.get("userid")) if user_row else str(item.user_id),
                    "operation_type": LogService.OPERATION_TYPE_LABELS.get(operation_type_value, "未知"),
                    "module": item.module or "",
                    "action": item.action or "",
                    "execution_time": f"{float(item.execution_time):.4f}s" if item.execution_time is not None else "",
                    "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
                }
            )

        return {"logs": rows, "total": total, "page": current_page, "page_size": current_page_size}

    @staticmethod
    async def export_user_logs(
        *,
        keyword: str = "",
        date_range: str = "",
        operation_type: int | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> ExcelFile:
        """按当前筛选导出操作日志，不处理浏览器下载。"""
        result = await LogService.query_user_logs(
            page=1,
            page_size=ExcelExportService.MAX_ROWS,
            keyword=keyword,
            date_range=date_range,
            operation_type=operation_type,
            column_filters=column_filters,
            column_filter_specs=column_filter_specs,
        )
        rows = [LogService._to_export_row(item) for item in result.get("logs", [])]
        return ExcelExportService.build_file(
            rows,
            USER_LOG_EXPORT_HEADERS,
            filename_stem="操作日志",
            total=int(result.get("total") or 0),
            sheet_name="操作日志",
        )

    @staticmethod
    def _to_export_row(item: dict[str, Any]) -> dict[str, Any]:
        """将操作日志展示行转为导出字段。"""
        return {
            "user_name": item.get("user_name") or "",
            "user_id": item.get("user_id") or "",
            "operation_type": item.get("operation_type") or "",
            "module": item.get("module") or "",
            "action": item.get("action") or "",
            "execution_time": item.get("execution_time") or "",
            "created_at": item.get("created_at") or "",
        }

    @staticmethod
    def _parse_date(text: str) -> datetime | None:
        """将日期文本转换为当天零点。"""
        normalized = str(text or "").strip()
        if not normalized:
            return None
        try:
            return datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    async def read_error_log_lines(limit: int = 500) -> list[str]:
        """读取错误日志末尾若干行并按新到旧返回。"""
        file_path = LOG.error_file
        if not file_path.exists():
            return [f"[日志文件不存在] {file_path}"]
        return await asyncio.to_thread(
            LogService._read_log_tail,
            file_path=file_path,
            limit=limit,
        )

    @staticmethod
    def _read_log_tail(*, file_path: Path, limit: int) -> list[str]:
        """读取日志文件尾部行，避免整文件读入内存。"""
        tail: deque[str] = deque(maxlen=max(1, int(limit)))
        with file_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
            for line in file_obj:
                tail.append(line.rstrip("\n"))
        if not tail:
            return ["[空日志]"]
        lines = list(tail)
        lines.reverse()
        return lines
