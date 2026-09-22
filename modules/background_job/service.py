"""系统能力：后台任务执行与进度状态。

按需创建 ``BackgroundJob`` 实例，不要做成进程级单例。
CPU 任务必须使用模块级可 pickle 函数；I/O 任务可在线程池运行。
"""

from __future__ import annotations

import asyncio
import multiprocessing
from collections.abc import Callable, Generator
from queue import Empty, Queue
from typing import Any

from loguru import logger
from nicegui import run

ProgressFunc = Callable[..., Generator[float, None, None]]

_manager: Any = None


def _mp_context() -> multiprocessing.context.BaseContext:
    """与 NiceGUI 进程池保持同一启动方式。"""
    method = run.process_pool_start_method
    if method is None:
        return multiprocessing.get_context()
    return multiprocessing.get_context(method)


def _ensure_manager() -> Any:
    """懒创建进度队列所用的 Manager，仅主进程调用。"""
    global _manager
    if _manager is None:
        _manager = _mp_context().Manager()
    return _manager


def shutdown_background_jobs() -> None:
    """关闭进度 Manager，避免残留子进程。"""
    global _manager
    if _manager is None:
        return
    try:
        _manager.shutdown()
    except Exception:
        logger.exception("关闭后台任务 Manager 失败")
    _manager = None


def _drive_progress(
    func: ProgressFunc,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    queue: Any,
) -> None:
    """在工作线程/进程中驱动进度生成器，并保证写入终止消息。"""
    last = 0.0
    try:
        for raw in func(*args, **kwargs):
            last = max(0.0, min(1.0, float(raw)))
            queue.put({"progress": last})
        queue.put({"progress": 1.0, "done": True})
    except Exception as exc:
        queue.put(
            {
                "progress": last,
                "error": f"{type(exc).__name__}: {exc}",
                "done": True,
            }
        )
        raise


def _queue_get_nowait(queue: Any) -> dict[str, Any] | None:
    """取出一条进度消息；队列为空时返回 None。"""
    try:
        message = queue.get_nowait()
    except Empty:
        return None
    if not isinstance(message, dict):
        return None
    return message


class BackgroundJob:
    """一次可绑定到进度条的后台任务。"""

    def __init__(self) -> None:
        self.progress = 0.0
        self.is_running = False
        self.error: str | None = None
        self.result: Any = None

    async def run_cpu(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在进程池执行 CPU 任务，不推送中间进度。"""
        return await self._run_plain(run.cpu_bound, func, *args, **kwargs)

    async def run_io(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在线程池执行 I/O 任务，不推送中间进度。"""
        return await self._run_plain(run.io_bound, func, *args, **kwargs)

    async def run_cpu_progress(self, func: ProgressFunc, *args: Any, **kwargs: Any) -> None:
        """在进程池执行可 pickle 的进度生成器，yield 0.0~1.0。"""
        await self._run_progress(run.cpu_bound, func, args, kwargs, use_manager=True)

    async def run_io_progress(self, func: ProgressFunc, *args: Any, **kwargs: Any) -> None:
        """在线程池执行进度生成器，yield 0.0~1.0。"""
        await self._run_progress(run.io_bound, func, args, kwargs, use_manager=False)

    def _begin(self) -> None:
        """占用任务槽并清空上次状态。"""
        if self.is_running:
            raise RuntimeError("后台任务正在执行")
        self.is_running = True
        self.progress = 0.0
        self.error = None
        self.result = None

    async def _run_plain(
        self,
        runner: Callable[..., Any],
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """执行无进度任务，仅维护 running / result / error。"""
        self._begin()
        try:
            result = await runner(func, *args, **kwargs)
            self.result = result
            self.progress = 1.0
            return result
        except Exception as exc:
            self.error = str(exc)
            raise
        finally:
            self.is_running = False

    async def _run_progress(
        self,
        runner: Callable[..., Any],
        func: ProgressFunc,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        use_manager: bool,
    ) -> None:
        """执行进度任务：生产者结束即停止消费，避免官方示例在异常时空转。"""
        self._begin()
        queue: Any = _ensure_manager().Queue() if use_manager else Queue()
        producer = asyncio.create_task(runner(_drive_progress, func, args, kwargs, queue))
        try:
            await self._consume(queue, producer)
            try:
                await producer
            except Exception as exc:
                if self.error:
                    raise RuntimeError(self.error) from exc
                raise
            if self.error:
                raise RuntimeError(self.error)
        except Exception as exc:
            if self.error is None:
                self.error = str(exc)
            raise
        finally:
            if self.progress < 1.0 and self.error is None:
                self.progress = 1.0
            self.is_running = False

    async def _consume(self, queue: Any, producer: asyncio.Task) -> None:
        """消费进度队列，生产者结束后排空剩余消息即返回。"""
        while True:
            message = _queue_get_nowait(queue)
            if message is not None:
                self._apply_message(message)
                if message.get("done"):
                    return
                continue
            if producer.done():
                while True:
                    leftover = _queue_get_nowait(queue)
                    if leftover is None:
                        return
                    self._apply_message(leftover)
                    if leftover.get("done"):
                        return
            await asyncio.sleep(0.05)

    def _apply_message(self, message: dict[str, Any]) -> None:
        """把一条队列消息应用到可绑定状态。"""
        if "progress" in message:
            try:
                self.progress = max(0.0, min(1.0, float(message["progress"])))
            except (TypeError, ValueError):
                logger.warning("忽略非法进度值: {}", message.get("progress"))
        error = message.get("error")
        if error:
            self.error = str(error)
