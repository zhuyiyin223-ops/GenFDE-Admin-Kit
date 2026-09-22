"""本地远程部署入口。

通过 SSH 登录生产服务器，进入项目目录并执行服务器上的 deploy.py。
本脚本只负责远程调用，不在本地执行部署逻辑。

SSH 主机、账号、私钥和远程项目路径从项目根目录 `.env` 读取，命令行参数可覆盖。
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from settings import load_env_file

PROJECT_ROOT = Path(__file__).resolve().parent
load_env_file()

DEFAULT_PORT = 22
DEFAULT_REMOTE_PYTHON = ".venv/bin/python"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 15


def _env_str(name: str, default: str = "") -> str:
    """读取环境变量；空白值回退到默认值。"""
    return os.getenv(name, default).strip() or default


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量；未设置时使用默认值。"""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数，当前值为：{raw}") from exc


def _resolve_private_key_path(private_key: Path) -> Path:
    """将私钥路径解析为绝对路径，相对路径以项目根目录为基准。"""
    path = private_key.expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _env_path(name: str) -> Path | None:
    """读取路径环境变量；未设置时返回 None。"""
    raw = _env_str(name)
    if not raw:
        return None
    return _resolve_private_key_path(Path(raw))


def _ensure_private_key_permissions(private_key_path: Path) -> None:
    """收紧私钥权限，避免 OpenSSH 拒绝使用过于开放的密钥文件。"""
    current_mode = private_key_path.stat().st_mode & 0o777
    if current_mode & 0o077:
        os.chmod(private_key_path, 0o600)


def build_remote_command(remote_project_path: str, remote_python: str) -> str:
    """构建服务器上进入项目目录并执行 deploy.py 的命令。"""
    project_path = remote_project_path.strip()
    python_path = remote_python.strip()
    if not project_path:
        raise ValueError("远程项目目录不能为空，请设置 DEPLOY_REMOTE_PROJECT_PATH 或传入 --remote-project-path")
    if not python_path:
        raise ValueError("远程 Python 路径不能为空，请设置 DEPLOY_REMOTE_PYTHON 或传入 --remote-python")

    return f"cd {shlex.quote(project_path)} && {shlex.quote(python_path)} -u deploy.py"


def build_ssh_command(
    *,
    host: str,
    username: str,
    port: int,
    private_key_path: Path,
    remote_command: str,
    connect_timeout_seconds: int,
    accept_new_host_key: bool,
) -> list[str]:
    """构建本地 SSH 调用参数。"""
    if not host.strip():
        raise ValueError("服务器地址不能为空，请设置 DEPLOY_SSH_HOST 或传入 --host")
    if not username.strip():
        raise ValueError("SSH 用户名不能为空，请设置 DEPLOY_SSH_USERNAME 或传入 --username")
    if port <= 0:
        raise ValueError("SSH 端口必须为正整数")
    if connect_timeout_seconds <= 0:
        raise ValueError("SSH 连接超时必须为正整数")

    host_key_policy = "accept-new" if accept_new_host_key else "yes"
    return [
        "ssh",
        "-i",
        str(private_key_path),
        "-p",
        str(port),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"ConnectTimeout={connect_timeout_seconds}",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=10",
        "-o",
        f"StrictHostKeyChecking={host_key_policy}",
        f"{username.strip()}@{host.strip()}",
        remote_command,
    ]


def remote_deploy(
    *,
    host: str,
    username: str,
    port: int,
    private_key_path: Path,
    remote_project_path: str,
    remote_python: str,
    connect_timeout_seconds: int,
    accept_new_host_key: bool,
) -> int:
    """连接服务器并执行远程部署，返回远程进程退出码。"""
    if not private_key_path.is_file():
        raise FileNotFoundError(
            f"SSH 私钥不存在：{private_key_path}，请设置 DEPLOY_SSH_PRIVATE_KEY 或传入 --private-key"
        )

    _ensure_private_key_permissions(private_key_path)
    remote_command = build_remote_command(remote_project_path, remote_python)
    ssh_command = build_ssh_command(
        host=host,
        username=username,
        port=port,
        private_key_path=private_key_path,
        remote_command=remote_command,
        connect_timeout_seconds=connect_timeout_seconds,
        accept_new_host_key=accept_new_host_key,
    )

    print(f"服务器：{username}@{host}:{port}")
    print(f"私钥：{private_key_path}")
    print(f"远程命令：{remote_command}")
    print()

    completed = subprocess.run(ssh_command, check=False)
    if completed.returncode != 0:
        print(f"\n远程部署失败，退出码 {completed.returncode}", file=sys.stderr)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="通过 SSH 在生产服务器执行 deploy.py")
    parser.add_argument("--host", default=_env_str("DEPLOY_SSH_HOST"), help="生产服务器地址")
    parser.add_argument("--username", default=_env_str("DEPLOY_SSH_USERNAME"), help="SSH 用户名")
    parser.add_argument("--port", type=int, default=_env_int("DEPLOY_SSH_PORT", DEFAULT_PORT), help="SSH 端口")
    parser.add_argument(
        "--private-key",
        type=Path,
        default=_env_path("DEPLOY_SSH_PRIVATE_KEY"),
        help="SSH 私钥路径",
    )
    parser.add_argument(
        "--remote-project-path",
        default=_env_str("DEPLOY_REMOTE_PROJECT_PATH"),
        help="生产服务器项目目录",
    )
    parser.add_argument(
        "--remote-python",
        default=_env_str("DEPLOY_REMOTE_PYTHON", DEFAULT_REMOTE_PYTHON),
        help="生产服务器 Python 路径，相对项目目录或绝对路径均可",
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        default=_env_int("DEPLOY_SSH_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT_SECONDS),
        help="SSH 连接超时秒数",
    )
    parser.add_argument(
        "--accept-new-host-key",
        action="store_true",
        help="首次连接时接受服务器 SSH 主机密钥",
    )
    return parser


def main() -> int:
    """命令行入口，返回标准进程退出码。"""
    try:
        args = build_parser().parse_args()
        private_key = args.private_key
        if private_key is None:
            raise ValueError("SSH 私钥不能为空，请设置 DEPLOY_SSH_PRIVATE_KEY 或传入 --private-key")
        return remote_deploy(
            host=args.host,
            username=args.username,
            port=args.port,
            private_key_path=_resolve_private_key_path(private_key),
            remote_project_path=args.remote_project_path,
            remote_python=args.remote_python,
            connect_timeout_seconds=args.connect_timeout,
            accept_new_host_key=args.accept_new_host_key,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"远程部署失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
