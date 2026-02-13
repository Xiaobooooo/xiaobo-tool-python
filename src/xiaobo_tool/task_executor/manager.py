import asyncio
import inspect
from abc import abstractmethod, ABC
from asyncio import Task
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor, Future, CancelledError
from typing import Callable, Any, Optional, Awaitable, overload

from loguru import logger

from xiaobo_tool.task_executor.models import Target


class BaseTaskManager(ABC):
    def __init__(self, max_workers: Optional[int] = None):
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers 必须为正整数或 None。")
        self._tasks = set()
        self._callbacks = set()

    @abstractmethod
    def submit_task(self, task_func, target=None, on_success=None, on_error=None, on_cancel=None, on_complete=None): ...

    @overload
    @abstractmethod
    def wait(self, wait_callbacks: bool = True): ...

    @overload
    @abstractmethod
    async def wait(self, wait_callbacks: bool = True): ...

    @abstractmethod
    def wait_callbacks(self): ...

    @overload
    @abstractmethod
    def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True): ...

    @overload
    @abstractmethod
    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True): ...


class TaskManager(BaseTaskManager):
    """通用同步任务池管理器"""

    def __init__(self, max_workers: Optional[int] = None):
        super().__init__(max_workers)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], None]] = None,
            on_error: Optional[Callable[[Target, Exception], None]] = None,
            on_cancel: Optional[Callable[[Target], None]] = None,
            on_complete: Optional[Callable[[Target], None]] = None,
    ) -> Future:
        """提交任务到线程池执行，完成后触发对应回调。"""

        def _trace_and_run_callback(callback: Callable[..., None], *args):
            callback_future = Future()
            self._callbacks.add(callback_future)
            try:
                callback(*args)
                callback_future.set_result(True)
            except Exception as e:
                logger.error(f"回调函数执行异常: {e.__class__.__name__}: {e}")
                if not callback_future.done():
                    callback_future.set_exception(e)
            finally:
                self._callbacks.discard(callback_future)

        def _task_done_callback(_future: Future):
            try:
                result = _future.result()
                if on_success:
                    _trace_and_run_callback(on_success, target, result)
            except CancelledError:
                if on_cancel:
                    _trace_and_run_callback(on_cancel, target)
            except Exception as e:
                if on_error:
                    _trace_and_run_callback(on_error, target, e)
            finally:
                if on_complete:
                    _trace_and_run_callback(on_complete, target)

        future = self.executor.submit(task_func)
        future.add_done_callback(lambda f: _task_done_callback(f))
        future.add_done_callback(lambda t: self._tasks.discard(t))
        self._tasks.add(future)
        return future

    def wait(self, wait_callbacks: bool = True):
        """等待所有已提交的任务完成。"""
        pending = set(self._tasks)
        while pending:
            done, pending = futures.wait(pending, timeout=0.05, return_when=futures.FIRST_COMPLETED)

        if wait_callbacks:
            self.wait_callbacks()

    def wait_callbacks(self):
        """等待所有回调函数执行完毕。"""
        pending = set(self._callbacks)
        while pending:
            done, pending = futures.wait(pending, timeout=0.05, return_when=futures.FIRST_COMPLETED)

    def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        """关闭任务池"""
        self.executor.shutdown(wait, cancel_futures=cancel_tasks)
        if wait:
            self.wait(wait_callbacks)
        elif wait_callbacks:
            self.wait_callbacks()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(False, True)


class AsyncTaskManager(BaseTaskManager):
    """通用异步任务池管理器"""

    def __init__(self, max_workers: Optional[int] = None):
        super().__init__(max_workers)
        self.sem = asyncio.Semaphore(max_workers) if max_workers else None

    def submit_task(
            self,
            task_func: Callable[..., Any],
            target: Optional[Target] = None,
            on_success: Optional[Callable[[Target, Any], Awaitable | None]] = None,
            on_error: Optional[Callable[[Target, Exception], Awaitable | None]] = None,
            on_cancel: Optional[Callable[[Target], Awaitable | None]] = None,
            on_complete: Optional[Callable[[Target], Awaitable | None]] = None,
    ) -> Task:
        """提交异步任务到事件循环执行，完成后触发对应回调。"""

        async def _run_with_semaphore():
            current = asyncio.current_task()
            if self.sem:
                async with self.sem:
                    current.started = True
                    return await task_func()
            current.started = True
            return await task_func()

        async def _trace_and_run_callback(callback: Callable[..., Awaitable | None], *args):
            callback_future = asyncio.wrap_future(Future())
            self._callbacks.add(callback_future)
            try:
                callback_result = callback(*args)
                if inspect.isawaitable(callback_result):
                    await callback_result
                callback_future.set_result(True)
            except Exception as e:
                logger.error(f"回调函数执行异常: {e.__class__.__name__}: {e}")
                if not callback_future.done():
                    callback_future.set_exception(e)
            finally:
                self._callbacks.discard(callback_future)

        async def _task_done_callback(_task: Task):
            try:
                result = _task.result()
                if on_success:
                    await _trace_and_run_callback(on_success, target, result)
            except asyncio.CancelledError:
                if on_cancel:
                    await _trace_and_run_callback(on_cancel, target)
            except Exception as e:
                if on_error:
                    await _trace_and_run_callback(on_error, target, e)
            finally:
                if on_complete:
                    await _trace_and_run_callback(on_complete, target)

        task = asyncio.create_task(_run_with_semaphore())
        task.started = False
        task.add_done_callback(lambda t: asyncio.create_task(_task_done_callback(t)))
        task.add_done_callback(lambda t: self._tasks.discard(t))
        self._tasks.add(task)
        return task

    async def wait(self, wait_callbacks: bool = True):
        pending = set(self._tasks)
        while pending:
            done, pending = await asyncio.wait(pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)

        if wait_callbacks:
            await self.wait_callbacks()

    async def wait_callbacks(self):
        pending = set(self._callbacks)
        while pending:
            done, pending = await asyncio.wait(pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)

    async def shutdown(self, wait: bool = True, cancel_tasks: bool = False, wait_callbacks: bool = True):
        """关闭任务池"""
        tasks = set(self._tasks)
        if cancel_tasks:
            for task in tasks:
                if not task.done() and not task.started:
                    task.cancel()

        if wait:
            await self.wait(wait_callbacks)
        elif wait_callbacks:
            await self.wait_callbacks()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown(False, True)
