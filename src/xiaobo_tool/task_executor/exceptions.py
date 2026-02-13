"""自定义异常模块"""


class TaskFailed(Exception):
    """不可恢复的任务失败异常，抛出后框架不会重试，直接标记失败。"""
    pass
