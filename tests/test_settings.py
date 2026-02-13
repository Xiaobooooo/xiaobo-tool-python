"""settings 模块测试"""
import pytest

from xiaobo_tool.task_executor.settings import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.max_workers == 5
        assert s.retries == 2
        assert s.retry_delay == 0.0
        assert s.shuffle is False
        assert s.use_proxy_ipv6 is False
        assert s.disable_proxy is False

    def test_override(self):
        s = Settings(max_workers=10, retries=5, retry_delay=1.5)
        assert s.max_workers == 10
        assert s.retries == 5
        assert s.retry_delay == 1.5

    def test_empty_string_to_default(self):
        s = Settings(proxy="")
        assert s.proxy is None

    def test_bool_str_true_values(self):
        for v in ("true", "yes", "y", "1", "on", "True", "YES"):
            s = Settings(shuffle=v)
            assert s.shuffle is True

    def test_bool_str_false_values(self):
        for v in ("false", "no", "n", "0", "off", "False", "NO"):
            s = Settings(shuffle=v)
            assert s.shuffle is False

    def test_bool_str_task_name_match(self):
        """task_name 匹配时 Union[bool, str] 字段解析为 True"""
        s = Settings(task_name="MyTask", shuffle="MyTask&OtherTask")
        assert s.shuffle is True

    def test_bool_str_task_name_no_match(self):
        """task_name 不匹配时解析为 False"""
        s = Settings(task_name="MyTask", shuffle="OtherTask&AnotherTask")
        assert s.shuffle is False

    def test_max_workers_gt_zero(self):
        with pytest.raises(Exception):
            Settings(max_workers=0)

    def test_retries_ge_zero(self):
        with pytest.raises(Exception):
            Settings(retries=-1)

    def test_int_to_bool(self):
        s = Settings(shuffle=1)
        assert s.shuffle is True
        s2 = Settings(shuffle=0)
        assert s2.shuffle is False
