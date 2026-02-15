from typing import Optional
import queue
import re
import threading
import time

from loguru import logger
from curl_cffi import requests

from xiaobo_tool.utils import generate_random_string


class ProxyPool:
    """
    代理池管理器
    """

    def __init__(
            self,
            proxy: Optional[str] = None,
            proxy_ipv6: Optional[str] = None,
            proxy_api: Optional[str] = None,
            proxy_ipv6_api: Optional[str] = None,
            use_proxy_ipv6: bool = False,
            disable_proxy: bool = False
    ):
        self.proxy = proxy
        self.proxy_ipv6 = proxy_ipv6
        self.proxy_api = proxy_api
        self.proxy_ipv6_api = proxy_ipv6_api
        self.use_proxy_ipv6 = use_proxy_ipv6
        self.disable_proxy = disable_proxy
        self._proxy_queue: "queue.Queue[tuple[str, float]]" = queue.Queue()
        self._cache_ttl = 180  # 3 minutes in seconds
        self._fetch_lock = threading.Lock()

    def _dequeue_proxy(self) -> Optional[str]:
        """
        从队列中取出未过期的代理

        Returns:
            可用代理字符串，队列为空或全部过期返回None
        """
        while True:
            try:
                proxy, expiry = self._proxy_queue.get_nowait()
            except queue.Empty:
                return None

            if expiry > time.time():
                return proxy

    @staticmethod
    def _extract_proxies(text: str) -> list[str]:
        """
        从文本中提取代理地址

        支持格式：host:port, user:pass@host:port, protocol://host:port, protocol://user:pass@host:port

        Args:
            text: 包含代理的文本

        Returns:
            提取到的代理列表
        """
        proxy_pattern = re.compile(
            r"(?:[a-zA-Z][a-zA-Z0-9+.-]*://)?"
            r"(?:[^:@\s/]+:[^@\s/]+@)?"
            r"(?:\[[^]\s]+]|[a-zA-Z0-9.-]+):\d{1,5}"
        )

        proxies = []
        seen = set()
        for match in proxy_pattern.finditer(text):
            proxy = match.group(0)
            if proxy in seen:
                continue
            seen.add(proxy)
            proxies.append(proxy)

        return proxies

    def _get_proxy_from_api(self, api_url: str) -> Optional[str]:
        """
        从API获取代理，带3分钟缓存有效期
        每个代理只使用一次，使用后从队列中删除

        Args:
            api_url: 代理API地址

        Returns:
            可用的代理字符串，失败返回None
        """
        # 队列中有可用代理，直接返回
        proxy = self._dequeue_proxy()
        if proxy:
            return proxy

        with self._fetch_lock:
            # 双重检查，避免并发重复请求API
            proxy = self._dequeue_proxy()
            if proxy:
                return proxy

            try:
                # 通过API获取代理列表
                response = requests.get(api_url, timeout=10)
                current_time = time.time()
                # 使用正则解析响应，提取代理
                proxies = self._extract_proxies(response.text)
                if not proxies:
                    logger.error(f"未从API中解析到代理，响应: {response.text}")
                    return None

                # 将提取到的代理按顺序加入队列（设置3分钟有效期）
                expiry = current_time + self._cache_ttl
                for proxy in proxies:
                    self._proxy_queue.put((proxy, expiry))

                return self._dequeue_proxy()

            except Exception as e:
                logger.error(f"API获取代理失败: {repr(e)}")
                return None

    def get_proxy(self, placeholder: str = '*****', replacement: str = '', _use_proxy_ipv6: Optional[bool] = None) -> Optional[str]:
        """
        获取一个可用的代理

        Args:
            placeholder: 日志中用于隐藏敏感信息的占位符
            replacement: 替换占位符的内容
            _use_proxy_ipv6: 是否使用IPv6代理，None时使用self.use_proxy_ipv6

        Returns:
            可用的代理字符串，无代理返回None
        """
        # 禁用代理
        if self.disable_proxy:
            return None

        # 确定使用哪种代理类型
        use_ipv6 = _use_proxy_ipv6 if _use_proxy_ipv6 is not None else self.use_proxy_ipv6
        if use_ipv6 and not self.proxy_ipv6 and not self.proxy_ipv6_api:
            use_ipv6 = False

        # 选择对应的代理配置
        if use_ipv6:
            proxy = self.proxy_ipv6
            api_url = self.proxy_ipv6_api
        else:
            proxy = self.proxy
            api_url = self.proxy_api

        if replacement:
            replacement = generate_random_string()
        # 将replacement中的符号替换为空
        replacement = ''.join(c for c in replacement if c.isalnum())

        # 优先使用直接配置的proxy
        if proxy:
            return proxy.replace(placeholder, replacement)

        # proxy不存在时使用proxy_api
        if api_url:
            api_proxy = self._get_proxy_from_api(api_url)
            if api_proxy:
                return api_proxy.replace(placeholder, replacement)

        return None
