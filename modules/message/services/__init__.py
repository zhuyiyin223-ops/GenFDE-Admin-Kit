"""系统能力：站内消息读写与在线推送。

只再导出。用例文件彼此不引用。业务域只通过本包函数发给指定用户，不要直接使用事件总线。
"""

from .get_unread_count import get_unread_count
from .get_unread_messages import get_unread_messages
from .get_user_messages import get_user_messages
from .mark_all_read import mark_all_read
from .mark_as_read import mark_as_read
from .send_message_to_user import send_message_to_user
from .send_message_to_users import send_message_to_users
from .subscribe import subscribe
from .unsubscribe import unsubscribe

__all__ = [
    "get_unread_count",       # 统计未读数量
    "get_unread_messages",    # 查询未读消息
    "get_user_messages",      # 查询用户消息
    "mark_all_read",          # 标记全部未读消息已读
    "mark_as_read",           # 标记单条消息已读
    "send_message_to_user",   # 给指定用户发送消息
    "send_message_to_users",  # 给多名用户发送同一条消息
    "subscribe",              # 订阅指定用户的站内消息事件
    "unsubscribe",            # 取消站内消息订阅
]
