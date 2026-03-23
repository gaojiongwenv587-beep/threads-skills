"""Threads 用户主页获取。"""

from __future__ import annotations

import json
import logging
import time

from .cdp import Page
from .feed import _parse_single_post, _try_extract_from_scripts
from .human import navigation_delay
from .types import ThreadPost, ThreadsUser, UserProfile
from .urls import profile_url

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


def _extract_user_posts(page: Page, max_posts: int) -> list[ThreadPost]:
    """提取用户主页的帖子列表，滚动加载直到满足数量要求。"""
    from .human import sleep_random

    seen_keys: set[str] = set()
    all_posts: list[ThreadPost] = []
    max_scrolls = max(10, max_posts // 4 * 3)
    stall_count = 0

    for scroll_i in range(max_scrolls):
        # 遍历所有含 thread_items 的 script 标签
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

        batch: list[ThreadPost] = []
        if scripts_json:
            try:
                scripts = json.loads(scripts_json)
                for raw in scripts:
                    try:
                        data = json.loads(raw)
                        batch.extend(_parse_posts_from_json(data, max_posts))
                    except Exception as e:
                        logger.debug("解析用户帖子 JSON 失败: %s", e)
            except Exception:
                pass

        prev_len = len(all_posts)
        for p in batch:
            key = p.post_id or p.url or p.content[:50]
            if key and key not in seen_keys:
                seen_keys.add(key)
                all_posts.append(p)

        new_count = len(all_posts) - prev_len
        logger.info("用户帖子第 %d 轮后共 %d 条（新增 %d）", scroll_i + 1, len(all_posts), new_count)

        if len(all_posts) >= max_posts:
            break

        if new_count == 0:
            stall_count += 1
            if stall_count >= 3:
                logger.info("连续 %d 次无新增，停止滚动", stall_count)
                break
        else:
            stall_count = 0

        prev_height = page.evaluate("document.body.scrollHeight")
        page.scroll_to_bottom()
        for _ in range(12):
            sleep_random(400, 600)
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
