import os

import dotenv
import pytest

dotenv.load_dotenv()


@pytest.fixture
def auth_token():
    """从 .env 文件获取 auth_token。"""
    token = os.getenv("AUTH_TOKEN")
    if not token:
        pytest.skip("AUTH_TOKEN 未配置")
    return token
