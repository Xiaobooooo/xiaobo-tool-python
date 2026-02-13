import asyncio
import inspect
import os
import random
import threading
import time
import traceback
from abc import ABC, abstractmethod
from asyncio import Task
from concurrent import futures
from concurrent.futures import Future
from typing import Optional, Callable, Any, List, Union, Type, Awaitable

from loguru import logger
from tenacity import retry_if_not_exception_type, stop_after_attempt, wait_fixed, retry

from xiaobo_tool import utils
from xiaobo_tool.task_executor.models import Target
from xiaobo_tool.task_executor.exceptions import TaskFailed
from xiaobo_tool.task_executor.manager import BaseTaskManager, TaskManager, AsyncTaskManager
from xiaobo_tool.proxy_pool import ProxyPool
from xiaobo_tool.task_executor.settings import Settings


class BaseTaskExecutor(ABC):

    def __init__(
            self,
            task_manager_cls: Type[BaseTaskManager],
            name: str = "TaskExecutor",
            settings: Optional[Settings] = None,
            **kwargs,
    ):
        """
        初始化任务执行器基类。可传入 Settings 对象，也可通过 kwargs 构建。

        :param task_manager_cls: 任务管理器类，TaskManager 或 AsyncTaskManager。
        :param name: 执行器名称，用于日志标识和 Settings 中的 task_name。
        :param settings: 配置对象，为 None 时自动从环境变量/.env/kwargs 构建。
        :param kwargs: 传递给 Settings 构造函数的额外参数，仅在 settings 为 None 时生效。
        """
        if settings is None:
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            settings = Settings(task_name=name, **filtered_kwargs)

        self.logger = logger.bind(name=name)
        self.settings = settings
        self._manager = task_manager_cls(self.settings.max_workers)

        self._proxy_pool = ProxyPool(
            self.settings.proxy,
            self.settings.proxy_ipv6,
            self.settings.proxy_api,
            self.settings.proxy_ipv6_api,
            self.settings.use_proxy_ipv6,
            self.settings.disable_proxy
        )

        self._log_settings()

        self._stats = {"success": 0, "pending": 0, "error": 0, "cancel": 0}
        self._errors: List[str] = []

    def _log_settings(self):
        """逐行记录当前配置信息。"""
        self.logger.info("--- 任务配置 ---")
        for field_name, field_info in self.settings.model_fields.items():
            if not field_info.description:
                continue
            description = field_info.description
            value = getattr(self.settings, field_name)

            if value is None:
                value_str = "未设置"
            elif isinstance(value, bool):
                value_str = "是" if value else "否"
            else:
                value_str = str(value)

            self.logger.info(f"{description}: {value_str}")

        self.logger.info("--- 任务配置 ---")

    def submit_tasks(
            self,
            task_func: Callable[..., Any],
            source: Union[int, List[Any]],
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            on_complete: Optional[Callable[[Target], None]] = None,
    ):
        """
        批量提交任务。source 为 int 时提交指定数量，为 list 时逐元素提交。

        :param task_func: 任务函数，接收 Target 参数。
        :param source: 任务数据源，int 表示数量，list 表示数据列表。
        :param on_success: 任务成功回调，接收 (Target, result)。
        :param on_error: 任务失败回调（重试耗尽后），接收 (Target, Exception)。
        :param on_cancel: 任务取消回调，接收 (Target,)。
        :param on_complete: 任务结束回调，无论成功/失败/取消都会执行，接收 (Target,)。
        """
        if isinstance(source, int):
            items = range(source)
        elif isinstance(source, list):
            items = source[:]
            if self.settings.shuffle:
                random.shuffle(items)
        else:
            raise TypeError("'source' 必须是 int 或 list 类型。")

        if not items:
            self.logger.warning("任务数量必须大于 0。")
            return

        self.logger.info(f"本次提交 {len(items)} 个任务")

        for index, item in enumerate(items):
            task_name = f"{index + 1:05d}"
            task_logger = self.logger.bind(name=task_name)

            data_preview = str(item[0]) if isinstance(item, (list, tuple)) else item

            target = Target(index=index, data=item, data_preview=data_preview, logger=task_logger)

            self.submit_task(
                task_func=task_func,
                target=target,
                on_success=on_success,
                on_error=on_error,
                on_cancel=on_cancel,
                on_complete=on_complete,
            )

    def submit_tasks_from_file(
            self,
            task_func: Callable[..., Any],
            filename: str,
            separator: str = '----',
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            on_complete: Optional[Callable[[Target], None]] = None,
    ):
        """
        从 txt 文件读取数据并批量提交任务，每行按 separator 分割为列表元素。

        :param task_func: 任务函数，接收 Target 参数。
        :param filename: 文件名，自动补全 .txt 后缀。
        :param separator: 每行数据的分隔符。
        :param on_success: 任务成功回调，接收 (Target, result)。
        :param on_error: 任务失败回调（重试耗尽后），接收 (Target, Exception)。
        :param on_cancel: 任务取消回调，接收 (Target,)。
        :param on_complete: 任务结束回调，无论成功/失败/取消都会执行，接收 (Target,)。
        """
        try:
            lines = utils.read_txt_file_lines(filename)
            source_list = [line.split(separator) for line in lines]
        except (FileNotFoundError, IOError) as e:
            self.logger.error(f"文件 '{filename}' 解析失败: {e}")
            return

        self.submit_tasks(
            task_func=task_func,
            source=source_list,
            on_success=on_success,
            on_error=on_error,
            on_cancel=on_cancel,
            on_complete=on_complete,
        )

    @abstractmethod
    def _increment_stat(self, key: str):
        ...

    @abstractmethod
    def _get_stat(self, key: str) -> int:
        """
        获取指定统计项的值。

        :param key: 统计项名称，如 'success'、'error'、'cancel'。
        :return: 该统计项的当前数值。
        """
        ...

    @abstractmethod
    def get_success_count(self) -> int:
        """
        获取成功任务数。

        :return: 成功任务数量。
        """
        ...

    @abstractmethod
    def get_error_count(self) -> int:
        """
        获取失败任务数。

        :return: 失败任务数量。
        """
        ...

    @abstractmethod
    def get_cancel_count(self) -> int:
        """
        获取取消任务数。

        :return: 取消任务数量。
        """
        ...

    @abstractmethod
    def statistics(self):
        ...

    @abstractmethod
    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            on_complete: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ) -> Future | Task:
        """
        提交单个任务。

        :param task_func: 任务函数，接收 Target 参数。
        :param target: 任务目标对象，包含数据、日志器等信息。
        :param on_success: 任务成功回调，接收 (Target, result)。
        :param on_error: 任务失败回调（重试耗尽后），接收 (Target, Exception)。
        :param on_cancel: 任务取消回调，接收 (Target,)。
        :param on_complete: 任务结束回调，无论成功/失败/取消都会执行，接收 (Target,)。
        :param retries: 覆盖 Settings 中的重试次数。
        :param retry_delay: 覆盖 Settings 中的重试延迟（秒）。
        :return: 同步执行器返回 Future，异步执行器返回 asyncio.Task。
        """
        ...

    @abstractmethod
    def wait(self):
        ...

    @abstractmethod
    def shutdown(self):
        ...


class TaskExecutor(BaseTaskExecutor):

    def __init__(self, name: str = "TaskExecutor", settings: Optional[Settings] = None, **kwargs):
        """
        同步任务执行器，基于线程池。

        :param name: 执行器名称，用于日志标识。
        :param settings: 配置对象，为 None 时自动从环境变量/.env/kwargs 构建。
        :param kwargs: 传递给 Settings 构造函数的额外参数。
        """
        super().__init__(TaskManager, name, settings, **kwargs)
        self._stats_lock = threading.Lock()

    def _increment_stat(self, key: str):
        with self._stats_lock:
            self._stats[key] += 1

    def _get_stat(self, key: str) -> int:
        with self._stats_lock:
            return self._stats.get(key, 0)

    def get_success_count(self) -> int:
        return self._get_stat('success')

    def get_error_count(self) -> int:
        return self._get_stat('error')

    def get_cancel_count(self) -> int:
        return self._get_stat('cancel')

    def statistics(self):
        with self._stats_lock:
            self.logger.opt(colors=True).info(
                "成功: {}   取消: {}   失败: {}\n<red>{}</red>",
                self._stats["success"], self._stats["cancel"], self._stats["error"], '\n'.join(self._errors)
            )

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            on_complete: Optional[Callable[[Target], None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """包装任务函数（添加重试、代理刷新），提交到线程池执行。"""

        def on_task_success(t: Target, result: Any):
            self._increment_stat("success")
            t.logger.success(f"✅ [{target.data_preview}]任务执行成功")
            if on_success:
                on_success(t, result)

        def on_task_cancel(t: Target):
            self._increment_stat("cancel")
            t.logger.warning(f"⏹️ [{target.data_preview}]任务取消")
            if on_cancel:
                on_cancel(t)

        def on_task_error(t: Target, error: Exception):
            if isinstance(error, futures.CancelledError):
                on_task_cancel(t)
                return
            self._increment_stat("error")

            error_text = f"{error.__class__.__name__}: {error}"
            try:
                tb = error.__traceback__
                last_frame = traceback.extract_tb(tb)[-1]
                filename = os.path.basename(last_frame.filename)
                lineno = last_frame.lineno
                error_text = f'[{filename}:{lineno}] {error_text}'
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")
            except Exception:
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")

            error_text = f"{target.data_preview}: {error_text}"
            with self._stats_lock:
                self._errors.append(error_text)

            if on_error:
                on_error(t, error)

        def _refresh_proxy(replacement: Optional[str] = None, use_proxy_ipv6: Optional[bool] = None):
            replacement_text = (replacement if replacement is not None else f'{target.data_preview}({time.time()})')
            proxy = self._proxy_pool.get_proxy(replacement=replacement_text, _use_proxy_ipv6=use_proxy_ipv6)
            target.proxy = proxy
            return proxy

        target.refresh_proxy = _refresh_proxy

        effective_retries = retries if retries is not None else self.settings.retries
        effective_retry_delay = retry_delay if retry_delay is not None else self.settings.retry_delay

        # --- 将所有执行逻辑包装到一个函数中 ---
        def _wrapped_task_executor():
            attempt_counter = {"n": 0}  # tenacity 不直接提供 attempt 编号，使用闭包计数

            def log_before_retry(retry_state):
                if target and target.logger:
                    exc = retry_state.outcome.exception()
                    target.logger.warning(
                        f"🔄 [{target.data_preview}]任务执行失败，将在 {retry_state.next_action.sleep:.2f} 秒后进行第 {retry_state.attempt_number} 次重试... "
                        f"异常: {repr(exc)}"
                    )

            @retry(
                retry=retry_if_not_exception_type(TaskFailed),
                stop=stop_after_attempt(effective_retries + 1),
                wait=wait_fixed(effective_retry_delay) if effective_retry_delay > 0 else None,
                before_sleep=log_before_retry,
                reraise=True
            )
            def task_to_run():
                attempt_counter["n"] += 1
                if target and target.logger:
                    target.logger.info(f"🚀 [{target.data_preview}]第 {attempt_counter['n']} 次运行")
                # 每次重试提供新的代理
                _refresh_proxy(replacement=f'{target.data_preview}({attempt_counter["n"]})')
                return task_func(target)

            return task_to_run()

        # --- 包装结束 ---
        self._manager.submit_task(
            task_func=_wrapped_task_executor,
            target=target,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
            on_complete=on_complete,
        )

    def wait(self, wait_callbacks: bool = True):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""
        try:
            self._manager.wait(wait_callbacks)
        except (KeyboardInterrupt, futures.CancelledError):
            self.logger.warning("用户中断，取消未开始的任务，等待运行中的任务...")
            try:
                self.shutdown(False, True)
                self._manager.wait(wait_callbacks)
            except (KeyboardInterrupt, futures.CancelledError):
                self.logger.error("用户强制中断，程序退出！")
                os._exit(0)

    def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        self._manager.shutdown(wait, cancel_tasks, wait_callbacks)

    def __enter__(self) -> 'TaskExecutor':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(True, True)


class AsyncTaskExecutor(BaseTaskExecutor):

    def __init__(self, name: str = "AsyncTaskExecutor", settings: Optional[Settings] = None, **kwargs):
        """
        异步任务执行器，基于 asyncio 信号量控制并发。

        :param name: 执行器名称，用于日志标识。
        :param settings: 配置对象，为 None 时自动从环境变量/.env/kwargs 构建。
        :param kwargs: 传递给 Settings 构造函数的额外参数。
        """
        super().__init__(AsyncTaskManager, name, settings, **kwargs)
        self._stats_lock = asyncio.Lock()

    async def _increment_stat(self, key: str):
        async with self._stats_lock:
            self._stats[key] += 1

    async def _get_stat(self, key: str) -> int:
        async with self._stats_lock:
            return self._stats.get(key, 0)

    async def get_success_count(self) -> int:
        return await self._get_stat('success')

    async def get_error_count(self) -> int:
        return await self._get_stat('error')

    async def get_cancel_count(self) -> int:
        return await self._get_stat('cancel')

    async def statistics(self):
        async with self._stats_lock:
            self.logger.opt(colors=True).info(
                "成功: {}   取消: {}   失败: {}\n<red>{}</red>",
                self._stats["success"], self._stats["cancel"], self._stats["error"], '\n'.join(self._errors)
            )

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], Awaitable | None]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable | None]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable | None]] = None,
            on_complete: Optional[Callable[[Target], Awaitable | None]] = None,
            retries: Optional[int] = None,
            retry_delay: Optional[float] = None,
    ):
        """包装异步任务函数（添加重试、代理刷新），提交到事件循环执行。"""

        async def _run_callback(cb: Callable[..., Any], *args):
            result = cb(*args)
            if inspect.isawaitable(result):
                await result

        async def on_task_success(t: Target, result: Any):
            await self._increment_stat("success")
            t.logger.success(f"✅ [{target.data_preview}]任务执行成功")
            if on_success:
                await _run_callback(on_success, t, result)

        async def on_task_cancel(t: Target):
            await self._increment_stat("cancel")
            t.logger.warning(f"⏹️ [{target.data_preview}]任务取消")
            if on_cancel:
                await _run_callback(on_cancel, t)

        async def on_task_error(t: Target, error: Exception):
            if isinstance(error, asyncio.CancelledError):
                await on_task_cancel(t)
                return
            await self._increment_stat("error")

            error_text = f"{error.__class__.__name__}: {error}"
            try:
                tb = error.__traceback__
                last_frame = traceback.extract_tb(tb)[-1]
                filename = os.path.basename(last_frame.filename)
                lineno = last_frame.lineno
                error_text = f'[{filename}:{lineno}] {error_text}'
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")
            except Exception:
                t.logger.error(f"❌ [{target.data_preview}]任务执行失败 -> {error_text}")

            error_text = f"{target.data_preview}: {error_text}"
            async with self._stats_lock:
                self._errors.append(error_text)

            if on_error:
                await _run_callback(on_error, t, error)

        def _refresh_proxy(replacement: Optional[str] = None, use_proxy_ipv6: Optional[bool] = None):
            replacement_text = (replacement if replacement is not None else f'{target.data_preview}({time.time()})')
            proxy = self._proxy_pool.get_proxy(replacement=replacement_text, _use_proxy_ipv6=use_proxy_ipv6)
            target.proxy = proxy
            return proxy

        target.refresh_proxy = _refresh_proxy

        effective_retries = retries if retries is not None else self.settings.retries
        effective_retry_delay = retry_delay if retry_delay is not None else self.settings.retry_delay

        # --- 将所有执行逻辑包装到一个函数中 ---
        async def _wrapped_task_executor():
            asyncio.current_task().started = True
            attempt_counter = {"n": 0}  # tenacity 不直接提供 attempt 编号，使用闭包计数

            def log_before_retry(retry_state):
                if target and target.logger:
                    exc = retry_state.outcome.exception()
                    target.logger.warning(
                        f"🔄 [{target.data_preview}]任务执行失败，将在 {retry_state.next_action.sleep:.2f} 秒后进行第 {retry_state.attempt_number} 次重试... "
                        f"异常: {repr(exc)}"
                    )

            @retry(
                retry=retry_if_not_exception_type(TaskFailed),
                stop=stop_after_attempt(effective_retries + 1),
                wait=wait_fixed(effective_retry_delay) if effective_retry_delay > 0 else None,
                before_sleep=log_before_retry,
                reraise=True
            )
            async def task_to_run():
                attempt_counter["n"] += 1
                if target and target.logger:
                    target.logger.info(f"🚀 [{target.data_preview}]第 {attempt_counter['n']} 次运行")
                # 每次重试提供新的代理
                _refresh_proxy(replacement=f'{target.data_preview}({attempt_counter["n"]})')
                return await task_func(target)

            return await task_to_run()

        # --- 包装结束 ---
        self._manager.submit_task(
            task_func=_wrapped_task_executor,
            target=target,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
            on_complete=on_complete,
        )

    def submit_tasks(
            self,
            task_func: Callable[..., Any],
            source: Union[int, List[Any]],
            on_success: Optional[Callable[[Target, Any], Awaitable | None]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable | None]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable | None]] = None,
            on_complete: Optional[Callable[[Target], Awaitable | None]] = None,
    ):
        super().submit_tasks(
            task_func=task_func,
            source=source,
            on_success=on_success,
            on_error=on_error,
            on_cancel=on_cancel,
            on_complete=on_complete,
        )

    def submit_tasks_from_file(
            self,
            task_func: Callable[..., Any],
            filename: str,
            separator: str = '----',
            on_success: Optional[Callable[[Target, Any], Awaitable | None]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable | None]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable | None]] = None,
            on_complete: Optional[Callable[[Target], Awaitable | None]] = None,
    ):
        super().submit_tasks_from_file(
            task_func=task_func,
            filename=filename,
            separator=separator,
            on_success=on_success,
            on_error=on_error,
            on_cancel=on_cancel,
            on_complete=on_complete,
        )

    async def wait(self, wait_callbacks: bool = True):
        """等待已提交的任务完成，支持捕获 Ctrl+C 中断。"""
        try:
            await self._manager.wait(wait_callbacks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.warning("用户中断，取消未开始的任务，等待运行中的任务...")
            try:
                await self.shutdown(False, True)
                await self._manager.wait(wait_callbacks)
            except (KeyboardInterrupt, asyncio.CancelledError):
                self.logger.error("用户强制中断，程序退出！")
                os._exit(0)

    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        await self._manager.shutdown(wait, cancel_tasks, wait_callbacks)

    async def __aenter__(self) -> 'AsyncTaskExecutor':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown(True, True)
