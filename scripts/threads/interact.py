"""Threads 社交互动：点赞、转发、回复、关注。"""

from __future__ import annotations

import logging
import time

from .cdp import Page
from .errors import ElementNotFoundError, PublishError
from .human import sleep_random
from .selectors import FOLLOW_BUTTON, LIKE_BUTTON, LIKE_BUTTON_ACTIVE, REPLY_BUTTON, REPOST_BUTTON
from .types import ActionResult, PublishContent
from .urls import BASE_URL, profile_url

logger = logging.getLogger(__name__)


def like_thread(page: Page, post_url: str) -> ActionResult:
    """对指定 Thread 点赞（或取消点赞）。

    Args:
        page: CDP 页面对象。
        post_url: Thread 完整 URL。

    Returns:
        ActionResult 包含操作结果。
    """
    logger.info("点赞 Thread: %s", post_url)
    page.navigate(post_url)
    page.wait_for_load(timeout=15)
    sleep_random(1500, 2500)

    for selector in [LIKE_BUTTON, LIKE_BUTTON_ACTIVE]:
        if page.has_element(selector):
            # 记录点赞前状态
            current_label = page.get_element_attribute(selector, "aria-label") or ""
            page.click_element(selector)
            sleep_random(500, 1000)

            action = "取消点赞" if "Unlike" in current_label else "点赞"
            logger.info("%s 成功", action)
            return ActionResult(
                post_id=post_url,
                success=True,
                message=f"{action}成功",
            )

    return ActionResult(
        post_id=post_url,
        success=False,
        message="未找到点赞按钮，请确认帖子 URL 正确",
    )


def repost_thread(page: Page, post_url: str) -> ActionResult:
    """转发 Thread（Repost）。

    Args:
        page: CDP 页面对象。
        post_url: Thread 完整 URL。

    Returns:
        ActionResult 包含操作结果。
    """
    logger.info("转发 Thread: %s", post_url)
    page.navigate(post_url)
    page.wait_for_load(timeout=15)
    sleep_random(1500, 2500)

    for selector in [REPOST_BUTTON]:
        if page.has_element(selector):
            page.click_element(selector)
            sleep_random(500, 1000)

            # 确认转发弹窗中的 "Repost" 按钮
            confirm_selectors = [
                '[role="dialog"] [aria-label="Repost"]',
                '[role="dialog"] div[role="button"]',
            ]
            for confirm in confirm_selectors:
                if page.has_element(confirm):
                    page.click_element(confirm)
                    sleep_random(500, 1000)
                    break

            return ActionResult(
                post_id=post_url,
                success=True,
                message="转发成功",
            )

    return ActionResult(
        post_id=post_url,
        success=False,
        message="未找到转发按钮",
    )


def reply_thread(page: Page, post_url: str, content: str) -> ActionResult:
    """回复 Thread。

    Args:
        page: CDP 页面对象。
        post_url: 要回复的 Thread URL。
        content: 回复内容。

    Returns:
        ActionResult 包含操作结果。
    """
    from .publish import THREADS_MAX_CHARS, _TEXT_AREA_SELECTORS

    if len(content) > THREADS_MAX_CHARS:
        return ActionResult(
            post_id=post_url,
            success=False,
            message=f"回复内容超过 {THREADS_MAX_CHARS} 字符限制",
        )

    logger.info("回复 Thread: %s", post_url)
    page.navigate(post_url)
    page.wait_for_load(timeout=15)
    sleep_random(1500, 2500)

    reply_clicked = False
    for selector in [REPLY_BUTTON]:
        if page.has_element(selector):
            page.click_element(selector)
            reply_clicked = True
            sleep_random(800, 1500)
            break

    if not reply_clicked:
        # 有些帖子可以直接在底部的文本框回复
        logger.info("未找到回复按钮，尝试直接在文本框回复")

    # 找回复文本框并输入
    for selector in _TEXT_AREA_SELECTORS:
        if page.has_element(selector):
            tag = page.evaluate(
                f"document.querySelector({repr(selector)})?.tagName?.toLowerCase()"
            )
            if tag == "textarea":
                page.input_text(selector, content)
            else:
                page.input_content_editable(selector, content)
            sleep_random(500, 800)

            # 提交回复：优先在 dialog 内按文字"回复"找按钮（与发布按钮同逻辑）
            sleep_random(800, 1200)
            submitted = page.evaluate(
                """
                (() => {
                    const container = document.querySelector('div[role="dialog"]') || document;
                    const els = container.querySelectorAll('[role="button"]');
                    for (const el of els) {
                        const t = (el.textContent || '').trim();
                        if (t === '回复' || t === 'Reply' || t === '发布' || t === 'Post') {
                            el.scrollIntoView({block: 'center'});
                            const rect = el.getBoundingClientRect();
                            return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
                        }
                    }
                    return null;
                })()
                """
            )
            if submitted:
                import random as _r, time as _t
                x = submitted["x"] + _r.uniform(-3, 3)
                y = submitted["y"] + _r.uniform(-3, 3)
                page.mouse_move(x, y)
                _t.sleep(_r.uniform(0.05, 0.1))
                page.mouse_click(x, y)
                # 等待 dialog 关闭（发布完成的标志），最多等 15 秒
                for _ in range(30):
                    _t.sleep(0.5)
                    still_open = page.evaluate(
                        "!!document.querySelector('div[role=\"dialog\"]')"
                    )
                    if not still_open:
                        break
                sleep_random(500, 800)
                return ActionResult(
                    post_id=post_url,
                    success=True,
                    message="回复发布成功",
                )

            return ActionResult(
                post_id=post_url,
                success=False,
                message="内容已输入但未找到提交按钮",
            )

    return ActionResult(
        post_id=post_url,
        success=False,
        message="未找到回复文本框",
    )


def follow_user(page: Page, username: str) -> ActionResult:
    """关注用户。

    Args:
        page: CDP 页面对象。
        username: 用户名（可带或不带 @）。

    Returns:
        ActionResult 包含操作结果。
    """
    username = username.lstrip("@")
    url = profile_url(username)
    logger.info("关注用户: @%s", username)

    page.navigate(url)
    page.wait_for_load(timeout=15)
    sleep_random(1500, 2500)

    for selector in [FOLLOW_BUTTON]:
        if page.has_element(selector):
            btn_text = page.get_element_text(selector) or ""
            if "Following" in btn_text or "Unfollow" in btn_text:
                return ActionResult(
                    post_id=username,
                    success=True,
                    message=f"已关注 @{username}（之前已关注）",
                )
            page.click_element(selector)
            sleep_random(800, 1500)
            return ActionResult(
                post_id=username,
                success=True,
                message=f"已关注 @{username}",
            )

    return ActionResult(
        post_id=username,
        success=False,
        message=f"未找到关注按钮（@{username}），请确认用户名正确",
    )
