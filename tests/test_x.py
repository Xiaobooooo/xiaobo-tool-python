from xiaobo_tool.x import XClient


def test_x(auth_token):
    x = XClient(auth_token)
    tweet_url = x.send_tweet('This is test tweet 111')
    assert tweet_url
