import sys

import dotenv
from loguru import logger

__version__ = '1.0.2'

dotenv.load_dotenv()

# 自定义日志格式
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | <cyan>[{extra[name]}]</cyan> - <level>{message}</level>",
    colorize=True,
    backtrace=False
)
logger.configure(extra={"name": "MainApp"})
