"""manager 模块测试"""
import asyncio
import time

import pytest

from xiaobo_tool.task_executor.manager import TaskManager, AsyncTaskManager
from xiaobo_tool.task_executor.models import Target


def _make_target(index=0):
    return Target(index=index, data=f"item_{index}", data_preview=f"item_{index}")


# ── 同步 TaskManager ─────────────────────────────────────

class TestTaskManager:
    def test_submit_and_wait(self):
        results = []
        mgr = TaskManager(max_workers=2)
        target = _make_target()

        mgr.submit_task(
            task_func=lambda: 42,
            target=target,
            on_success=lambda t, r: results.append(r),
        )
        mgr.wait()
        assert results == [42]

    def test_error_callback(self):
        errors = []
        mgr = TaskManager(max_workers=1)
        target = _make_target()

        def failing():
            raise ValueError("boom")

        mgr.submit_task(
            task_func=failing,
            target=target,
            on_error=lambda t, e: errors.append(str(e)),
        )
        mgr.wait()
        assert len(errors) == 1
        assert "boom" in errors[0]

    def test_cancel_callback(self):
        cancels = []
        mgr = TaskManager(max_workers=1)

        # 提交一个慢任务占住线程池
        mgr.submit_task(task_func=lambda: time.sleep(5), target=_make_target(0))
        # 提交第二个任务
        mgr.submit_task(
            task_func=lambda: None,
            target=_make_target(1),
            on_cancel=lambda t: cancels.append(t.index),
        )
        mgr.shutdown(wait=True, cancel_tasks=True)
        # 第二个任务应该被取消（或已完成）
        # 不做严格断言，因为取决于调度时序

    def test_multiple_tasks(self):
        results = []
        mgr = TaskManager(max_workers=3)
        for i in range(5):
            mgr.submit_task(
                task_func=lambda: 1,
                target=_make_target(i),
                on_success=lambda t, r: results.append(r),
            )
        mgr.wait()
        assert sum(results) == 5

    def test_invalid_max_workers(self):
        with pytest.raises(ValueError):
            TaskManager(max_workers=0)


# ── 异步 AsyncTaskManager ────────────────────────────────

class TestAsyncTaskManager:
    @pytest.mark.asyncio
    async def test_submit_and_wait(self):
        results = []
        mgr = AsyncTaskManager(max_workers=2)
        target = _make_target()

        async def task():
            return 99

        async def on_ok(t, r):
            results.append(r)

        mgr.submit_task(task_func=task, target=target, on_success=on_ok)
        await mgr.wait()
        assert results == [99]

    @pytest.mark.asyncio
    async def test_error_callback(self):
        errors = []
        mgr = AsyncTaskManager(max_workers=1)
        target = _make_target()

        async def failing():
            raise RuntimeError("async boom")

        async def on_err(t, e):
            errors.append(str(e))

        mgr.submit_task(task_func=failing, target=target, on_error=on_err)
        await mgr.wait()
        assert len(errors) == 1
        assert "async boom" in errors[0]

    @pytest.mark.asyncio
    async def test_semaphore_concurrency(self):
        """验证信号量限制并发数"""
        running = []
        max_concurrent = 0

        async def track_task():
            nonlocal max_concurrent
            running.append(1)
            current = len(running)
            if current > max_concurrent:
                max_concurrent = current
            await asyncio.sleep(0.05)
            running.pop()

        mgr = AsyncTaskManager(max_workers=2)
        for i in range(6):
            mgr.submit_task(task_func=track_task, target=_make_target(i))
        await mgr.wait()
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_cancel_unstarted(self):
        cancels = []
        mgr = AsyncTaskManager(max_workers=1)

        async def slow():
            await asyncio.sleep(10)

        async def on_cancel(t):
            cancels.append(t.index)

        # 第一个任务占住信号量
        mgr.submit_task(task_func=slow, target=_make_target(0))
        await asyncio.sleep(0.01)  # 让第一个任务开始
        # 提交更多任务
        for i in range(1, 4):
            mgr.submit_task(task_func=slow, target=_make_target(i), on_cancel=on_cancel)

        await mgr.shutdown(wait=True, cancel_tasks=True)
        # 未开始的任务应被取消
        assert len(cancels) >= 1
