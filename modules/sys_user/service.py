"""用户账号与附件服务层。"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from models import Role, User, UserAttachment, UserRole
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.excel.service import ExcelExportService, ExcelFile
from modules.keyword_search.service import STATUS_LABELS, YES_NO_LABELS, build_keyword_q, or_q
from modules.password.service import PasswordService
from modules.permission.service import PermissionService
from modules.ui.attachment_types import (
    DEFAULT_ATTACHMENT_EXTENSIONS,
    AttachmentItem,
    is_allowed_attachment_name,
    validate_attachment_preview_content,
)
from settings import PROJECT_ROOT

USER_ATTACHMENT_ROOT = PROJECT_ROOT / "data" / "upload" / "user"
USER_ATTACHMENT_MAX_FILES = 6
USER_ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024
USER_EXPORT_HEADERS = {
    "userid": "账号",
    "name": "姓名",
    "is_admin": "管理员",
    "roles": "角色",
    "is_active": "状态",
    "login_count": "登录次数",
    "last_active_at": "最近活跃时间",
    "ip_addr": "登录IP",
    "create_at": "创建于",
    "disabled_at": "禁用于",
}


class UserService:
    """用户账号数据服务。"""

    @staticmethod
    def is_password_policy_valid(password: str) -> bool:
        """校验旧系统同款密码策略。"""
        text = str(password or "").strip()
        if not 6 <= len(text) <= 16:
            return False
        return bool(
            re.search(r"[A-Z]", text)
            and re.search(r"[a-z]", text)
            and re.search(r"\d", text)
            and re.search(r"[^A-Za-z0-9]", text)
        )

    @staticmethod
    def _normalize_userid(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("账号不能为空")
        if len(text) > 32:
            raise ValueError("账号长度不能超过32个字符")
        return text

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("用户名不能为空")
        if len(text) > 32:
            raise ValueError("用户名长度不能超过32个字符")
        return text

    @staticmethod
    def _normalize_role_ids(role_ids: list[int] | None) -> list[int]:
        """归一化角色 ID 列表。"""
        normalized_ids: list[int] = []
        for role_id in role_ids or []:
            try:
                role_id_int = int(role_id)
            except (TypeError, ValueError):
                continue
            if role_id_int > 0 and role_id_int not in normalized_ids:
                normalized_ids.append(role_id_int)
        return normalized_ids

    @staticmethod
    async def get_role_options(*, include_role_ids: list[int] | None = None) -> dict[int, str]:
        """读取可选角色，编辑时允许带出已停用但已关联的角色。"""
        include_ids = UserService._normalize_role_ids(include_role_ids)
        query = Q(is_active=True)
        if include_ids:
            query |= Q(id__in=include_ids)
        roles = await Role.filter(query).order_by("id")
        return {int(role.id): role.name for role in roles}

    @staticmethod
    async def search_users(
        *,
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        status: bool | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        """分页查询用户并附带角色信息，不处理 UI 排序状态。"""
        page = max(1, int(page or 1))
        page_size = max(1, int(page_size or 10))

        query = Q()
        keyword_q = or_q(
            build_keyword_q(
                (
                    "userid",
                    "name",
                    "ip_addr",
                    "login_count",
                    "last_active_at",
                    "created_at",
                    "disabled_at",
                ),
                keyword,
                model=User,
                labels={"is_active": STATUS_LABELS, "is_admin": YES_NO_LABELS},
            ),
            await UserService._user_ids_q_by_role_keyword(keyword),
        )
        if keyword_q:
            query &= keyword_q
        if status is not None:
            query &= Q(is_active=bool(status))
        query = apply_column_filter_q(query, column_filter_specs, column_filters)

        total = await User.filter(query).count()
        users = await User.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
        user_ids = [int(user.id) for user in users]
        user_role_map = await UserService._build_user_role_map(user_ids)
        attachment_count_map = await UserAttachmentService.count_by_user_ids(user_ids)

        return {
            "users": [
                UserService._serialize_user(
                    user,
                    user_role_map.get(int(user.id), {"role_ids": [], "role_names": []}),
                    attachment_count=attachment_count_map.get(int(user.id), 0),
                )
                for user in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def export_users(
        *,
        keyword: str | None = None,
        status: bool | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> ExcelFile:
        """按当前筛选导出用户账号，不处理浏览器下载。"""
        result = await UserService.search_users(
            page=1,
            page_size=ExcelExportService.MAX_ROWS,
            keyword=keyword,
            status=status,
            column_filters=column_filters,
            column_filter_specs=column_filter_specs,
        )
        rows = [UserService._to_export_row(user) for user in result.get("users", [])]
        return ExcelExportService.build_file(
            rows,
            USER_EXPORT_HEADERS,
            filename_stem="用户账号",
            total=int(result.get("total") or 0),
            sheet_name="用户账号",
        )

    @staticmethod
    async def get_user_detail(user_id: int) -> dict[str, Any] | None:
        """获取用户详情，不做页面层处理。"""
        user = await User.filter(id=user_id).first()
        if not user:
            return None
        user_role_map = await UserService._build_user_role_map([int(user.id)])
        attachment_count_map = await UserAttachmentService.count_by_user_ids([int(user.id)])
        return UserService._serialize_user(
            user,
            user_role_map.get(int(user.id), {"role_ids": [], "role_names": []}),
            attachment_count=attachment_count_map.get(int(user.id), 0),
        )

    @staticmethod
    async def create_user(
        *,
        userid: str,
        password: str,
        name: str,
        role_ids: list[int],
        is_admin: bool,
    ) -> tuple[bool, str, User | None]:
        """创建用户账号，不处理页面交互和提示展示。"""
        try:
            normalized_userid = UserService._normalize_userid(userid)
            normalized_name = UserService._normalize_name(name)
        except ValueError as exc:
            return False, str(exc), None

        if await User.filter(userid=normalized_userid).exists():
            return False, "该账号已存在", None
        if not UserService.is_password_policy_valid(str(password or "")):
            return False, "密码必须为6到16位，包含大小写字母、数字、特殊符号", None

        normalized_role_ids = UserService._normalize_role_ids(role_ids)
        if not is_admin and not normalized_role_ids:
            return False, "非管理员账号必须分配至少一个角色", None

        try:
            async with in_transaction():
                user = await User.create(
                    userid=normalized_userid,
                    password_hash=PasswordService.hash_password(str(password).strip()),
                    name=normalized_name,
                    is_admin=bool(is_admin),
                    is_active=True,
                    alternative_id=uuid.uuid4().hex,
                    login_count=0,
                )
                await UserService._replace_user_roles(int(user.id), normalized_role_ids)
        except Exception:
            logger.exception("创建用户失败 userid={}", normalized_userid)
            return False, "用户创建失败，请稍后重试", None

        PermissionService.clear_user_permission_cache()
        return True, "用户创建成功", user

    @staticmethod
    async def update_user(
        *,
        user_id: int,
        userid: str,
        name: str,
        is_admin: bool,
        role_ids: list[int],
        is_active: bool,
        reset_password: bool,
        new_password: str | None = None,
    ) -> tuple[bool, str]:
        """更新用户账号信息，不处理页面层确认逻辑。"""
        try:
            normalized_userid = UserService._normalize_userid(userid)
            normalized_name = UserService._normalize_name(name)
        except ValueError as exc:
            return False, str(exc)

        normalized_role_ids = UserService._normalize_role_ids(role_ids)
        if not is_admin and not normalized_role_ids:
            return False, "非管理员账号必须分配至少一个角色"
        if reset_password and not UserService.is_password_policy_valid(str(new_password or "")):
            return False, "新密码必须为6到16位，包含大小写字母、数字、特殊符号"

        existing_user = await User.filter(userid=normalized_userid).exclude(id=user_id).first()
        if existing_user:
            return False, "该账号已被其他用户使用"

        try:
            async with in_transaction():
                user = await User.filter(id=user_id).first()
                if not user:
                    return False, "用户不存在"

                previous_is_active = bool(user.is_active)
                user.userid = normalized_userid
                user.name = normalized_name
                user.is_admin = bool(is_admin)
                user.is_active = bool(is_active)
                if previous_is_active and not user.is_active:
                    user.alternative_id = uuid.uuid4().hex
                    user.disabled_at = datetime.now()
                elif not previous_is_active and user.is_active:
                    user.disabled_at = None
                if reset_password:
                    user.password_hash = PasswordService.hash_password(str(new_password or "").strip())
                    user.alternative_id = uuid.uuid4().hex
                await user.save()
                await UserService._replace_user_roles(int(user.id), normalized_role_ids)
        except Exception:
            logger.exception("更新用户失败 user_id={}", user_id)
            return False, "用户更新失败，请稍后重试"

        PermissionService.clear_user_permission_cache(int(user_id))
        status_text = (
            "禁用"
            if previous_is_active and not is_active
            else "启用"
            if not previous_is_active and is_active
            else ""
        )
        if status_text:
            return True, f"用户更新成功，账号已{status_text}"
        return True, "用户更新成功"

    @staticmethod
    async def _user_ids_q_by_role_keyword(keyword: str | None) -> Q | None:
        """按角色名称关键词反查用户 ID。"""
        role_q = build_keyword_q(("name",), keyword, model=Role)
        if role_q is None:
            return None
        role_ids = [int(pk) for pk in await Role.filter(role_q).values_list("id", flat=True)]
        if not role_ids:
            return None
        user_ids = [
            int(pk)
            for pk in await UserRole.filter(role_id__in=role_ids).values_list("user_id", flat=True)
        ]
        if not user_ids:
            return None
        return Q(id__in=user_ids)

    @staticmethod
    async def _build_user_role_map(user_ids: list[int]) -> dict[int, dict[str, list[Any]]]:
        """构建用户角色映射。"""
        if not user_ids:
            return {}
        relation_rows = await UserRole.filter(user_id__in=user_ids).values("user_id", "role_id")
        role_ids = sorted({int(row["role_id"]) for row in relation_rows})
        roles = await Role.filter(id__in=role_ids).values("id", "name") if role_ids else []
        role_name_map = {int(role["id"]): str(role["name"]) for role in roles}
        result: dict[int, dict[str, list[Any]]] = {
            user_id: {"role_ids": [], "role_names": []}
            for user_id in user_ids
        }
        for row in relation_rows:
            user_id = int(row["user_id"])
            role_id = int(row["role_id"])
            result.setdefault(user_id, {"role_ids": [], "role_names": []})
            result[user_id]["role_ids"].append(role_id)
            result[user_id]["role_names"].append(role_name_map.get(role_id, str(role_id)))
        return result

    @staticmethod
    def _serialize_user(
        user: User,
        role_data: dict[str, list[Any]],
        *,
        attachment_count: int = 0,
    ) -> dict[str, Any]:
        """序列化用户行。"""
        return {
            "id": int(user.id),
            "userid": user.userid,
            "name": user.name,
            "is_admin": bool(user.is_admin),
            "is_active": bool(user.is_active),
            "role_ids": role_data.get("role_ids", []),
            "role_names": role_data.get("role_names", []),
            "attachment_count": int(attachment_count or 0),
            "login_count": int(user.login_count or 0),
            "last_active_at": user.last_active_at.strftime("%Y-%m-%d %H:%M") if user.last_active_at else "",
            "ip_addr": user.ip_addr or "",
            "create_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "",
            "disabled_at": user.disabled_at.strftime("%Y-%m-%d %H:%M") if user.disabled_at else "",
        }

    @staticmethod
    def _to_export_row(user: dict[str, Any]) -> dict[str, Any]:
        """将序列化用户行转为导出字段。"""
        return {
            "userid": user.get("userid") or "",
            "name": user.get("name") or "",
            "is_admin": "是" if user.get("is_admin") else "否",
            "roles": "、".join(user.get("role_names") or []) or "-",
            "is_active": "正常" if user.get("is_active") else "禁用",
            "login_count": user.get("login_count") or 0,
            "last_active_at": user.get("last_active_at") or "",
            "ip_addr": user.get("ip_addr") or "",
            "create_at": user.get("create_at") or "",
            "disabled_at": user.get("disabled_at") or "",
        }

    @staticmethod
    async def _replace_user_roles(user_id: int, role_ids: list[int]) -> None:
        """覆盖保存用户角色关系。"""
        normalized_role_ids = UserService._normalize_role_ids(role_ids)
        await UserRole.filter(user_id=user_id).delete()
        if normalized_role_ids:
            await UserRole.bulk_create(
                [UserRole(user_id=user_id, role_id=role_id) for role_id in normalized_role_ids]
            )


class UserAttachmentService:
    """管理用户附件文件及对应的数据库记录。"""

    @staticmethod
    async def list_attachments(user_id: int) -> list[AttachmentItem]:
        """查询指定用户的附件，并转换为通用展示数据。"""
        records = await UserAttachment.filter(user_id=int(user_id)).order_by("id")
        return [UserAttachmentService._serialize_attachment(record) for record in records]

    @staticmethod
    async def count_by_user_ids(user_ids: list[int]) -> dict[int, int]:
        """批量统计用户附件数量，避免列表查询出现 N+1。"""
        if not user_ids:
            return {}
        rows = await UserAttachment.filter(user_id__in=user_ids).values("user_id")
        counts = {int(user_id): 0 for user_id in user_ids}
        for row in rows:
            user_id = int(row["user_id"])
            counts[user_id] = counts.get(user_id, 0) + 1
        return counts

    @staticmethod
    async def save_attachments(
        *,
        user_id: int,
        userid: str,
        attachments: Sequence[AttachmentItem],
    ) -> list[Path]:
        """将待提交附件保存到用户目录并批量创建记录。"""
        pending_attachments = list(attachments)
        if not pending_attachments:
            return []
        if len(pending_attachments) > USER_ATTACHMENT_MAX_FILES:
            raise ValueError(f"用户附件最多上传 {USER_ATTACHMENT_MAX_FILES} 个")

        target_dir = USER_ATTACHMENT_ROOT / UserAttachmentService._build_account_dir_name(
            user_id=user_id,
            userid=userid,
        )
        await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

        written_paths: list[Path] = []
        records: list[UserAttachment] = []
        try:
            for attachment in pending_attachments:
                original_name, content = UserAttachmentService._validate_attachment(attachment)
                storage_name = UserAttachmentService._build_storage_name(original_name)
                file_path = target_dir / storage_name
                await asyncio.to_thread(file_path.write_bytes, content)
                written_paths.append(file_path)
                records.append(
                    UserAttachment(
                        original_name=original_name,
                        storage_name=storage_name,
                        content_type=str(attachment.content_type or "application/octet-stream")[:128],
                        file_size=len(content),
                        storage_path=file_path.relative_to(PROJECT_ROOT).as_posix(),
                        user_id=int(user_id),
                    )
                )
            await UserAttachment.bulk_create(records)
        except Exception:
            await UserAttachmentService.delete_files(written_paths)
            raise
        return written_paths

    @staticmethod
    async def get_attachment_file(attachment_id: int) -> tuple[UserAttachment, Path] | None:
        """读取附件记录并返回经过目录边界校验的本地路径。"""
        record = await UserAttachment.filter(id=int(attachment_id)).first()
        if record is None:
            return None
        file_path = UserAttachmentService._resolve_storage_path(record.storage_path)
        if file_path is None or not await asyncio.to_thread(file_path.is_file):
            return None
        return record, file_path

    @staticmethod
    async def delete_attachment(*, user_id: int, attachment_id: int) -> tuple[bool, str]:
        """删除指定用户的附件记录和本地文件。"""
        record = await UserAttachment.filter(
            id=int(attachment_id),
            user_id=int(user_id),
        ).first()
        if record is None:
            return False, "附件不存在或已被删除"

        file_path = UserAttachmentService._resolve_storage_path(record.storage_path)
        await record.delete()
        if file_path is not None:
            try:
                await UserAttachmentService.delete_files([file_path])
            except OSError:
                logger.exception(
                    "附件记录已删，本地文件清理失败 attachment_id={} path={}",
                    attachment_id,
                    file_path,
                )
        return True, "附件已删除"

    @staticmethod
    async def delete_files(file_paths: Sequence[Path]) -> None:
        """删除指定本地文件，并清理已经为空的账号目录。"""
        if not file_paths:
            return
        await asyncio.to_thread(UserAttachmentService._delete_files_sync, list(file_paths))

    @staticmethod
    def _validate_attachment(attachment: AttachmentItem) -> tuple[str, bytes]:
        """校验附件内容并返回安全的原文件名。"""
        original_name = Path(str(attachment.file_name or "").replace("\\", "/")).name.strip()
        if not original_name:
            raise ValueError("附件文件名不能为空")
        if len(original_name) > 255:
            raise ValueError(f"附件文件名过长：{original_name[:30]}...")
        if not is_allowed_attachment_name(original_name, DEFAULT_ATTACHMENT_EXTENSIONS):
            raise ValueError(f"{original_name} 的文件格式不支持")

        content = attachment.content
        if not content:
            raise ValueError(f"{original_name} 没有可保存的文件内容")
        if len(content) > USER_ATTACHMENT_MAX_SIZE:
            raise ValueError(f"{original_name} 超过 10.00 MB，无法保存")
        validate_attachment_preview_content(original_name, content)
        return original_name, content

    @staticmethod
    def _build_account_dir_name(*, user_id: int, userid: str) -> str:
        """生成稳定且不可越界的账号目录名。"""
        safe_userid = re.sub(r"[^\w.-]+", "_", str(userid or ""), flags=re.UNICODE).strip("._")
        account_name = safe_userid[:48] or "user"
        return f"{account_name}_{int(user_id)}"

    @staticmethod
    def _build_storage_name(original_name: str) -> str:
        """生成纯 UUID 本地文件名，原始名称仅保存在数据库中。"""
        suffix = Path(original_name).suffix.lower()[:16]
        return f"{uuid.uuid4().hex}{suffix}"

    @staticmethod
    def _serialize_attachment(record: UserAttachment) -> AttachmentItem:
        """将用户附件记录转换为通用展示对象。"""
        attachment_id = int(record.id)
        content_url = f"/sys/user/attachments/{attachment_id}/content"
        return AttachmentItem(
            attachment_id=attachment_id,
            file_name=str(record.original_name or "未命名附件"),
            content_type=str(record.content_type or "application/octet-stream"),
            size=int(record.file_size or 0),
            thumbnail_url=content_url,
            preview_url=content_url,
            download_url=f"{content_url}?download=true",
        )

    @staticmethod
    def _resolve_storage_path(storage_path: str | None) -> Path | None:
        """解析数据库相对路径，并限制文件只能位于用户上传目录。"""
        if not storage_path:
            return None
        upload_root = USER_ATTACHMENT_ROOT.resolve()
        file_path = (PROJECT_ROOT / storage_path).resolve()
        if not file_path.is_relative_to(upload_root):
            return None
        return file_path

    @staticmethod
    def _delete_files_sync(file_paths: list[Path]) -> None:
        """同步删除文件，并清理已经为空的账号目录。"""
        parent_dirs: set[Path] = set()
        for file_path in file_paths:
            parent_dirs.add(file_path.parent)
            file_path.unlink(missing_ok=True)
        for parent_dir in parent_dirs:
            try:
                parent_dir.rmdir()
            except OSError:
                continue
