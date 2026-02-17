import json
from typing import Optional, TYPE_CHECKING

from loguru import logger
from xiaobo_tool.utils import get_session, raise_response_error, json_get

if TYPE_CHECKING:
    from loguru import Logger

# Twitter 网页端公开的 Bearer Token
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


class XClient:
    """使用 auth_token 操作 X(Twitter) API 的客户端"""

    def __init__(
            self,
            auth_token: str,
            ct0: Optional[str] = None,
            proxy: Optional[str] = None,
            _logger: Optional['Logger'] = None,
    ):
        """
        初始化 XClient。

        :param auth_token: X(Twitter) 的 auth_token。
        :param ct0: CSRF token，为 None 时自动获取。
        :param proxy: 代理地址。
        :param _logger: 自定义日志器，为 None 时使用默认 logger。
        :raises ValueError: auth_token 为空时抛出。
        """
        if not auth_token:
            raise ValueError("auth_token 不能为空。")

        self.logger = _logger if _logger else logger
        self.session = get_session(proxy)
        self.session.cookies.set("auth_token", auth_token, domain=".x.com")
        self.session.headers.update({
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        })
        if ct0:
            self.ct0 = ct0
            self.session.cookies.set("ct0", self.ct0, domain=".x.com")
            self.session.headers.update({"X-Csrf-Token": ct0})
        else:
            self.logger.warning("ct0 不存在，进行获取 ct0")
            self.get_ct0()

    def get_ct0(self) -> str:
        """
        获取 ct0 CSRF token。

        :return: ct0 token 字符串。
        :raises RuntimeError: 获取失败时抛出。
        """
        resp = self.session.get("https://api.x.com/1.1/account/settings.json")
        ct0 = self.session.cookies.get("ct0", domain=".x.com")
        if not ct0:
            raise RuntimeError(f"获取 ct0 失败, status={resp.status_code}")
        logger.success("ct0获取成功")
        self.ct0 = ct0
        self.session.headers.update({"X-Csrf-Token": ct0})
        return ct0

    def send_tweet(self, text: str) -> str:
        """
        发送推文。

        :param text: 推文内容。
        :return: 推文链接。
        :raises HTTPError: 请求失败时抛出。
        :raises RuntimeError: API 返回业务错误时抛出。
        """
        payload = {
            "variables": {
                "tweet_text": text,
                "dark_request": False,
                "media": {
                    "media_entities": [],
                    "possibly_sensitive": False,
                },
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
        data = self._request(
            "POST",
            "https://x.com/i/api/graphql/oB-5XsHNAbjvARJEc8CZFw/CreateTweet",
            "发送推文",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = json_get(data, "data/create_tweet/tweet_results/result")
        tweet_id = result["rest_id"]
        screen_name = json_get(result, "core/user_results/result/legacy/screen_name", "i")
        tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"
        logger.success("推文发送成功，推文链接: {}", tweet_url)
        return tweet_url

    def retweet(self, tweet_id: str) -> dict:
        """
        转推。

        :param tweet_id: 要转推的推文 ID。
        :return: 转推结果字典。
        :raises HTTPError: 请求失败时抛出。
        :raises RuntimeError: API 返回业务错误时抛出。
        """
        payload = {
            "variables": {
                "tweet_id": tweet_id,
                "dark_request": False,
            },
            "queryId": "LFho5rIi4xcKO90p9jwG7A",
        }
        data = self._request(
            "POST",
            "https://x.com/i/api/graphql/LFho5rIi4xcKO90p9jwG7A/CreateRetweet",
            "转推",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        logger.success("转推成功, tweet_id={}", tweet_id)
        return data

    def undo_retweet(self, tweet_id: str) -> dict:
        """
        取消转推。

        :param tweet_id: 要取消转推的推文 ID。
        :return: 取消转推结果字典。
        :raises HTTPError: 请求失败时抛出。
        :raises RuntimeError: API 返回业务错误时抛出。
        """
        payload = {
            "variables": {
                "source_tweet_id": tweet_id,
                "dark_request": False,
            },
            "queryId": "iQtK4dl5hBmXewYZuEOKVw",
        }
        data = self._request(
            "POST",
            "https://x.com/i/api/graphql/iQtK4dl5hBmXewYZuEOKVw/DeleteRetweet",
            "取消转推",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        logger.success("取消转推成功, tweet_id={}", tweet_id)
        return data

    def get_user_by_screen_name(self, screen_name: str) -> dict:
        """
        通过 screen_name 查询用户信息。

        :param screen_name: 用户的 screen_name（不含 @）。
        :return: 用户信息字典，包含 rest_id 等字段。
        :raises HTTPError: 请求失败时抛出。
        :raises RuntimeError: 用户不存在时抛出。
        """
        params = {
            "variables": json.dumps({
                "screen_name": screen_name,
                "withGrokTranslatedBio": False,
            }),
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
            "fieldToggles": json.dumps({
                "withPayments": False,
                "withAuxiliaryUserLabels": True,
            }),
        }
        data = self._request(
            "GET",
            "https://x.com/i/api/graphql/AWbeRIdkLtqTRN7yL_H8yw/UserByScreenName",
            "查询用户",
            params=params,
        )
        result = json_get(data, "data/user/result")
        if not result:
            raise RuntimeError(f"用户 @{screen_name} 不存在")
        logger.success("查询用户成功: @{}, user_id={}", screen_name, result["rest_id"])
        return result

    def _request(self, method: str, url: str, action: str, **kwargs) -> dict:
        """
        统一请求方法，自动检查 HTTP 状态码和 errors 字段。

        :param method: 请求方法（GET/POST）。
        :param url: 请求 URL。
        :param action: 操作描述，用于错误信息。
        :param kwargs: 传递给 session.request 的额外参数。
        :return: 响应 JSON 字典。
        :raises HTTPError: HTTP 状态码非 200 时抛出。
        :raises RuntimeError: 响应包含 errors 时抛出。
        """
        resp = self.session.request(method, url, **kwargs)
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

    def _resolve_user_id(self, user_id: Optional[str] = None, screen_name: Optional[str] = None) -> str:
        """
        解析用户 ID，若仅提供 screen_name 则自动查询。

        :param user_id: 用户 ID。
        :param screen_name: 用户 screen_name。
        :return: 用户 ID 字符串。
        :raises ValueError: 两个参数都为空时抛出。
        """
        if user_id:
            return user_id
        if screen_name:
            return self.get_user_by_screen_name(screen_name)["rest_id"]
        raise ValueError("user_id 和 screen_name 至少提供一个。")

    def follow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """
        关注用户。

        :param user_id: 目标用户 ID。
        :param screen_name: 目标用户 screen_name，与 user_id 二选一。
        :return: 用户信息字典。
        :raises HTTPError: 请求失败时抛出。
        """
        user_id = self._resolve_user_id(user_id, screen_name)
        payload = {
            "include_profile_interstitial_type": "1",
            "include_blocking": "1",
            "include_blocked_by": "1",
            "include_followed_by": "1",
            "include_want_retweets": "1",
            "include_mute_edge": "1",
            "include_can_dm": "1",
            "include_can_media_tag": "1",
            "include_ext_is_blue_verified": "1",
            "include_ext_verified_type": "1",
            "include_ext_profile_image_shape": "1",
            "skip_status": "1",
            "user_id": user_id,
        }
        data = self._request(
            "POST",
            "https://x.com/i/api/1.1/friendships/create.json",
            "关注用户",
            data=payload,
        )
        logger.success("关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    def unfollow(self, user_id: Optional[str] = None, *, screen_name: Optional[str] = None) -> dict:
        """
        取消关注用户。

        :param user_id: 目标用户 ID。
        :param screen_name: 目标用户 screen_name，与 user_id 二选一。
        :return: 用户信息字典。
        :raises HTTPError: 请求失败时抛出。
        """
        user_id = self._resolve_user_id(user_id, screen_name)
        payload = {
            "include_profile_interstitial_type": "1",
            "include_blocking": "1",
            "include_blocked_by": "1",
            "include_followed_by": "1",
            "include_want_retweets": "1",
            "include_mute_edge": "1",
            "include_can_dm": "1",
            "include_can_media_tag": "1",
            "include_ext_is_blue_verified": "1",
            "include_ext_verified_type": "1",
            "include_ext_profile_image_shape": "1",
            "skip_status": "1",
            "user_id": user_id,
        }
        data = self._request(
            "POST",
            "https://x.com/i/api/1.1/friendships/destroy.json",
            "取消关注用户",
            data=payload,
        )
        logger.success("取消关注用户成功: @{}", data.get("screen_name", user_id))
        return data

    def authorize_oauth2(self, auth_url: str) -> str:
        """
        批准 OAuth2 授权请求。

        :param auth_url: OAuth2 授权页面 URL。
        :return: 授权成功后的回调地址。
        :raises RuntimeError: 获取 auth_code 或授权失败时抛出。
        """
        api_url = auth_url.replace("twitter.com", "x.com").replace("/i/oauth2/authorize", "/i/api/2/oauth2/authorize")
        data = self._request("GET", api_url, "获取授权auth_code")
        auth_code = data.get("auth_code")
        if not auth_code:
            raise RuntimeError(f"获取授权auth_code失败: 响应中无 auth_code")

        data = self._request("POST", "https://x.com/i/api/2/oauth2/authorize", "OAuth2授权",
                             json={"approval": "true", "code": auth_code})
        redirect_uri = data.get("redirect_uri")
        if not redirect_uri:
            raise RuntimeError(f"OAuth2授权失败: 响应中无 redirect_uri")
        logger.success("OAuth2授权成功")
        return redirect_uri
