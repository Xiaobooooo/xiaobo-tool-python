"""通用任务执行框架，支持同步多线程与异步并发，提供重试、代理池、回调等能力。"""
from .models import Target
from .exceptions import TaskFailed
from .executor import TaskExecutor, AsyncTaskExecutor
from .manager import TaskManager, AsyncTaskManager

__all__ = [
    'Target',
    'TaskManager',
    'AsyncTaskManager',
    'TaskFailed',
    'TaskExecutor',
    'AsyncTaskExecutor',
]
