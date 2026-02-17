import json
from typing import Optional, TYPE_CHECKING

from loguru import logger

from xiaobo_tool.utils import get_session, get_async_session, raise_response_error, json_get

if TYPE_CHECKING:
    from loguru import Logger
    from curl_cffi import Response

# Twitter 网页端公开的 Bearer Token
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


class _XClientBase:
    """XClient 和 AsyncXClient 的共享基类，包含 payload 构建和响应解析逻辑。"""

    def _setup_session(
            self,
            auth_token: str,
            ct0: Optional[str],
            proxy: Optional[str],
            _logger: Optional['Logger'],
            is_async: bool = False
    ):
        if not auth_token:
            raise ValueError("auth_token 不能为空。")
        self.logger = _logger if _logger else logger
        self.session = get_async_session(proxy) if is_async else get_session(proxy)
        self.session.cookies.set("auth_token", auth_token, domain=".x.com")
        self.session.headers.update({
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        })
        if ct0:
            self.ct0 = ct0
            self.session.cookies.set("ct0", ct0, domain=".x.com")
            self.session.headers.update({"X-Csrf-Token": ct0})

    @staticmethod
    def _check_response(resp: 'Response', action: str) -> dict:
        """检查 HTTP 状态码、账号锁定、errors 字段，返回解析后的 JSON。"""
        if resp.status_code != 200:
            raise_response_error(action, resp)
        data = resp.json()
        if "this account is temporarily locked" in resp.text.lower():
            raise RuntimeError("账号已被临时锁定(temporarily locked)")
        errors = data.get("errors")
        if errors:
            msg = errors[0].get("message", str(errors[0])) if isinstance(errors[0], dict) else str(errors[0])
            raise RuntimeError(f"{action}失败: {msg}")
        return data

    def _save_ct0(self, resp: 'Response') -> str:
        """从响应 cookies 中提取并保存 ct0。"""
        ct0 = self.session.cookies.get("ct0", domain=".x.com")
        if not ct0:
            raise RuntimeError(f"获取 ct0 失败, status={resp.status_code}")
        self.logger.success("ct0获取成功")
        self.ct0 = ct0
        self.session.headers.update({"X-Csrf-Token": ct0})
        return ct0

    # ---- payload 构建 ----

    @staticmethod
    def _tweet_payload(text: str) -> dict:
        return {
            "variables": {
                "tweet_text": text,
                "dark_request": False,
                "media": {"media_entities": [], "possibly_sensitive": False},
                "semantic_annotation_ids": [],
            },
            "features": {
                "communities_web_enable_tweet_community_results_fetch": True,
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "creator_subscriptions_quote_tweet_preview_enabled": False,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "articles_preview_enabled": True,
                "rweb_video_timestamps_enabled": True,
                "rweb_tipjar_consumption_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_enhance_cards_enabled": False,
            },
            "queryId": "oB-5XsHNAbjvARJEc8CZFw",
        }

    @staticmethod
    def _retweet_payload(tweet_id: str) -> dict:
        return {"variables": {"tweet_id": tweet_id, "dark_request": False}, "queryId": "LFho5rIi4xcKO90p9jwG7A"}

    @staticmethod
    def _undo_retweet_payload(tweet_id: str) -> dict:
        return {"variables": {"source_tweet_id": tweet_id, "dark_request": False}, "queryId": "iQtK4dl5hBmXewYZuEOKVw"}

    @staticmethod
    def _user_query_params(screen_name: str) -> dict:
        return {
            "variables": json.dumps({"screen_name": screen_name, "withGrokTranslatedBio": False}),
            "features": json.dumps({
                "hidden_profile_subscriptions_enabled": True,
                "profile_label_improvements_pcf_label_in_post_enabled": True,
                "responsive_web_profile_redirect_enabled": False,
                "rweb_tipjar_consumption_enabled": False,
                "verified_phone_label_enabled": False,
                "subscriptions_verification_info_is_identity_verified_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "highlights_tweets_tab_ui_enabled": True,
                "responsive_web_twitter_article_notes_tab_enabled": True,
                "subscriptions_feature_can_gift_premium": True,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
            }),
            "fieldToggles": json.dumps({"withPayments": False, "withAuxiliaryUserLabels": True}),
        }

    @staticmethod
    def _friendship_payload(user_id: str) -> dict:
        return {
            "include_profile_interstitial_type": "1", "include_blocking": "1",
            "include_blocked_by": "1", "include_followed_by": "1",
            "include_want_retweets": "1", "include_mute_edge": "1",
            "include_can_dm": "1", "include_can_media_tag": "1",
            "include_ext_is_blue_verified": "1", "include_ext_verified_type": "1",
            "include_ext_profile_image_shape": "1", "skip_status": "1",
            "user_id": user_id,
        }

    # ---- 结果解析 ----

    def _parse_tweet_result(self, data: dict) -> str:
        result = json_get(data, "data/create_tweet/tweet_results/result")
        tweet_id = result["rest_id"]
        screen_name = json_get(result, "core/user_results/result/legacy/screen_name", "i")
        tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"
        self.logger.success("推文发送成功，推文链接: {}", tweet_url)
        return tweet_url

    def _parse_user_result(self, data: dict, screen_name: str) -> dict:
        result = json_get(data, "data/user/result")
        if not result:
            raise RuntimeError(f"用户 @{screen_name} 不存在")
        self.logger.success("查询用户成功: @{}, user_id={}", screen_name, result["rest_id"])
        return result

    @staticmethod
    def _parse_oauth2(data: dict, field: str, action: str):
        value = data.get(field)
        if not value:
            raise RuntimeError(f"{action}失败: 响应中无 {field}")
        return value


class XClient(_XClientBase):
    """使用 auth_token 同步操作 X(Twitter) API 的客户端"""

    def __init__(
            self,
            auth_token: str,
            ct0: Optional[str] = None,
            proxy: Optional[str] = None,
            _logger: Optional['Logger'] = None
    ):
        """
        初始化 XClient。

        :param auth_token: X(Twitter) 的 auth_token。
        :param ct0: CSRF token，为 None 时自动获取。
        :param proxy: 代理地址。
        :param _logger: 自定义日志器，为 None 时使用默认 logger。
        """
        self._setup_session(auth_token, ct0, proxy, _logger)
        if not ct0:
            self.logger.warning("ct0 不存在，进行获取 ct0")
            self.get_ct0()

    def _request(self, method: str, url: str, action: str, **kwargs) -> dict:
        resp = self.session.request(method, url, **kwargs)
        return self._check_response(resp, action)

    def get_ct0(self) -> str:
        """获取 ct0 CSRF token。"""
        resp = self.session.get("https://api.x.com/1.1/account/settings.json")
        return self._save_ct0(resp)

    def _resolve_user_id(self, user_id: Optional[str] = None, screen_name: Optional[str] = None) -> str:
        if user_id:
            return user_id
        if screen_name:
            return self.get_user_by_screen_name(screen_name)["rest_id"]
        raise ValueError("user_id 和 screen_name 至少提供一个。")

    def send_tweet(self, text: str) -> str:
        """发送推文，返回推文链接。"""
        data = self._request("POST", "https://x.com/i/api/graphql/oB-5XsHNAbjvARJEc8CZFw/CreateTweet",
                             "发送推文", json=self._tweet_payload(text), headers={"Content-Type": "application/json"})
        return self._parse_tweet_result(data)

    def retweet(self, tweet_id: str) -> dict:
        """转推，返回转推结果字典。"""
        data = self._request("POST", "https://x.com/i/api/graphql/LFho5rIi4xcKO90p9jwG7A/CreateRetweet",
                             "转推", json=self._retweet_payload(tweet_id), headers={"Content-Type": "application/json"})
        self.logger.success("转推成功, tweet_id={}", tweet_id)
        return data

    def undo_retweet(self, tweet_id: str) -> dict:
        """取消转推，返回结果字典。"""
        data = self._request("POST", "https://x.com/i/api/graphql/iQtK4dl5hBmXewYZuEOKVw/DeleteRetweet",
                             "取消转推", json=self._undo_retweet_payload(tweet_id), headers={"Content-Type": "application/json"})
        self.logger.success("取消转推成功, tweet_id={}", tweet_id)
        return data

    def get_user_by_screen_name(self, screen_name: str) -> dict:
        """通过 screen_name 查询用户信息，返回包含 rest_id 的用户字典。"""
        data = self._request("GET", "https://x.com/i/api/graphql/AWbeRIdkLtqTRN7yL_H8yw/UserByScreenName",
                             "查询用户", params=self._user_query_params(screen_name))
        return self._parse_user_result(data, screen_name)

    def follow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """关注用户，user_id 和 screen_name 二选一。"""
        user_id = self._resolve_user_id(user_id, screen_name)
        data = self._request("POST", "https://x.com/i/api/1.1/friendships/create.json",
                             "关注用户", data=self._friendship_payload(user_id))
        self.logger.success("关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    def unfollow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """取消关注用户，user_id 和 screen_name 二选一。"""
        user_id = self._resolve_user_id(user_id, screen_name)
        data = self._request("POST", "https://x.com/i/api/1.1/friendships/destroy.json",
                             "取消关注用户", data=self._friendship_payload(user_id))
        self.logger.success("取消关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    def authorize_oauth2(self, auth_url: str) -> str:
        """批准 OAuth2 授权请求，返回回调地址。"""
        api_url = auth_url.replace("twitter.com", "x.com").replace("/i/oauth2/authorize", "/i/api/2/oauth2/authorize")
        data = self._request("GET", api_url, "获取授权auth_code")
        auth_code = self._parse_oauth2(data, "auth_code", "获取授权auth_code")
        data = self._request("POST", "https://x.com/i/api/2/oauth2/authorize", "OAuth2授权",
                             json={"approval": "true", "code": auth_code})
        redirect_uri = self._parse_oauth2(data, "redirect_uri", "OAuth2授权")
        self.logger.success("OAuth2授权成功")
        return redirect_uri


class AsyncXClient(_XClientBase):
    """使用 auth_token 异步操作 X(Twitter) API 的客户端"""

    def __init__(self, auth_token: str, ct0: Optional[str] = None,
                 proxy: Optional[str] = None, _logger: Optional['Logger'] = None):
        """
        初始化 AsyncXClient。不会自动获取 ct0，请使用 create() 或手动调用 get_ct0()。

        :param auth_token: X(Twitter) 的 auth_token。
        :param ct0: CSRF token，为 None 时需手动获取。
        :param proxy: 代理地址。
        :param _logger: 自定义日志器，为 None 时使用默认 logger。
        """
        self._setup_session(auth_token, ct0, proxy, _logger, is_async=True)

    @classmethod
    async def create(
            cls,
            auth_token: str,
            ct0: Optional[str] = None,
            proxy: Optional[str] = None,
            _logger: Optional['Logger'] = None
    ) -> 'AsyncXClient':
        """异步工厂方法，创建实例并自动获取 ct0。"""
        instance = cls(auth_token, ct0, proxy, _logger)
        if not ct0:
            instance.logger.warning("ct0 不存在，进行获取 ct0")
            await instance.get_ct0()
        return instance

    async def _request(self, method: str, url: str, action: str, **kwargs) -> dict:
        resp = await self.session.request(method, url, **kwargs)
        return self._check_response(resp, action)

    async def get_ct0(self) -> str:
        """获取 ct0 CSRF token。"""
        resp = await self.session.get("https://api.x.com/1.1/account/settings.json")
        return self._save_ct0(resp)

    async def _resolve_user_id(self, user_id: Optional[str] = None, screen_name: Optional[str] = None) -> str:
        if user_id:
            return user_id
        if screen_name:
            result = await self.get_user_by_screen_name(screen_name)
            return result["rest_id"]
        raise ValueError("user_id 和 screen_name 至少提供一个。")

    async def send_tweet(self, text: str) -> str:
        """发送推文，返回推文链接。"""
        data = await self._request("POST", "https://x.com/i/api/graphql/oB-5XsHNAbjvARJEc8CZFw/CreateTweet",
                                   "发送推文", json=self._tweet_payload(text), headers={"Content-Type": "application/json"})
        return self._parse_tweet_result(data)

    async def retweet(self, tweet_id: str) -> dict:
        """转推，返回转推结果字典。"""
        data = await self._request("POST", "https://x.com/i/api/graphql/LFho5rIi4xcKO90p9jwG7A/CreateRetweet",
                                   "转推", json=self._retweet_payload(tweet_id), headers={"Content-Type": "application/json"})
        self.logger.success("转推成功, tweet_id={}", tweet_id)
        return data

    async def undo_retweet(self, tweet_id: str) -> dict:
        """取消转推，返回结果字典。"""
        data = await self._request("POST", "https://x.com/i/api/graphql/iQtK4dl5hBmXewYZuEOKVw/DeleteRetweet",
                                   "取消转推", json=self._undo_retweet_payload(tweet_id), headers={"Content-Type": "application/json"})
        self.logger.success("取消转推成功, tweet_id={}", tweet_id)
        return data

    async def get_user_by_screen_name(self, screen_name: str) -> dict:
        """通过 screen_name 查询用户信息，返回包含 rest_id 的用户字典。"""
        data = await self._request("GET", "https://x.com/i/api/graphql/AWbeRIdkLtqTRN7yL_H8yw/UserByScreenName",
                                   "查询用户", params=self._user_query_params(screen_name))
        return self._parse_user_result(data, screen_name)

    async def follow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """关注用户，user_id 和 screen_name 二选一。"""
        user_id = await self._resolve_user_id(user_id, screen_name)
        data = await self._request("POST", "https://x.com/i/api/1.1/friendships/create.json",
                                   "关注用户", data=self._friendship_payload(user_id))
        self.logger.success("关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    async def unfollow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """取消关注用户，user_id 和 screen_name 二选一。"""
        user_id = await self._resolve_user_id(user_id, screen_name)
        data = await self._request("POST", "https://x.com/i/api/1.1/friendships/destroy.json",
                                   "取消关注用户", data=self._friendship_payload(user_id))
        self.logger.success("取消关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    async def authorize_oauth2(self, auth_url: str) -> str:
        """批准 OAuth2 授权请求，返回回调地址。"""
        api_url = auth_url.replace("twitter.com", "x.com").replace("/i/oauth2/authorize", "/i/api/2/oauth2/authorize")
        data = await self._request("GET", api_url, "获取授权auth_code")
        auth_code = self._parse_oauth2(data, "auth_code", "获取授权auth_code")
        data = await self._request("POST", "https://x.com/i/api/2/oauth2/authorize", "OAuth2授权",
                                   json={"approval": "true", "code": auth_code})
        redirect_uri = self._parse_oauth2(data, "redirect_uri", "OAuth2授权")
        self.logger.success("OAuth2授权成功")
        return redirect_uri
