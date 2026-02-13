# Xiaobo Tool [![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/0xiaobo888)](https://x.com/0xiaobo888)

![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?logo=python&tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-tool-python%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
![Project Version from TOML](https://img.shields.io/badge/dynamic/toml?logo=semanticweb&color=orange&label=version&query=project.version&url=https%3A%2F%2Fraw.githubusercontent.com%2FXiaobooooo%2Fxiaobo-tool-python%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)

Python 通用工具库，提供任务执行器、代理池、X(Twitter) 客户端等模块。

## 安装

```bash
uv add xiaobo-tool
```

## 模块概览

### task_executor - 任务执行器

支持同步（线程池）和异步（asyncio）两种模式，内置重试、代理轮换、回调通知和统计。

```python
from xiaobo_tool.task_executor import TaskExecutor, Target


def my_task(target: Target):
    print(f"执行任务: {target.data}, 代理: {target.proxy}")


with TaskExecutor(name="Demo", max_workers=3, retries=2) as executor:
    executor.submit_tasks(
        task_func=my_task,
        source=["item1", "item2", "item3"],
        on_success=lambda t, r: print(f"{t.data} 成功"),
        on_error=lambda t, e: print(f"{t.data} 失败: {e}"),
    )
    executor.wait()
    executor.statistics()
```

异步模式：

```python
import asyncio
from xiaobo_tool.task_executor import AsyncTaskExecutor, Target


async def my_async_task(target: Target):
    print(f"执行任务: {target.data}")


async def main():
    async with AsyncTaskExecutor(name="AsyncDemo", max_workers=5) as executor:
        executor.submit_tasks(task_func=my_async_task, source=10)
        await executor.wait()
        await executor.statistics()


asyncio.run(main())
```

从文件批量提交任务：

```python
# 读取 accounts.txt，每行按 "----" 分割
executor.submit_tasks_from_file(task_func=my_task, filename="accounts", separator="----")
```

配置通过 `Settings` 管理，支持构造参数、环境变量、`.env` 文件三种方式：

| 配置项              | 默认值     | 说明                                                                       |
|------------------|---------|--------------------------------------------------------------------------|
| `MAX_WORKERS`    | `5`     | 最大线程数                                                                    |
| `PROXY`          | *(空)*   | 代理，支持 `host:port` / `user:pass@host:port`，占位符 `*****` 自动替换为 index 或第一位数据 |
| `PROXY_IPV6`     | *(空)*   | IPv6 代理，格式同 `PROXY`                                                      |
| `PROXY_API`      | *(空)*   | 代理提取 API 地址（一行一个）                                                        |
| `PROXY_IPV6_API` | *(空)*   | IPv6 代理提取 API 地址                                                         |
| `RETRIES`        | `2`     | 重试次数（抛出 `TaskFailed` 不重试）                                                |
| `RETRY_DELAY`    | `0`     | 重试延迟（秒）                                                                  |
| `SHUFFLE`        | `false` | 是否打乱任务顺序，按照数量运行的任务，支持布尔值或任务名称，多个任务用&拼接，如： `task1&task2`                  |
| `USE_PROXY_IPV6` | `false` | 是否优先使用 IPv6 代理，支持布尔值或任务名称，多个任务用&拼接，如： `task1&task2`                      |
| `DISABLE_PROXY`  | `false` | 是否禁用代理，支持布尔值或任务名称，多个任务用&拼接，如：`task1&task2`                               |

抛出 `TaskFailed` 异常可跳过重试，直接标记任务失败：

```python
from xiaobo_tool.task_executor import TaskFailed


def my_task(target: Target):
    if invalid(target.data):
        raise TaskFailed("数据无效，无需重试")
```

### proxy_pool - 代理池

管理代理获取与轮换，支持直连代理和 API 代理（带 3 分钟缓存）。

```python
from xiaobo_tool.proxy_pool import ProxyPool

pool = ProxyPool(proxy_api="http://your-proxy-api.com/get")
proxy = pool.get_proxy()
```

### x - X(Twitter) 客户端

基于 `auth_token` 操作 X API，支持发推和 OAuth2 授权。

```python
from xiaobo_tool.x import XClient

client = XClient(auth_token="your_auth_token", proxy="http://127.0.0.1:7890")
tweet_url = client.send_tweet("Hello World!")
```

OAuth2 授权：

```python
redirect_uri = client.authorize_oauth2("https://x.com/i/oauth2/authorize?client_id=xxx&...")
```

### utils - 工具函数

- `read_txt_file_lines(filename)` - 按行读取 txt 文件
- `write_txt_file(filename, data)` - 写入/追加 txt 文件
- `get_session(proxy)` / `get_async_session(proxy)` - 创建 HTTP 会话（curl_cffi）
- `json_get(data, path, default)` - 通过路径访问嵌套 JSON 数据
- `raise_response_error(name, response)` - 解析 HTTP 错误响应并抛出异常

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest
```

## 依赖

- [curl-cffi](https://github.com/lexiforest/curl_cffi) - HTTP 客户端（浏览器指纹模拟）
- [loguru](https://github.com/Delgan/loguru) - 日志
- [pydantic-settings](https://github.com/pydantic/pydantic-settings) - 配置管理
- [tenacity](https://github.com/jd/tenacity) - 重试机制
