"""models 模块测试"""
from xiaobo_tool.task_executor.models import Target


class TestTarget:
    def test_creation(self):
        t = Target(index=0, data="hello", data_preview="hello")
        assert t.index == 0
        assert t.data == "hello"
        assert t.proxy is None
        assert t.logger is None

    def test_refresh_proxy_default(self):
        t = Target(index=0, data="x", data_preview="x", proxy="http://p:80")
        assert t.refresh_proxy() == "http://p:80"

    def test_refresh_proxy_override(self):
        t = Target(index=0, data="x", data_preview="x")
        t.refresh_proxy = lambda: "http://new:80"
        assert t.refresh_proxy() == "http://new:80"
