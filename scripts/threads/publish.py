"""Threads 内容发布。

分步流程（参考小红书 fill → 预览 → confirm 设计）：
  1. fill_thread()  — 填写内容，不发布，供用户预览
  2. click_publish() — 用户确认后点击发布按钮
  或直接调用 publish_thread() 一步完成。
"""

from __future__ import annotations

import logging
import time

from .cdp import Page
from .errors import ContentTooLongError, ElementNotFoundError, PublishError
from .human import sleep_random
from .selectors import COMPOSE_TRIGGER, FILE_INPUT, POST_BUTTON, THREAD_TEXT_INPUT
from .types import PublishContent
from .urls import HOME_URL

logger = logging.getLogger(__name__)

# Threads 字符上限
THREADS_MAX_CHARS = 500

# 便于模块外引用（interact.py 的 reply_thread 会用到）
_COMPOSE_SELECTORS = COMPOSE_TRIGGER
_TEXT_AREA_SELECTORS = THREAD_TEXT_INPUT
_PUBLISH_BUTTON_SELECTORS = POST_BUTTON


def publish_thread(page: Page, content: PublishContent) -> dict:
    """一步发布 Thread（填写 + 发布）。

    Args:
        page: CDP 页面对象。
        content: 发布内容。

    Returns:
        发布结果 dict。
    """
    fill_thread(page, content)
    return click_publish(page)


def fill_thread(page: Page, content: PublishContent) -> dict:
    """填写 Thread 内容，不立即发布（供预览确认）。

    Args:
        page: CDP 页面对象。
        content: 发布内容。

    Returns:
        状态信息 dict。

    Raises:
        ContentTooLongError: 内容超过 500 字符。
        PublishError: 找不到发布界面。
    """
    if len(content.content) > THREADS_MAX_CHARS:
        raise ContentTooLongError(len(content.content), THREADS_MAX_CHARS)

    logger.info("填写 Thread 内容（%d 字符）", len(content.content))

    # 确保在首页
    page.navigate(HOME_URL)
    page.wait_for_load(timeout=15)
    sleep_random(1500, 2500)

    # 点击发布入口
    compose_opened = False
    for selector in _COMPOSE_SELECTORS:
        if page.has_element(selector):
            page.click_element(selector)
            compose_opened = True
            logger.info("点击发布入口: %s", selector)
            break

    if not compose_opened:
        raise PublishError("未找到发布入口，请确认已登录且在首页")

    sleep_random(1000, 2000)

    # 找文本输入框
    text_area_found = False
    for selector in _TEXT_AREA_SELECTORS:
        if page.has_element(selector):
            # 使用 contenteditable 输入或 textarea
            tag = page.evaluate(
                f"document.querySelector({repr(selector)})?.tagName?.toLowerCase()"
            )
            if tag == "textarea":
                page.input_text(selector, content.content)
            else:
                page.input_content_editable(selector, content.content)
            text_area_found = True
            logger.info("输入内容到: %s (tag=%s)", selector, tag)
            break

    if not text_area_found:
        raise PublishError("未找到文本输入框，Threads 界面可能已更新")

    # 等待 dialog 完全展开（填文字后 Threads 会展开完整的发布弹框）
    sleep_random(1000, 1500)

    # 上传图片（如有）
    if content.image_paths:
        _attach_images(page, content.image_paths)

    return {
        "status": "filled",
        "message": (
            "内容已填写，请在浏览器中预览后调用 click-publish 发布。\n"
            "⚠️ 如输入框未出现，选择器可能已失效，运行 python scripts/inspector.py 重新探查。"
        ),
        "content_length": len(content.content),
    }


def click_publish(page: Page) -> dict:
    """点击发布按钮，完成发布。

    在 fill_thread 之后调用，需要用户已在浏览器中确认内容。

    Returns:
        发布结果 dict。

    Raises:
        PublishError: 找不到发布按钮或发布失败。
    """
    logger.info("点击发布按钮")

    # 策略1: dialog 内文字匹配（✅ 实测：填文字后会弹出 dialog，发布按钮在 dialog 内）
    # 优先在 dialog 内找，避免误点顶部 inline 的"发布"按钮
    published = page.evaluate(
        """
        (() => {
            const container = document.querySelector('div[role="dialog"]') || document;
            const els = container.querySelectorAll('[role="button"]');
            for (const el of els) {
                if ((el.textContent || '').trim() === '发布') {
                    el.scrollIntoView({block: 'center'});
                    const rect = el.getBoundingClientRect();
                    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
                }
            }
            return null;
        })()
        """
    )
    if published:
        import random as _random
        x = published["x"] + _random.uniform(-3, 3)
        y = published["y"] + _random.uniform(-3, 3)
        page.mouse_move(x, y)
        import time as _time
        _time.sleep(_random.uniform(0.05, 0.1))
        page.mouse_click(x, y)
        logger.info("已点击 dialog 内发布按钮 pos=(%.0f,%.0f)", x, y)
        sleep_random(2000, 3000)
        return {"status": "success", "message": "Thread 发布成功"}

    # 策略2: CSS 选择器候选（备用）
    for selector in _PUBLISH_BUTTON_SELECTORS:
        if page.has_element(selector):
            page.click_element(selector)
            logger.info("已点击发布按钮: %s", selector)
            sleep_random(2000, 3000)
            return {"status": "success", "message": "Thread 发布成功"}

    raise PublishError(
        "未找到发布按钮，可能界面已更新或内容未填写。"
        "请先调用 fill-thread，然后在浏览器中确认后再调用 click-publish。"
    )


def _attach_images(page: Page, image_paths: list[str]) -> None:
    """向 Thread 附加图片。

    与小红书 set_file_input 方法相同，通过 CDP DOM.setFileInputFiles 上传。
    """
    for selector in [FILE_INPUT, 'input[type="file"]']:
        if page.has_element(selector):
            # 过滤出实际存在的文件
            valid_paths = [p for p in image_paths if p]
            if valid_paths:
                try:
                    page.set_file_input(selector, valid_paths)
                    logger.info("已上传 %d 张图片", len(valid_paths))
                    sleep_random(1500, 3000)
                except Exception as e:
                    logger.warning("图片上传失败: %s", e)
            return

    logger.warning("未找到文件上传入口，跳过图片上传")
