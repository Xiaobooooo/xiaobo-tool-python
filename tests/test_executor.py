"""executor 模块测试"""
import pytest

from xiaobo_tool.task_executor.executor import TaskExecutor, AsyncTaskExecutor
from xiaobo_tool.task_executor.exceptions import TaskFailed


# ── 同步 TaskExecutor ─────────────────────────────────────

class TestTaskExecutor:
    def test_basic_success(self):
        results = []
        executor = TaskExecutor(name="Test", max_workers=2, disable_proxy=True)
        executor.submit_tasks(
            task_func=lambda t: t.data,
            source=["a", "b", "c"],
            on_success=lambda t, r: results.append(r),
        )
        executor.wait()
        assert sorted(results) == ["a", "b", "c"]
        assert executor.get_success_count() == 3
        assert executor.get_error_count() == 0

    def test_error_counting(self):
        executor = TaskExecutor(name="Test", max_workers=1, retries=0, disable_proxy=True)

        def fail(t):
            raise RuntimeError("fail")

        executor.submit_tasks(task_func=fail, source=["x"])
        executor.wait()
        assert executor.get_error_count() == 1
        assert executor.get_success_count() == 0

    def test_retry_then_succeed(self):
        call_count = {"n": 0}
        executor = TaskExecutor(name="Test", max_workers=1, retries=2, retry_delay=0, disable_proxy=True)

        def flaky(t):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        executor.submit_tasks(task_func=flaky, source=["item"])
        executor.wait()
        assert executor.get_success_count() == 1
        assert call_count["n"] == 3

    def test_task_failed_no_retry(self):
        call_count = {"n": 0}
        executor = TaskExecutor(name="Test", max_workers=1, retries=3, retry_delay=0, disable_proxy=True)

        def fatal(t):
            call_count["n"] += 1
            raise TaskFailed("不可恢复")

        executor.submit_tasks(task_func=fatal, source=["item"])
        executor.wait()
        assert call_count["n"] == 1  # TaskFailed 不重试
        assert executor.get_error_count() == 1

    def test_submit_tasks_int_source(self):
        results = []
        executor = TaskExecutor(name="Test", max_workers=2, disable_proxy=True)
        executor.submit_tasks(
            task_func=lambda t: t.index,
            source=3,
            on_success=lambda t, r: results.append(r),
        )
        executor.wait()
        assert sorted(results) == [0, 1, 2]

    def test_submit_tasks_from_file(self, tmp_path, monkeypatch):
        import sys
        f = tmp_path / "input.txt"
        f.write_text("aaa----111\nbbb----222\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])

        results = []
        executor = TaskExecutor(name="Test", max_workers=1, disable_proxy=True)
        executor.submit_tasks_from_file(
            task_func=lambda t: t.data,
            filename="input",
            on_success=lambda t, r: results.append(r),
        )
        executor.wait()
        assert len(results) == 2
        assert ["aaa", "111"] in results
        assert ["bbb", "222"] in results

    def test_context_manager(self):
        with TaskExecutor(name="Test", max_workers=1, disable_proxy=True) as executor:
            executor.submit_tasks(task_func=lambda t: None, source=1)

    def test_statistics(self, capsys):
        executor = TaskExecutor(name="Test", max_workers=1, disable_proxy=True)
        executor.submit_tasks(task_func=lambda t: None, source=2)
        executor.wait()
        executor.statistics()  # 不抛异常即可

    def test_proxy_refresh(self):
        executor = TaskExecutor(name="Test", max_workers=1, proxy="http://p:8080")
        proxies = []

        def capture_proxy(t):
            proxies.append(t.proxy)

        executor.submit_tasks(task_func=capture_proxy, source=1)
        executor.wait()
        assert len(proxies) == 1
        assert proxies[0] == "http://p:8080"


# ── 异步 AsyncTaskExecutor ────────────────────────────────

class TestAsyncTaskExecutor:
    @pytest.mark.asyncio
    async def test_basic_success(self):
        results = []
        executor = AsyncTaskExecutor(name="AsyncTest", max_workers=2, disable_proxy=True)

        async def task(t):
            return t.data

        async def on_ok(t, r):
            results.append(r)

        executor.submit_tasks(task_func=task, source=["x", "y"], on_success=on_ok)
        await executor.wait()
        assert sorted(results) == ["x", "y"]
        assert await executor.get_success_count() == 2

    @pytest.mark.asyncio
    async def test_error_counting(self):
        executor = AsyncTaskExecutor(name="AsyncTest", max_workers=1, retries=0, disable_proxy=True)

        async def fail(t):
            raise RuntimeError("async fail")

        executor.submit_tasks(task_func=fail, source=["x"])
        await executor.wait()
        assert await executor.get_error_count() == 1

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self):
        call_count = {"n": 0}
        executor = AsyncTaskExecutor(name="AsyncTest", max_workers=1, retries=2, retry_delay=0, disable_proxy=True)

        async def flaky(t):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("not yet")
            return "ok"

        executor.submit_tasks(task_func=flaky, source=["item"])
        await executor.wait()
        assert await executor.get_success_count() == 1
        assert call_count["n"] == 3

    @pytest.mark.asyncio
    async def test_task_failed_no_retry(self):
        call_count = {"n": 0}
        executor = AsyncTaskExecutor(name="AsyncTest", max_workers=1, retries=3, retry_delay=0, disable_proxy=True)

        async def fatal(t):
            call_count["n"] += 1
            raise TaskFailed("不可恢复")

        executor.submit_tasks(task_func=fatal, source=["item"])
        await executor.wait()
        assert call_count["n"] == 1
        assert await executor.get_error_count() == 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncTaskExecutor(name="AsyncTest", max_workers=1, disable_proxy=True) as executor:
            async def noop(t):
                pass

            executor.submit_tasks(task_func=noop, source=1)
