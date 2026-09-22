"""项目部署脚本。

本模块负责在当前项目目录执行部署编排：进入虚拟环境、拉取代码、执行数据库迁移并重启
Supervisor 管理的项目进程。本模块不负责安装系统依赖、创建虚拟环境或修改 Supervisor 配置。

Git 凭据、仓库地址和 Supervisor 进程名从项目根目录 `.env` 读取。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from settings import load_env_file

PROJECT_ROOT = Path(__file__).resolve().parent
load_env_file()


def _env_str(name: str, default: str = "") -> str:
    """读取环境变量；空白值回退到默认值。"""
    return os.getenv(name, default).strip() or default


VENV_DIR = Path(_env_str("DEPLOY_VENV_DIR") or str(PROJECT_ROOT / ".venv")).resolve()
SUPERVISOR_PROGRAM = _env_str("DEPLOY_SUPERVISOR_PROGRAM")
GIT_REPO_URL = _env_str("DEPLOY_GIT_REPO_URL")
GIT_BRANCH = _env_str("DEPLOY_GIT_BRANCH", "main")
DEPLOY_GIT_USERNAME = _env_str("DEPLOY_GIT_USERNAME")
DEPLOY_GIT_PASSWORD = _env_str("DEPLOY_GIT_PASSWORD")


def _build_env() -> dict[str, str]:
    """构建虚拟环境运行变量，不修改当前 Shell 会话。"""
    if not VENV_DIR.exists():
        raise FileNotFoundError(f"虚拟环境不存在：{VENV_DIR}")

    bin_dir = VENV_DIR / "bin"
    if not bin_dir.exists():
        raise FileNotFoundError(f"虚拟环境 bin 目录不存在：{bin_dir}")

    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(VENV_DIR)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run_command(command: list[str], *, env: dict[str, str]) -> None:
    """执行单个部署命令，失败时立即中断后续步骤。"""
    command_text = " ".join(_mask_command_sensitive_parts(command))
    print(f"\n==> {command_text}")
    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def _mask_command_sensitive_parts(command: list[str]) -> list[str]:
    """隐藏命令中的认证信息，不改变实际执行参数。"""
    return [part.replace(DEPLOY_GIT_PASSWORD, "***") if DEPLOY_GIT_PASSWORD else part for part in command]


def _build_git_remote_url() -> str:
    """构建 Git 远端地址，支持内嵌 HTTPS 认证信息。"""
    if not GIT_REPO_URL:
        raise ValueError("仓库地址不能为空，请设置 DEPLOY_GIT_REPO_URL")
    if not DEPLOY_GIT_USERNAME or not DEPLOY_GIT_PASSWORD:
        return GIT_REPO_URL
    if not GIT_REPO_URL.startswith("https://"):
        return GIT_REPO_URL

    encoded_username = quote(DEPLOY_GIT_USERNAME, safe="")
    encoded_password = quote(DEPLOY_GIT_PASSWORD, safe="")
    return GIT_REPO_URL.replace("https://", f"https://{encoded_username}:{encoded_password}@", 1)


def _ensure_git_write_permissions() -> None:
    """校验 Git 目录写权限，不负责修改线上文件属主或权限。"""
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        return
    if not os.access(git_dir, os.W_OK):
        raise PermissionError(
            f"当前用户对 Git 目录无写权限：{git_dir}，请修正仓库属主或改用仓库属主执行部署"
        )


def _ensure_git_safe_directory(env: dict[str, str]) -> None:
    """将项目目录加入 Git 安全目录，避免部署用户与仓库属主不一致时报错。"""
    _run_command(
        ["git", "config", "--global", "--add", "safe.directory", str(PROJECT_ROOT)],
        env=env,
    )


def _has_local_git_changes(env: dict[str, str]) -> bool:
    """检查工作区和暂存区是否存在会影响同步的本地改动。"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return bool(result.stdout.strip())


def _stash_local_git_changes(env: dict[str, str]) -> None:
    """同步前暂存本地改动，避免部署拉取被未提交文件阻断。"""
    if not _has_local_git_changes(env):
        return

    _run_command(
        [
            "git",
            "stash",
            "push",
            "--include-untracked",
            "--message",
            "deploy-auto-stash-before-sync",
        ],
        env=env,
    )


def _sync_gitee_repository(env: dict[str, str]) -> None:
    """从远端同步项目代码，保留本地改动到 stash 后再拉取。"""
    if not GIT_BRANCH:
        raise ValueError("Git 分支不能为空，请设置 DEPLOY_GIT_BRANCH")

    remote_url = _build_git_remote_url()
    git_dir = PROJECT_ROOT / ".git"
    _ensure_git_write_permissions()
    _ensure_git_safe_directory(env)
    if not git_dir.exists():
        _run_command(["git", "init"], env=env)
        _run_command(["git", "remote", "add", "origin", remote_url], env=env)
        _run_command(["git", "fetch", "origin", GIT_BRANCH], env=env)
        _run_command(["git", "checkout", "-B", GIT_BRANCH, f"origin/{GIT_BRANCH}"], env=env)
        return

    _stash_local_git_changes(env)
    _run_command(["git", "fetch", remote_url, GIT_BRANCH], env=env)
    _run_command(["git", "checkout", GIT_BRANCH], env=env)
    _run_command(["git", "pull", "--ff-only", remote_url, GIT_BRANCH], env=env)


def deploy() -> None:
    """按固定顺序执行部署流程，不处理远程 SSH 登录。"""
    if not SUPERVISOR_PROGRAM:
        raise ValueError("Supervisor 进程名不能为空，请设置 DEPLOY_SUPERVISOR_PROGRAM")

    env = _build_env()
    tortoise_bin = VENV_DIR / "bin" / "tortoise"
    if not tortoise_bin.exists():
        raise FileNotFoundError(f"tortoise 命令不存在：{tortoise_bin}")

    print(f"项目目录：{PROJECT_ROOT}")
    print(f"虚拟环境：{VENV_DIR}")
    print(f"Git 仓库：{GIT_REPO_URL}")
    print(f"Git 分支：{GIT_BRANCH}")
    print(f"Supervisor 进程：{SUPERVISOR_PROGRAM}")

    _sync_gitee_repository(env)
    _run_command([str(tortoise_bin), "makemigrations"], env=env)
    _run_command([str(tortoise_bin), "migrate"], env=env)
    _run_command(["sudo", "supervisorctl", "restart", SUPERVISOR_PROGRAM], env=env)

    print("\n==> 部署完成")


def main() -> int:
    """命令行入口，返回标准进程退出码。"""
    try:
        deploy()
    except (FileNotFoundError, PermissionError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"\n部署失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
