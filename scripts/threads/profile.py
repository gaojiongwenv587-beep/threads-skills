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
    """提取用户主页的帖子列表。"""
    # 复用 feed 的 JSON 提取逻辑
    raw = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            for (const s of scripts) {
                try {
                    const d = JSON.parse(s.textContent);
                    if (JSON.stringify(d).includes('thread_items')) {
                        return s.textContent;
                    }
                } catch(e) {}
            }
            return null;
        })()
        """
    )

    if not raw:
        return []

    try:
        data = json.loads(raw)
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
        return posts[:max_posts]
    except Exception as e:
        logger.debug("提取用户帖子失败: %s", e)
        return []
