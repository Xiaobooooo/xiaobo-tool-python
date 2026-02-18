import pytest

from xiaobo_tool.x import XClient, AsyncXClient


def test_x_send_tweet(auth_token):
    x = XClient(auth_token)
    tweet_url = x.send_tweet('This is test tweet 111')
    assert tweet_url


def test_x_get_user_by_screen_name(auth_token):
    x = XClient(auth_token)
    result = x.get_user_by_screen_name("0xiaobo888")
    assert result["rest_id"] == "1993385550867578880"


@pytest.mark.asyncio
async def test_async_x_get_user_by_screen_name(auth_token):
    x = await AsyncXClient.create(auth_token)
    result = await x.get_user_by_screen_name("0xiaobo888")
    assert result["rest_id"] == "1993385550867578880"


def test_x_follow_and_unfollow(auth_token):
    x = XClient(auth_token)
    user_id = "1993385550867578880"

    # 通过 user_id 关注
    data = x.follow(user_id)
    assert data["id_str"] == user_id


def test_x_follow_by_screen_name(auth_token):
    x = XClient(auth_token)

    # 通过 screen_name 取消关注
    data = x.unfollow(screen_name="0xiaobo888")
    assert data["id_str"] == "1993385550867578880"
