from typing import Optional
from xiaobo_tool.utils import get_session, get_async_session, raise_response_error


class TempEmail:
    """临时邮箱客户端（同步）"""

    def __init__(self, base_url: str = 'http://43.155.171.174:2222'):
        self.session = get_session()
        self.base_url = base_url.rstrip('/')

    def __enter__(self) -> 'TempEmail':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _get(self, path: str, params: Optional[dict] = None) -> dict | list | str:
        """发送 GET 请求并返回响应 data 字段"""
        resp = self.session.get(f"{self.base_url}/tempMail/{path}", params=params)
        if resp.status_code != 200:
            raise_response_error(f"临时邮箱/{path}", resp)
        result = resp.json()
        if result.get("code") != 200:
            raise RuntimeError(f"临时邮箱/{path}: {result.get('msg', result)}")
        return result.get("data")

    def query_domains(self) -> list[str]:
        """
        查询可用域名列表。

        :return: 域名字符串列表。
        """
        return self._get("queryDomains")

    def create_mailbox(self, domain: str = '', mailbox: str = '', mail_type: int = 0) -> str:
        """
        创建一个临时邮箱。

        :param domain: 指定域名，为空时随机选择。
        :param mailbox: 指定邮箱名，不为空时 type 无效。
        :param mail_type: 随机生成类型 0-英数混合 1-字母 2-数字 3-手机号 4-首字母+数字。
        :return: 完整邮箱地址。
        """
        params = {"type": mail_type, "domain": domain, "mailbox": mailbox}
        return self._get("createMailbox", params)

    def get_new_mail(self, mailbox: str, title: str = '') -> dict:
        """
        获取新邮件（需先创建邮箱）。

        :param mailbox: 邮箱地址。
        :param title: 按标题过滤的关键字。
        :return: 邮件详情字典。
        """
        params = {"mailbox": mailbox, "title": title}
        return self._get("getNewMail", params)


class AsyncTempEmail:
    """临时邮箱客户端（异步）"""

    def __init__(self, base_url: str = 'http://43.155.171.174:2222'):
        self.session = get_async_session()
        self.base_url = base_url.rstrip('/')

    async def __aenter__(self) -> 'AsyncTempEmail':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def _get(self, path: str, params: Optional[dict] = None) -> dict | list | str:
        """发送 GET 请求并返回响应 data 字段"""
        resp = await self.session.get(f"{self.base_url}/tempMail/{path}", params=params)
        if resp.status_code != 200:
            raise_response_error(f"临时邮箱/{path}", resp)
        result = resp.json()
        if result.get("code") != 200:
            raise RuntimeError(f"临时邮箱/{path}: {result.get('msg', result)}")
        return result.get("data")

    async def query_domains(self) -> list[str]:
        """
        查询可用域名列表。

        :return: 域名字符串列表。
        """
        return await self._get("queryDomains")

    async def create_mailbox(self, domain: str = '', mailbox: str = '', mail_type: int = 0) -> str:
        """
        创建一个临时邮箱。

        :param domain: 指定域名，为空时随机选择。
        :param mailbox: 指定邮箱名，不为空时 mail_type 无效。
        :param mail_type: 随机生成类型 0-英数混合 1-字母 2-数字 3-手机号 4-首字母+数字。
        :return: 完整邮箱地址。
        """
        params = {"type": mail_type, "domain": domain, "mailbox": mailbox}
        return await self._get("createMailbox", params)

    async def get_new_mail(self, mailbox: str, title: str = '') -> dict:
        """
        获取新邮件（需先创建邮箱）。

        :param mailbox: 邮箱地址。
        :param title: 按标题过滤的关键字。
        :return: 邮件详情字典。
        """
        params = {"mailbox": mailbox, "title": title}
        return await self._get("getNewMail", params)
