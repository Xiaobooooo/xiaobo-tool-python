import time
import random
from typing import Any

from loguru import logger
from xiaobo_tool.task_executor import TaskExecutor, Target, TaskFailed
from xiaobo_tool.task_executor.settings import Settings

APPNAME = "TaskExample"


def example_task_processor(target: Target):
    """
    这是我们要并发执行的主任务函数。
    """
    logger.debug(f"proxy: {target.proxy}")
    target.logger.info(f"开始处理任务，数据: {target.data}")
    target.logger.info(f"任务分配到的代理是: {target.proxy}")

    sleep_time = random.uniform(1, 3)
    time.sleep(sleep_time)

    if target.data in ["data-6"]:
        raise TaskFailed("任务失败，不进行重试")

    # 为了演示重试，我们让 'data-3' 和 'data-7' 任务总是失败
    if target.data in ["data-3", "data-7"]:
        # target.index 是从0开始的，所以这里可以用来区分不同任务的失败场景
        if target.index % 2 == 0:
            # 偶数索引的任务模拟一个网络错误
            raise ConnectionError("模拟一个网络连接错误")
        else:
            # 奇数索引的任务模拟一个值错误
            raise ValueError("模拟一个无效值错误")

    return f"'{target.data}' 处理完毕，耗时 {sleep_time:.2f} 秒"


def on_task_success(target: Target, result: Any):
    """任务成功完成时的回调函数。"""
    target.logger.success(f"成功回调 [数据: {target.data}] -> 结果: {result}")


def on_task_error(target: Target, error: Exception):
    """任务失败时的回调函数（所有重试都用完后才会调用）。"""
    time.sleep(1)  # 模拟阻塞，测试wait是否等待回调函数
    target.logger.error(f"失败回调 [数据: {target.data}] -> 最终异常: {error.__class__.__name__}: {error}")


def on_task_cancel(target: Target):
    """任务被取消时的回调函数。"""
    target.logger.warning(f"取消回调 [数据: {target.data}]")


def main():
    task_data_list = [f"data-{i}" for i in range(15)]
    settings = Settings(shuffle=False)
    with TaskExecutor(APPNAME, settings=settings) as task_manager:
        logger.info("--- 开始批量提交任务 ---")
        # 批量提交任务
        # 也可以在提交时覆盖重试策略
        task_manager.submit_tasks(
            task_func=example_task_processor,
            source=task_data_list,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
        )

        task_manager.wait()

        task_manager.statistics()

    logger.info("--- 所有任务已执行完毕 ---")


if __name__ == "__main__":
    main()
