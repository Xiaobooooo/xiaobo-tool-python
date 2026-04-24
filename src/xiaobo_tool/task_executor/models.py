from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger


@dataclass
class Target:
    """任务数据载体，封装索引、数据、代理和日志器，传递给任务函数。"""
    index: int
    data: Any
    data_preview: str
    logger: 'Logger' = None
    proxy: Optional[str] = None

    def refresh_proxy(self):
        return self.proxy

