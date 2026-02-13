"""proxy_pool 模块测试"""
import time
from unittest.mock import patch, MagicMock

import pytest

from xiaobo_tool.proxy_pool import ProxyPool


class TestExtractProxies:
    def test_host_port(self):
        text = "proxy: 1.2.3.4:8080"
        assert ProxyPool._extract_proxies(text) == ["1.2.3.4:8080"]

    def test_with_protocol(self):
        text = "http://1.2.3.4:8080"
        assert ProxyPool._extract_proxies(text) == ["http://1.2.3.4:8080"]

    def test_with_auth(self):
        text = "socks5://user:pass@1.2.3.4:1080"
        assert ProxyPool._extract_proxies(text) == ["socks5://user:pass@1.2.3.4:1080"]

    def test_multiple(self):
        text = "1.1.1.1:80\n2.2.2.2:443\n3.3.3.3:8080"
        result = ProxyPool._extract_proxies(text)
        assert len(result) == 3

    def test_dedup(self):
        text = "1.1.1.1:80\n1.1.1.1:80"
        assert len(ProxyPool._extract_proxies(text)) == 1

    def test_no_match(self):
        assert ProxyPool._extract_proxies("no proxy here") == []


class TestGetProxy:
    def test_disabled(self):
        pool = ProxyPool(proxy="http://p:8080", disable_proxy=True)
        assert pool.get_proxy() is None

    def test_direct_proxy(self):
        pool = ProxyPool(proxy="http://1.2.3.4:8080")
        assert pool.get_proxy() == "http://1.2.3.4:8080"

    def test_placeholder_replacement(self):
        pool = ProxyPool(proxy="http://user:*****@host:8080")
        result = pool.get_proxy(placeholder="*****", replacement="session123")
        assert result == "http://user:session123@host:8080"

    def test_ipv6_proxy(self):
        pool = ProxyPool(proxy_ipv6="http://[::1]:8080", use_proxy_ipv6=True)
        assert pool.get_proxy() == "http://[::1]:8080"

    def test_ipv6_fallback_to_ipv4(self):
        """请求 IPv6 但无 IPv6 配置时回退到 IPv4"""
        pool = ProxyPool(proxy="http://1.2.3.4:8080", use_proxy_ipv6=True)
        assert pool.get_proxy() == "http://1.2.3.4:8080"

    def test_no_proxy_configured(self):
        pool = ProxyPool()
        assert pool.get_proxy() is None

    def test_override_use_ipv6(self):
        pool = ProxyPool(proxy="http://v4:80", proxy_ipv6="http://v6:80", use_proxy_ipv6=False)
        assert "v6" in pool.get_proxy(_use_proxy_ipv6=True)


class TestGetProxyFromApi:
    @patch("xiaobo_tool.proxy_pool.requests.get")
    def test_api_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "10.0.0.1:3128\n10.0.0.2:3128"
        mock_get.return_value = mock_resp

        pool = ProxyPool(proxy_api="http://api.example.com/proxy")
        proxy = pool.get_proxy()
        assert proxy in ("10.0.0.1:3128", "10.0.0.2:3128")
        mock_get.assert_called_once()

    @patch("xiaobo_tool.proxy_pool.requests.get")
    def test_api_uses_cache(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "10.0.0.1:3128\n10.0.0.2:3128"
        mock_get.return_value = mock_resp

        pool = ProxyPool(proxy_api="http://api.example.com/proxy")
        p1 = pool.get_proxy()
        p2 = pool.get_proxy()
        # 两次调用只请求一次 API，第二次从缓存取
        mock_get.assert_called_once()
        assert p1 != p2  # 每个代理只用一次

    @patch("xiaobo_tool.proxy_pool.requests.get")
    def test_api_failure(self, mock_get):
        mock_get.side_effect = Exception("network error")
        pool = ProxyPool(proxy_api="http://api.example.com/proxy")
        assert pool.get_proxy() is None

    @patch("xiaobo_tool.proxy_pool.requests.get")
    def test_api_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "no proxies"
        mock_get.return_value = mock_resp

        pool = ProxyPool(proxy_api="http://api.example.com/proxy")
        assert pool.get_proxy() is None

    def test_cache_expiry(self):
        pool = ProxyPool()
        pool._cache_ttl = 0  # 立即过期
        pool._proxy_queue.put(("1.1.1.1:80", time.time() - 1))
        assert pool._dequeue_proxy() is None
