"""Threads 用户主页获取。"""

from __future__ import annotations

import json
import logging
import time

from .cdp import Page
from .feed import _parse_single_post, _try_extract_from_scripts
from .human import navigation_delay
from .types import ThreadPost, ThreadsUser, UserProfile
from .urls import profile_url, replies_url

logger = logging.getLogger(__name__)


def get_user_profile(page: Page, username: str, max_posts: int = 12) -> UserProfile:
    """获取用户主页信息及帖子列表。

    Args:
        page: CDP 页面对象。
        username: 用户名（可带或不带 @）。
        max_posts: 最多返回帖子数。

    Returns:
        UserProfile 包含用户信息和帖子。
    """
    username = username.lstrip("@")
    url = profile_url(username)
    logger.info("获取用户主页: @%s", username)

    page.navigate(url)
    page.wait_for_load(timeout=20)
    navigation_delay()

    user = _extract_user_info(page, username)
    posts = _extract_user_posts(page, max_posts)

    return UserProfile(user=user, posts=posts)


_INTERCEPTOR_JS = """
window.__threadsCaptured__ = [];
const _origFetch = window.fetch;
window.fetch = async function(...args) {
    const resp = await _origFetch(...args);
    try {
        const clone = resp.clone();
        const text = await clone.text();
        if (text.includes('thread_items')) {
            window.__threadsCaptured__.push(text);
        }
    } catch(e) {}
    return resp;
};
const _origXHRSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send = function() {
    this.addEventListener('load', function() {
        try {
            if (this.responseText && this.responseText.includes('thread_items')) {
                window.__threadsCaptured__.push(this.responseText);
            }
        } catch(e) {}
    });
    return _origXHRSend.apply(this, arguments);
};
"""


def get_user_replies(page: Page, username: str, max_posts: int = 20) -> list[ThreadPost]:
    """获取用户「回复」Tab 的历史回复列表。

    Args:
        page: CDP 页面对象。
        username: 用户名（可带或不带 @）。
        max_posts: 最多返回回复数。

    Returns:
        ThreadPost 列表（每条是用户发出的回复帖）。
    """
    username = username.lstrip("@")
    url = replies_url(username)
    logger.info("获取用户历史回复: @%s/replies", username)

    # 注入拦截器必须在 navigate 之前
    page._send_session("Page.addScriptToEvaluateOnNewDocument", {"source": _INTERCEPTOR_JS})
    page.navigate(url)
    page.wait_for_load(timeout=20)
    navigation_delay()

    return _extract_user_posts(page, max_posts, use_interceptor=True)


def get_user_replies_grouped(page: Page, username: str) -> list[list[ThreadPost]]:
    """获取用户「回复」Tab 的所有回复，以 thread 分组（原贴 + 回复 配对）。

    Args:
        page: CDP 页面对象。
        username: 用户名（可带或不带 @）。

    Returns:
        list of groups，每组是一个 thread_items 内的帖子列表（[原贴, 回复] 或仅回复）。
    """
    username = username.lstrip("@")
    logger.info("获取用户全部回复（分组模式）: @%s/replies", username)
    return _extract_all_reply_groups(page, username)


def _extract_user_info(page: Page, username: str) -> ThreadsUser:
    """从页面中提取用户基本信息。"""
    # 尝试从 JSON 数据提取
    raw = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            for (const s of scripts) {
                try {
                    const d = JSON.parse(s.textContent);
                    const str = JSON.stringify(d);
                    if (str.includes('"username"') && str.includes('"follower_count"')) {
                        return s.textContent;
                    }
                } catch(e) {}
            }
            return null;
        })()
        """
    )

    if raw:
        try:
            data = json.loads(raw)
            user = _find_user_in_json(data, username)
            if user:
                return user
        except Exception as e:
            logger.debug("解析用户 JSON 失败: %s", e)

    # 回退：从 DOM 提取
    return _extract_user_from_dom(page, username)


def _find_user_in_json(obj: object, username: str) -> ThreadsUser | None:
    """递归在 JSON 中查找用户数据。"""
    if isinstance(obj, dict):
        if obj.get("username") == username and "pk" in obj:
            return ThreadsUser(
                user_id=str(obj.get("pk", "")),
                username=obj.get("username", ""),
                display_name=obj.get("full_name", ""),
                avatar_url=obj.get("profile_pic_url", ""),
                is_verified=obj.get("is_verified", False),
                follower_count=str(obj.get("follower_count", "")),
                following_count=str(obj.get("following_count", "")),
                bio=obj.get("biography", ""),
            )
        for v in obj.values():
            result = _find_user_in_json(v, username)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_user_in_json(item, username)
            if result:
                return result
    return None


def _extract_user_from_dom(page: Page, username: str) -> ThreadsUser:
    """从 DOM 提取用户信息（降级方案）。"""
    data = page.evaluate(
        """
        (() => {
            const nameEl = document.querySelector(
                'h1, h2, [class*="username"], [class*="displayName"]'
            );
            const bioEl = document.querySelector(
                '[class*="bio"], [class*="description"], [dir="auto"]'
            );
            const avatarEl = document.querySelector(
                'img[alt*="profile"], img[class*="avatar"]'
            );
            // 粉丝数：在 span[dir="auto"] 中找包含"位粉丝"或"followers"的文本
            let followerCount = '';
            document.querySelectorAll('span[dir="auto"]').forEach(s => {
                const t = s.textContent?.trim() || '';
                if (!followerCount && (t.includes('位粉丝') || t.includes('followers'))) {
                    followerCount = t;
                }
            });
            return JSON.stringify({
                displayName: nameEl?.textContent?.trim() || '',
                bio: bioEl?.textContent?.trim() || '',
                avatarUrl: avatarEl?.src || '',
                followerCount,
            });
        })()
        """
    )

    if data:
        try:
            d = json.loads(data)
            return ThreadsUser(
                username=username,
                display_name=d.get("displayName", ""),
                bio=d.get("bio", ""),
                avatar_url=d.get("avatarUrl", ""),
                follower_count=d.get("followerCount", ""),
            )
        except Exception:
            pass

    return ThreadsUser(username=username)


def _extract_user_posts(
    page: Page, max_posts: int, use_interceptor: bool = False
) -> list[ThreadPost]:
    """提取用户主页的帖子列表，滚动加载直到满足数量要求。"""
    from .human import sleep_random

    seen_keys: set[str] = set()
    all_posts: list[ThreadPost] = []
    max_scrolls = max(10, max_posts // 4 * 3)
    stall_count = 0

    def _ingest(raw: str) -> None:
        try:
            data = json.loads(raw)
            for p in _parse_posts_from_json(data, max_posts):
                key = p.post_id or p.url or p.content[:50]
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    all_posts.append(p)
        except Exception as e:
            logger.debug("解析帖子 JSON 失败: %s", e)

    for scroll_i in range(max_scrolls):
        prev_len = len(all_posts)

        # 1) 从 script 标签读取（SSR 首屏数据）
        scripts_json = page.evaluate(
            """
            (() => {
                const scripts = document.querySelectorAll('script[type="application/json"]');
                const results = [];
                for (const s of scripts) {
                    const t = s.textContent || '';
                    if (t.length > 500 && t.includes('thread_items')) results.push(t);
                }
                results.sort((a, b) => b.length - a.length);
                return JSON.stringify(results);
            })()
            """
        )
        if scripts_json:
            try:
                for raw in json.loads(scripts_json):
                    _ingest(raw)
            except Exception:
                pass

        # 2) 从拦截器缓冲区读取（滚动懒加载的 XHR/fetch 数据）
        if use_interceptor:
            try:
                captured_json = page.evaluate(
                    "JSON.stringify(window.__threadsCaptured__ || [])"
                )
                if captured_json:
                    for raw in json.loads(captured_json):
                        _ingest(raw)
                    page.evaluate("window.__threadsCaptured__ = []")
            except Exception as e:
                logger.debug("读取拦截器缓冲区失败: %s", e)

        new_count = len(all_posts) - prev_len
        logger.info("用户帖子第 %d 轮后共 %d 条（新增 %d）", scroll_i + 1, len(all_posts), new_count)

        if len(all_posts) >= max_posts:
            break

        if new_count == 0:
            stall_count += 1
            if stall_count >= 5:
                logger.info("连续 %d 次无新增，停止滚动", stall_count)
                break
        else:
            stall_count = 0

        prev_height = page.evaluate("document.body.scrollHeight")
        page.scroll_to_bottom()
        for _ in range(15):
            sleep_random(500, 800)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > prev_height:
                break

    return all_posts[:max_posts]


def _parse_posts_from_json(data: object, max_posts: int) -> list[ThreadPost]:
    """递归从 JSON 中提取帖子。"""
    posts: list[ThreadPost] = []

    def _find(obj: object) -> None:
        if len(posts) >= max_posts:
            return
        if isinstance(obj, dict):
            if "thread_items" in obj:
                for item in obj["thread_items"]:
                    if isinstance(item, dict) and "post" in item:
                        post = _parse_single_post(item["post"])
                        if post:
                            posts.append(post)
            else:
                for v in obj.values():
                    _find(v)
        elif isinstance(obj, list):
            for item in obj:
                _find(item)

    _find(data)
    return posts


def _extract_all_reply_groups(page: Page, username: str) -> list[list[ThreadPost]]:
    """提取所有 thread 分组（原贴 + 回复 配对）。

    策略：
    1. 在页面加载前注入 fetch/XHR 拦截器捕获所有包含 thread_items 的 API 响应
    2. 页面加载后从 script 标签提取初始数据
    3. 合并去重
    """
    from .human import sleep_random

    # 注入拦截器（在下次导航时生效）
    try:
        page._send_session("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                window.__threadsCaptured__ = [];
                const _origFetch = window.fetch;
                window.fetch = async function(...args) {
                    const resp = await _origFetch(...args);
                    try {
                        const clone = resp.clone();
                        const text = await clone.text();
                        if (text.includes('thread_items')) {
                            window.__threadsCaptured__.push(text);
                        }
                    } catch(e) {}
                    return resp;
                };
                const _origXHRSend = window.XMLHttpRequest.prototype.send;
                window.XMLHttpRequest.prototype.send = function() {
                    this.addEventListener('load', function() {
                        try {
                            if (this.responseText && this.responseText.includes('thread_items')) {
                                window.__threadsCaptured__.push(this.responseText);
                            }
                        } catch(e) {}
                    });
                    return _origXHRSend.apply(this, arguments);
                };
            """
        })
    except Exception as e:
        logger.debug("注入拦截器失败（忽略）: %s", e)

    # 重新导航以触发拦截器
    url = __import__("threads.urls", fromlist=["replies_url"]).replies_url(username)
    page.navigate(url)
    page.wait_for_load(timeout=20)
    from .human import navigation_delay
    navigation_delay()

    seen_group_keys: set[str] = set()
    all_groups: list[list[ThreadPost]] = []

    def _add_groups_from_raw(raw: str) -> int:
        new = 0
        try:
            data = json.loads(raw)
            for group in _parse_thread_groups_from_json(data):
                if not group:
                    continue
                key = group[0].post_id or group[0].url or group[0].content[:50]
                if key and key not in seen_group_keys:
                    seen_group_keys.add(key)
                    all_groups.append(group)
                    new += 1
        except Exception as e:
            logger.debug("解析分组 JSON 失败: %s", e)
        return new

    # 1. 从 fetch/XHR 拦截器获取 API 响应
    captured_raw = page.evaluate("JSON.stringify(window.__threadsCaptured__ || [])")
    if captured_raw:
        try:
            for raw in json.loads(captured_raw):
                _add_groups_from_raw(raw)
        except Exception:
            pass
    logger.info("从 API 拦截器获取 %d 组", len(all_groups))

    # 2. 从 script 标签获取初始 SSR 数据
    scripts_json = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            const results = [];
            for (const s of scripts) {
                const t = s.textContent || '';
                if (t.length > 500 && t.includes('thread_items')) results.push(t);
            }
            results.sort((a, b) => b.length - a.length);
            return JSON.stringify(results);
        })()
        """
    )
    if scripts_json:
        try:
            for raw in json.loads(scripts_json):
                _add_groups_from_raw(raw)
        except Exception:
            pass
    logger.info("合并 script 标签后共 %d 组", len(all_groups))

    # 3. 尝试滚动加载更多（最多 10 轮，3 次无新增停止）
    stall_count = 0
    for scroll_i in range(10):
        prev_height = page.evaluate("document.body.scrollHeight")
        page.scroll_to_bottom()
        for _ in range(15):
            sleep_random(400, 700)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > prev_height:
                break

        # 检查是否有新的 API 响应
        captured_raw = page.evaluate("JSON.stringify(window.__threadsCaptured__ || [])")
        new_count = 0
        if captured_raw:
            try:
                for raw in json.loads(captured_raw):
                    new_count += _add_groups_from_raw(raw)
            except Exception:
                pass
        # 重置拦截缓冲区
        page.evaluate("window.__threadsCaptured__ = []")

        logger.info("滚动第 %d 轮，新增 %d 组，共 %d 组", scroll_i + 1, new_count, len(all_groups))
        if new_count == 0:
            stall_count += 1
            if stall_count >= 3:
                logger.info("连续 3 次无新增，停止滚动")
                break
        else:
            stall_count = 0

    return all_groups


def _parse_thread_groups_from_json(data: object) -> list[list[ThreadPost]]:
    """递归从 JSON 中提取 thread 分组（保留 thread_items 配对结构）。"""
    groups: list[list[ThreadPost]] = []

    def _find(obj: object) -> None:
        if isinstance(obj, dict):
            if "thread_items" in obj:
                group: list[ThreadPost] = []
                for item in obj["thread_items"]:
                    if isinstance(item, dict) and "post" in item:
                        post = _parse_single_post(item["post"])
                        if post:
                            group.append(post)
                if group:
                    groups.append(group)
            else:
                for v in obj.values():
                    _find(v)
        elif isinstance(obj, list):
            for item in obj:
                _find(item)

    _find(data)
    return groups
