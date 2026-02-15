"""
通用工具模块
"""
import json
import re
import secrets
import string
import threading
from enum import IntFlag
from typing import List, Optional, NoReturn
from pathlib import Path
import sys

from curl_cffi import BrowserTypeLiteral, Session, AsyncSession, Response
from curl_cffi.requests.exceptions import HTTPError
from curl_cffi.requests.impersonate import DEFAULT_CHROME

# 进程内文件锁表，避免多线程写同一文件时竞争
_thread_file_locks: dict[Path, threading.Lock] = {}
_file_locks_guard = threading.Lock()


def _resolve_txt_path(filename: str, allow_missing: bool = False) -> Path:
    """
    补全 .txt 后缀并将相对路径定位到脚本目录，缺失时回退到脚本父目录同级 data 目录。

    :param filename: 文件名或路径。
    :param allow_missing: 为 True 时文件不存在不抛异常，返回主路径。
    :return: 解析后的绝对路径。
    :raises FileNotFoundError: allow_missing 为 False 且文件不存在时抛出。
    """
    if not filename.lower().endswith('.txt'):
        filename += '.txt'

    path = Path(filename)
    if not path.is_absolute():
        entry_dir = Path(sys.argv[0]).resolve().parent
        primary = entry_dir / path
        if primary.exists():
            path = primary
        else:
            base_dir = entry_dir.parent
            if 'Xiaobooooo' in base_dir.name:
                base_dir = base_dir.parent
            data_dir = base_dir / 'data'
            candidate = data_dir / path
            if candidate.exists():
                path = candidate
            else:
                if allow_missing:
                    path = primary
                else:
                    raise FileNotFoundError(f"错误：文件未找到，已尝试 '{primary}' 与 '{candidate}'。")
    return path


def _get_thread_lock(path: Path) -> threading.Lock:
    """
    为目标路径获取/创建一个进程内线程锁。

    :param path: 文件路径。
    :return: 对应路径的线程锁。
    """
    with _file_locks_guard:
        lock = _thread_file_locks.get(path)
        if lock is None:
            lock = threading.Lock()
            _thread_file_locks[path] = lock
        return lock


def read_txt_file_lines(filename: str) -> List[str]:
    """
    读取txt文件内容并按行返回一个列表。

    功能:
    - 如果文件名没有 .txt 后缀(不区分大小写)，会自动补全。
    - 优先读取脚本目录下的文件；不存在则读取脚本父目录同级的 data 目录。
    - 按行读取文件，并去除每行两侧的空白字符（包括换行符）。
    - 返回一个包含文件中所有非空行的字符串列表。

    :param filename: 要读取的txt文件名。
    :return: 包含文件所有行的字符串列表。
    :raises FileNotFoundError: 如果文件未找到。
    :raises IOError: 如果发生其他读取错误。
    """
    path = _resolve_txt_path(filename)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            # 使用列表推导式高效读取，并只保留非空行
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        raise FileNotFoundError(f"读取文件 '{path}' 时发生错误: 未找到文件")
    except Exception as e:
        raise IOError(f"读取文件 '{path}' 时发生错误: {e}")


def write_txt_file(filename: str, data: str | List[str], append: bool = True, separator: str = "----") -> None:
    """
    写入或追加文本到txt文件。

    功能:
    - 自动补全 .txt 后缀（不区分大小写）。
    - 优先写入/追加脚本目录下的文件；不存在则写入脚本父目录同级的 data 目录。
    - data 支持字符串或字符串列表，列表会用分隔符拼接后写入。
    - append 为 True 时追加写入，否则覆盖写入，默认 True。
    - separator 控制列表拼接时的分隔符，默认 "----"。

    :param filename: 目标文件名。
    :param data: 要写入的内容，字符串或字符串列表。
    :param append: 是否追加写入。
    :param separator: data 为列表时的拼接分隔符。
    """
    path = _resolve_txt_path(filename, allow_missing=True)
    lock = _get_thread_lock(path)

    text = separator.join(data) if isinstance(data, list) else str(data)
    if text and not text.endswith('\n'):
        text += '\n'

    mode = 'a' if append else 'w'
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, mode, encoding='utf-8') as f:
            f.write(text)


def get_session(proxy: str = None, timeout: int = 30, impersonate: Optional[BrowserTypeLiteral] = DEFAULT_CHROME) -> Session:
    """
    创建同步 HTTP 会话。 自动配置User-Agent

    :param proxy: 代理地址。
    :param timeout: 请求超时时间（秒）。
    :param impersonate: 浏览器指纹模拟类型。
    :return: 同步 Session 实例。
    """
    return Session(proxy=proxy, timeout=timeout, impersonate=impersonate)


def get_async_session(
        proxy: str = None,
        timeout: int = 30,
        impersonate: Optional[BrowserTypeLiteral] = DEFAULT_CHROME
) -> AsyncSession:
    """
    创建异步 HTTP 会话。 自动配置User-Agent

    :param proxy: 代理地址。
    :param timeout: 请求超时时间（秒）。
    :param impersonate: 浏览器指纹模拟类型。
    :return: 异步 AsyncSession 实例。
    """
    return AsyncSession(proxy=proxy, timeout=timeout, impersonate=impersonate)


def json_get(data: dict | list, path: str, default=None):
    """
    通过keys拼接的字符串路径获取dict/list中的值。

    :param data: 要查询的字典或列表
    :param path: 用 "/" 分隔的路径字符串，支持数组索引
    :param default: 路径不存在时返回的默认值
    :return: 路径对应的值，或默认值

    示例:
        data = {"a": [2, 5, 7], "b": {"c": "hello"}}
        json_get(data, "a/0")  # 返回 2
        json_get(data, "a/2")  # 返回 7
        json_get(data, "b/c")  # 返回 "hello"
    """
    if not path:
        return data

    keys = path.split('/')
    current = data

    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return default
            current = current[key]
        elif isinstance(current, list):
            try:
                index = int(key)
                if index < 0 or index >= len(current):
                    return default
                current = current[index]
            except (ValueError, IndexError):
                return default
        else:
            return default

    return current


def raise_response_error(name: str, response: Response, msg_key: Optional[str] = None) -> NoReturn:
    """
    解析 HTTP 响应中的错误信息并抛出 HTTPError。

    支持 JSON、HTML（含 Cloudflare 错误页）等响应格式，自动提取错误消息。

    :param name: 接口名称，用于错误消息前缀。
    :param response: HTTP 响应对象。
    :param msg_key: JSON 响应中自定义错误消息的路径（支持 json_get 路径格式）。
    :raises HTTPError: 始终抛出，附带解析后的错误信息。
    """
    error_message = None
    content_type = response.headers.get('Content-Type', "").lower()
    if 'application/json' in content_type or '+json' in content_type:
        try:
            data = response.json()
            if msg_key:
                error_message = json_get(data, msg_key)
            if not error_message:
                error_message = (
                        data.get('message') or
                        data.get('msg') or
                        data.get('error') or
                        data.get('error_message') or
                        data.get('error_msg')
                )
        except json.JSONDecodeError:
            pass
    elif 'text/html' in content_type:
        if response.text.lstrip().startswith('<'):
            if 'cf-error-details' not in response.text:
                raise HTTPError(f'{name}: {response.status_code} - 响应HTML', response=response)
            error_message = parse_cloudflare_error(response.text)
    if error_message:
        raise HTTPError(f'{name}: {error_message}', response=response)

    response_text = response.text.replace('\n', '').replace('\r', '')[:200]
    raise HTTPError(f'{name}: {response.status_code} - {response_text}', response=response)


def parse_cloudflare_error(html_text: str) -> Optional[str]:
    """
    从 Cloudflare 错误页面 HTML 中提取错误码和错误信息。

    :param html_text: Cloudflare 错误页面的 HTML 文本。
    :return: 格式化的错误描述字符串，无法解析时返回 None。
    """
    if not html_text:
        return None

    error_code = None
    error_message = None

    # Pattern 1: 5xx errors - "Error code XXX" in code-label span
    code_match = re.search(r'<span class="code-label">Error code (\d+)</span>', html_text)
    if code_match:
        error_code = code_match.group(1)

    # Pattern 2: 1xxx errors - Error followed by code in separate spans
    if not error_code:
        code_match = re.search(
            r'<span[^>]*data-translate="error"[^>]*>Error</span>\s*<span>(\d+)</span>',
            html_text,
        )
        if code_match:
            error_code = code_match.group(1)

    # Message pattern 1: 5xx - inline-block span in h1
    msg_match = re.search(
        r'<h1[^>]*>.*?<span class="inline-block">([^<]+)</span>', html_text, re.DOTALL
    )
    if msg_match:
        error_message = msg_match.group(1).strip()

    # Message pattern 2: 1xxx - h2 with text-gray-600 class
    if not error_message:
        msg_match = re.search(
            r'<h2\s+class="text-gray-600[^"]*"[^>]*>\s*([^<]+)\s*</h2>', html_text
        )
        if msg_match:
            error_message = msg_match.group(1).strip()

    # Pattern 3: Blocked page - "Sorry, you have been blocked"
    if not error_message:
        block_match = re.search(
            r'<h1[^>]*data-translate="block_headline"[^>]*>([^<]+)</h1>', html_text
        )
        if block_match:
            error_message = block_match.group(1).strip()
            # Try to extract subheadline: "You are unable to access xxx.com"
            subheadline_match = re.search(
                r'<h2[^>]*class="cf-subheadline"[^>]*>\s*<span[^>]*>([^<]+)</span>\s*([^\s<]+)',
                html_text,
            )
            if subheadline_match:
                access_text = subheadline_match.group(1).strip()
                domain = subheadline_match.group(2).strip()
                if access_text and domain:
                    error_message = f"{error_message} ({access_text} {domain})"

    if error_code and error_message:
        return f"Cloudflare Error Code {error_code} - {error_message}"
    if error_code:
        return f"Cloudflare Error Code {error_code}"
    if error_message:
        return f"Cloudflare Error - {error_message}"
    return None


class CharType(IntFlag):
    """随机字符串的字符类型标志位，支持位或组合。"""
    DIGIT = 1  # 数字 0-9
    LETTER = 2  # 字母 a-zA-Z
    SYMBOL = 4  # 特殊字符
    HEX = 8  # 十六进制 0-9a-fA-F


class LetterCase(IntFlag):
    """字母大小写标志位，支持位或组合。"""
    UPPER = 1  # 大写字母
    LOWER = 2  # 小写字母


def generate_random_string(
        length: int,
        char_types: CharType = CharType.DIGIT | CharType.LETTER,
        letter_case: LetterCase = LetterCase.UPPER | LetterCase.LOWER
) -> str:
    """
    生成指定长度和字符类型的随机字符串。

    :param length: 随机字符串长度，必须为正整数。
    :param char_types: 字符类型标志位，支持位或组合，例如 CharType.DIGIT | CharType.LETTER：
        - CharType.DIGIT: 数字 0-9
        - CharType.LETTER: 字母 a-zA-Z（受 letter_case 控制）
        - CharType.SYMBOL: 特殊字符
        - CharType.HEX: 十六进制字符 0-9a-fA-F（受 letter_case 控制）
    :param letter_case: 字母大小写标志位，支持位或组合：
        - LetterCase.UPPER: 纯大写
        - LetterCase.LOWER: 纯小写
        - LetterCase.UPPER | LetterCase.LOWER: 大小写都包含（默认）
    :return: 生成的随机字符串。
    :raises ValueError: 参数无效时抛出。
    """
    if length <= 0:
        raise ValueError("length 必须为正整数")
    if not letter_case:
        raise ValueError("letter_case 至少需要设置 LetterCase.UPPER 或 LetterCase.LOWER")

    charset = ""
    if char_types & CharType.DIGIT:
        charset += string.digits
    if char_types & CharType.LETTER:
        charset += string.ascii_letters
    if char_types & CharType.SYMBOL:
        charset += string.punctuation
    if char_types & CharType.HEX:
        charset += "0123456789abcdefABCDEF"

    if not charset:
        raise ValueError("未指定有效的字符类型")

    # 根据大小写标志转换字符池
    has_upper = bool(letter_case & LetterCase.UPPER)
    has_lower = bool(letter_case & LetterCase.LOWER)
    if has_upper and not has_lower:
        charset = charset.upper()
    elif has_lower and not has_upper:
        charset = charset.lower()

    # 去重保持字符池唯一
    charset = "".join(dict.fromkeys(charset))
    return "".join(secrets.choice(charset) for _ in range(length))
