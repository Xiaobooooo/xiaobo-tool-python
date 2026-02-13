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
        resp = self.session.post(
            "https://x.com/i/api/graphql/oB-5XsHNAbjvARJEc8CZFw/CreateTweet",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise_response_error("发送推文", resp)

        data = resp.json()
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"发送推文失败: {errors[0].get('message', errors[0])}")
        result = json_get(data, "data/create_tweet/tweet_results/result")
        tweet_id = result["rest_id"]
        screen_name = json_get(result, "core/user_results/result/legacy/screen_name", "i")
        tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"
        logger.success("推文发送成功，推文链接: {}", tweet_url)
        return tweet_url

    def authorize_oauth2(self, auth_url: str) -> str:
        """
        批准 OAuth2 授权请求。

        :param auth_url: OAuth2 授权页面 URL。
        :return: 授权成功后的回调地址。
        :raises RuntimeError: 获取 auth_code 或授权失败时抛出。
        """
        api_url = (
            auth_url
            .replace("twitter.com", "x.com")
            .replace("/i/oauth2/authorize", "/i/api/2/oauth2/authorize")
        )
        response = self.session.get(api_url)
        try:
            auth_code = response.json().get("auth_code")
            if not auth_code:
                raise RuntimeError()
        except Exception:
            raise_response_error('获取授权auth_code', response)

        response = self.session.post("https://x.com/i/api/2/oauth2/authorize", json={"approval": "true", "code": auth_code})
        try:
            redirect_uri = response.json().get("redirect_uri")
            if not redirect_uri:
                raise RuntimeError()
        except Exception:
            raise_response_error('OAuth2授权', response)
        logger.success("OAuth2授权成功")
        return redirect_uri
