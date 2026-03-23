"""Threads 搜索功能。"""

from __future__ import annotations

import json
import logging
import time

from .cdp import Page
from .feed import _parse_single_post
from .human import navigation_delay, sleep_random
from .types import SearchResult, ThreadPost, ThreadsUser
from .urls import SEARCH_URL

logger = logging.getLogger(__name__)


def search(
    page: Page,
    query: str,
    search_type: str = "all",
    max_results: int = 20,
) -> SearchResult:
    """搜索 Threads。

    Args:
        page: CDP 页面对象。
        query: 搜索关键词。
        search_type: "all" | "recent" | "profiles"
        max_results: 最多返回条数。

    Returns:
        SearchResult 包含帖子和用户结果。
    """
    logger.info("搜索: %s (type=%s)", query, search_type)

    # 导航到搜索页
    # ✅ 已验证 filter 参数：热门(默认)、recent(近期)、profiles(主页)
    search_url = f"{SEARCH_URL}?q={query}"
    if search_type == "recent":
        search_url += "&filter=recent"
    elif search_type == "profiles":
        search_url += "&filter=profiles"
    # search_type == "all" 不加 filter，使用默认热门 tab

    page.navigate(search_url)
    page.wait_for_load(timeout=20)
    navigation_delay()

    result = SearchResult(query=query)
    seen_post_keys: set[str] = set()
    seen_usernames: set[str] = set()

    # profiles 模式不需要滚动，内容有限；帖子模式需要滚动加载
    max_scrolls = 1 if search_type == "profiles" else max(10, max_results // 4 * 3)
    stall_count = 0

    for scroll_i in range(max_scrolls):
        # 每轮先尝试 JSON 路径，再 DOM 降级
        batch_posts: list[ThreadPost] = []
        batch_users: list[ThreadsUser] = []

        scripts_json = page.evaluate(
            """
            (() => {
                const scripts = document.querySelectorAll('script[type="application/json"]');
                const results = [];
                for (const s of scripts) {
                    if ((s.textContent || '').length > 500) results.push(s.textContent);
                }
                results.sort((a, b) => b.length - a.length);
                return JSON.stringify(results);
            })()
            """
        )

        if scripts_json:
            try:
                scripts = json.loads(scripts_json)
                for raw in scripts:
                    try:
                        data = json.loads(raw)
                        posts, users = _parse_search_results(data, max_results)
                        batch_posts.extend(posts)
                        batch_users.extend(users)
                    except Exception as e:
                        logger.debug("解析搜索结果 JSON 失败: %s", e)
            except Exception:
                pass

        # JSON 没拿到帖子则 DOM 降级
        if not batch_posts:
            batch_posts = _extract_search_results_from_dom(page, max_results)

        prev_len = len(result.posts) + len(result.users)
        for p in batch_posts:
            key = p.post_id or p.url or p.content[:50]
            if key and key not in seen_post_keys:
                seen_post_keys.add(key)
                result.posts.append(p)
        for u in batch_users:
            if u.username and u.username not in seen_usernames:
                seen_usernames.add(u.username)
                result.users.append(u)

        new_count = len(result.posts) + len(result.users) - prev_len
        logger.info(
            "搜索第 %d 轮后共 %d 条帖子 / %d 个用户（新增 %d）",
            scroll_i + 1, len(result.posts), len(result.users), new_count,
        )

        if len(result.posts) >= max_results:
            break

        # 连续 3 次无新增则停止
        if new_count == 0:
            stall_count += 1
            if stall_count >= 3:
                logger.info("连续 %d 次无新增，停止滚动", stall_count)
                break
        else:
            stall_count = 0

        # 滚动到底部，等待新内容渲染
        prev_height = page.evaluate("document.body.scrollHeight")
        page.scroll_to_bottom()
        for _ in range(12):
            sleep_random(400, 600)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > prev_height:
                break

    result.posts = result.posts[:max_results]
    result.users = result.users[:max_results]
    return result


def _parse_search_results(
    data: dict, max_results: int
) -> tuple[list[ThreadPost], list[ThreadsUser]]:
    """从 JSON 中解析搜索结果。"""
    posts: list[ThreadPost] = []
    users: list[ThreadsUser] = []

    def _find(obj: object) -> None:
        if isinstance(obj, dict):
            # 帖子
            if "thread_items" in obj:
                for item in obj["thread_items"]:
                    if isinstance(item, dict) and "post" in item and len(posts) < max_results:
                        post = _parse_single_post(item["post"])
                        if post:
                            posts.append(post)
            # 用户
            elif obj.get("username") and obj.get("pk") and len(users) < max_results:
                if obj.get("username") not in [u.username for u in users]:
                    users.append(
                        ThreadsUser(
                            user_id=str(obj.get("pk", "")),
                            username=obj.get("username", ""),
                            display_name=obj.get("full_name", ""),
                            avatar_url=obj.get("profile_pic_url", ""),
                            is_verified=obj.get("is_verified", False),
                            follower_count=str(obj.get("follower_count", "")),
                            bio=obj.get("biography", ""),
                        )
                    )
            else:
                for v in obj.values():
                    _find(v)
        elif isinstance(obj, list):
            for item in obj:
                _find(item)

    _find(data)
    return posts, users


def _extract_search_results_from_dom(page: Page, max_results: int) -> list[ThreadPost]:
    """从 DOM 提取搜索结果（降级方案）。使用已验证的选择器。"""
    items_data = page.evaluate(
        f"""
        (() => {{
            const results = [];
            // ✅ 已验证：帖子容器
            const containers = document.querySelectorAll('div[data-pressable-container="true"]');
            for (const c of containers) {{
                if (results.length >= {max_results}) break;
                // ✅ 作者用户名
                const userEl = c.querySelector('a[href^="/@"]');
                const href = userEl?.getAttribute('href') || '';
                const username = href.replace('/@', '').split('/')[0] || '';
                // ✅ 帖子正文（取所有 span[dir=auto] 拼接）
                const textEls = c.querySelectorAll('span[dir="auto"]');
                const texts = Array.from(textEls).map(el => el.textContent?.trim()).filter(Boolean);
                const content = texts.join(' ');
                // 时间戳和链接
                const timeEl = c.querySelector('time');
                const timestamp = timeEl?.getAttribute('datetime') || '';
                const postLink = c.querySelector('a[href*="/post/"]');
                const postHref = postLink?.getAttribute('href') || '';
                const url = postHref ? 'https://www.threads.net' + postHref : '';
                if (content || username) {{
                    results.push({{ content, username, timestamp, url }});
                }}
            }}
            return JSON.stringify(results);
        }})()
        """
    )

    if not items_data:
        return []

    try:
        items = json.loads(items_data)
        posts = []
        for item in items:
            if not (item.get("content") or item.get("username")):
                continue
            url = item.get("url", "")
            post_id = url.split("/post/")[-1].strip("/") if "/post/" in url else ""
            posts.append(ThreadPost(
                post_id=post_id,
                author=ThreadsUser(username=item.get("username", "")),
                content=item.get("content", ""),
                created_at=item.get("timestamp", ""),
                url=url,
            ))
        return posts
    except Exception:
        return []
