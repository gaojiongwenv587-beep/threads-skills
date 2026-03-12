"""Threads 登录状态检查与登录流程。

Threads 使用 Instagram 账号登录，登录状态通过 Cookie 持久化在 Chrome Profile 中。
与小红书不同，无需手机验证码，登录后 session 在 Profile 目录长期保持。
"""

from __future__ import annotations

import json
import logging
import time

from .cdp import Browser, Page
from .errors import NotLoggedInError
from .human import sleep_random
from .selectors import LOGIN_INDICATORS, LOGOUT_INDICATORS
from .urls import HOME_URL, LOGIN_URL

logger = logging.getLogger(__name__)


def check_login(page: Page) -> dict:
    """检查当前登录状态。

    Returns:
        {
            "logged_in": bool,
            "username": str | None,
            "message": str,
        }
    """
    logger.info("检查 Threads 登录状态")
    page.navigate(HOME_URL)
    page.wait_for_load(timeout=15)
    time.sleep(2)

    # 检查是否被重定向到登录页
    current_url = page.evaluate("window.location.href") or ""
    if "/login" in current_url:
        return {
            "logged_in": False,
            "username": None,
            "message": "未登录，页面已跳转到登录页",
        }

    # 尝试从页面状态中提取用户名
    username = _extract_username(page)
    if username:
        return {
            "logged_in": True,
            "username": username,
            "message": f"已登录: @{username}",
        }

    # 未登录指示器优先检查（未登录首页也有帖子容器，会误判为已登录）
    for selector in LOGOUT_INDICATORS:
        if page.has_element(selector):
            return {
                "logged_in": False,
                "username": None,
                "message": "未登录，请执行 login 命令",
            }

    # 登录指示器
    for selector in LOGIN_INDICATORS:
        if page.has_element(selector):
            return {
                "logged_in": True,
                "username": None,
                "message": "已登录（用户名获取失败）",
            }

    return {
        "logged_in": False,
        "username": None,
        "message": "登录状态不明确，建议重新登录",
    }


def _extract_username(page: Page) -> str | None:
    """从页面 JS 状态或 DOM 中提取当前用户名。"""
    # 方法1：从 window.__reactFiber 或 Meta 全局状态中提取（如果暴露）
    candidates = [
        # Instagram/Meta 常见的全局状态变量
        "window._sharedData?.config?.viewer?.username",
        "window.__additionalData?.[Object.keys(window.__additionalData)[0]]?.data?.user?.username",
    ]
    for expr in candidates:
        try:
            val = page.evaluate(expr)
            if val and isinstance(val, str):
                return val
        except Exception:
            pass

    # 方法2：从 meta og:url 标签推断
    try:
        og_url = page.evaluate(
            'document.querySelector(\'meta[property="og:url"]\')?.content'
        )
        if og_url and "threads.net/@" in og_url:
            return og_url.split("/@")[1].split("/")[0]
    except Exception:
        pass

    return None


def open_login_page(page: Page) -> dict:
    """导航到 Threads 登录页，等待用户手动登录。

    Threads 登录需要 Instagram 账号，建议在有图形界面的 Chrome 中手动完成。
    登录后 Cookie 会持久化在 Chrome Profile，后续无需重复登录。

    Returns:
        状态信息。
    """
    logger.info("打开 Threads 登录页")
    page.navigate(LOGIN_URL)
    page.wait_for_load(timeout=15)
    sleep_random(1000, 2000)

    return {
        "status": "waiting",
        "message": (
            "已打开登录页面。请在浏览器中完成 Instagram 账号登录。\n"
            "登录成功后 Cookie 将自动保存，无需重复登录。\n"
            "登录完成后运行 check-login 确认状态。"
        ),
        "url": LOGIN_URL,
    }


def ensure_logged_in(page: Page) -> dict:
    """确认已登录，否则抛出异常。

    Returns:
        登录信息 dict。

    Raises:
        NotLoggedInError: 未登录时抛出。
    """
    status = check_login(page)
    if not status["logged_in"]:
        raise NotLoggedInError()
    return status
