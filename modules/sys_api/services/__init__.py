"""业务域：开放 API 客户端、令牌与请求日志。

只再导出。用例文件彼此不引用。令牌与日志查询共用 ``client_lookup``；签发与刷新共用 ``token_codec``。
"""

from .authenticate_client import authenticate_client
from .create_client import create_client
from .create_log import create_log
from .get_active_client_by_client_id import get_active_client_by_client_id
from .get_client_detail import get_client_detail
from .get_log_detail import get_log_detail
from .issue_tokens_for_client import issue_tokens_for_client
from .rotate_refresh_token import rotate_refresh_token
from .search_clients import search_clients
from .search_logs import search_logs
from .search_tokens import search_tokens
from .token_codec import decode_token, ensure_ip_allowed
from .update_client import update_client

__all__ = [
    "authenticate_client",             # 校验客户端账号密码
    "create_client",                   # 创建 API 客户端
    "create_log",                      # 写入请求日志
    "decode_token",                    # 校验并解码指定类型的 JWT
    "ensure_ip_allowed",               # 拒绝不在白名单内的请求 IP
    "get_active_client_by_client_id",  # 按标识读取启用客户端
    "get_client_detail",               # 读取客户端详情
    "get_log_detail",                  # 读取请求日志详情
    "issue_tokens_for_client",         # 签发访问令牌和刷新令牌
    "rotate_refresh_token",            # 轮换刷新令牌
    "search_clients",                  # 分页查询客户端
    "search_logs",                     # 分页查询请求日志
    "search_tokens",                   # 分页查询令牌
    "update_client",                   # 更新 API 客户端
]
