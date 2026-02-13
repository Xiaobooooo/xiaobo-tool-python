import asyncio
import random
from typing import Any

from loguru import logger

from xiaobo_tool.task_executor import Target, TaskFailed, AsyncTaskExecutor

APPNAME = "AsyncExample"
FILENAME = 'example'


async def example_async_task_processor(target: Target):
    """
    这是我们要并发执行的主任务函数。
    """
    target.logger.info(f"开始处理任务，数据: {target.data}")
    target.logger.info(f"任务分配到的代理是: {target.proxy}")

    sleep_time = random.uniform(1, 3)
    await asyncio.sleep(sleep_time)

    if target.data in ["data-6"]:
        raise TaskFailed("任务失败，不进行重试")

    # 为了演示重试，我们让 'data-3' 和 'data-7' 任务总是失败
    if target.data[0] in ["data-3", "data-7"]:
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
    target.logger.info(f"成功回调 [数据: {target.data[0]}] -> 结果: {result}")
    # 保存成功信息
    # write_txt_file('example_success', result)


async def on_task_error(target: Target, error: Exception):
    """任务失败时的回调函数（所有重试都用完后才会调用）。"""
    await asyncio.sleep(1)  # 模拟阻塞，测试wait是否等待回调函数
    target.logger.error(f"失败回调 [数据: {target.data[0]}] -> 最终异常: {error.__class__.__name__}: {error}")
    # 保存失败信息
    # write_txt_file('example_error.txt', target.data)


def on_task_cancel(target: Target):
    """任务被取消时的回调函数。"""
    target.logger.warning(f"取消回调 [数据: {target.data[0]}]")
    # 保存取消的信息
    # write_txt_file('example_cancel', target.data)


def on_task_complete(target: Target):
    """任务结束时的回调函数，无论成功、失败还是取消都会执行。"""
    target.logger.info(f"完成回调 [数据: {target.data[0]}]")


async def main():
    async with AsyncTaskExecutor(APPNAME, retries=1) as task_manager:
        task_manager.submit_tasks_from_file(
            task_func=example_async_task_processor,
            filename=FILENAME,
            on_success=on_task_success,
            on_error=on_task_error,
            on_cancel=on_task_cancel,
            on_complete=on_task_complete,
        )

        await task_manager.wait()

        await task_manager.statistics()

    logger.info("--- 所有任务已执行完毕 ---")


if __name__ == "__main__":
    asyncio.run(main())
