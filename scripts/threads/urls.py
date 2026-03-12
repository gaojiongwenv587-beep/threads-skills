"""Threads 平台 URL 常量。"""

BASE_URL = "https://www.threads.net"
HOME_URL = f"{BASE_URL}/"
SEARCH_URL = f"{BASE_URL}/search"
LOGIN_URL = f"{BASE_URL}/login"


def profile_url(username: str) -> str:
    """用户主页 URL。"""
    username = username.lstrip("@")
    return f"{BASE_URL}/@{username}"


def post_url(username: str, post_id: str) -> str:
    """单条 Thread URL。"""
    username = username.lstrip("@")
    return f"{BASE_URL}/@{username}/post/{post_id}"
