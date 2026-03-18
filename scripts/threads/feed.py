"""Threads 首页 Feed 获取。

通过 CDP 导航到首页，从 DOM 中提取帖子列表。
与小红书不同，Threads 不暴露 window.__INITIAL_STATE__，
使用 DOM 解析 + JSON-LD / 页面状态提取。
"""

from __future__ import annotations

import json
import logging
import re
import time

from .cdp import Page
from .errors import NoFeedsError
from .human import navigation_delay, sleep_random
from .types import FeedResponse, ThreadPost, ThreadsUser
from .urls import HOME_URL

logger = logging.getLogger(__name__)

# 相对时间行正则：匹配"21小时"、"3分钟"、"1天"等
_REL_TIME_RE = re.compile(
    r"^\d+\s*(秒|分鐘|分钟|小時|小时|天|週|周|個月|个月|年)前?$"
)


def _clean_content(raw: str) -> str:
    """过滤帖子正文开头的话题标签行和相对时间行。

    Threads DOM 里 span[dir=auto] 会把话题标签（如"醫美"）和
    相对时间（如"21小时"）混入正文，需要去除它们及其之前的行。
    """
    lines = raw.split("\n")
    time_idx = next(
        (i for i, l in enumerate(lines) if _REL_TIME_RE.match(l.strip())),
        None,
    )
    if time_idx is not None:
        lines = lines[time_idx + 1:]
    return "\n".join(lines).strip()


def list_feeds(page: Page, max_posts: int = 20) -> FeedResponse:
    """获取首页推荐 Feed，滚动加载直到满足数量要求。

    Args:
        page: CDP 页面对象。
        max_posts: 最多返回帖子数。

    Returns:
        FeedResponse 包含帖子列表。

    Raises:
        NoFeedsError: 未提取到任何帖子。
    """
    logger.info("获取 Threads 首页 Feed (max=%d)", max_posts)
    page.navigate(HOME_URL)
    page.wait_for_load(timeout=20)
    navigation_delay()

    seen_keys: set[str] = set()
    all_posts: list[ThreadPost] = []

    # 每次滚动预期能加载约 5 条新帖，多留一倍余量
    max_scrolls = max(15, max_posts // 4 * 3)
    stall_count = 0  # 连续无新增次数，超过阈值则放弃

    for scroll_i in range(max_scrolls):
        # 第一次可尝试 JSON 路径；滚动后新帖只在 DOM，跳过 JSON 避免重复
        batch = _extract_posts_from_page(page, max_posts * 3) if scroll_i == 0 \
            else _extract_from_dom(page, max_posts * 3)
        prev_len = len(all_posts)
        for p in batch:
            # URL 在 JSON/DOM 两路径都一致，优先用 URL 去重
            key = p.url or p.content[:50]
            if key and key not in seen_keys:
                seen_keys.add(key)
                all_posts.append(p)

        new_count = len(all_posts) - prev_len
        logger.info("第 %d 次滚动后共 %d 条（新增 %d）", scroll_i + 1, len(all_posts), new_count)

        if len(all_posts) >= max_posts:
            break

        # 连续 3 次没有新增，说明已到达 Feed 末尾
        if new_count == 0:
            stall_count += 1
            if stall_count >= 3:
                logger.info("连续 %d 次无新帖，停止滚动", stall_count)
                break
        else:
            stall_count = 0

        # 滚动到底部，等待页面高度增加（新帖渲染完）再继续
        prev_height = page.evaluate("document.body.scrollHeight")
        page.scroll_to_bottom()
        # 最多等 6 秒，检测到高度增加即可提前继续
        for _ in range(12):
            sleep_random(400, 600)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > prev_height:
                break

    if not all_posts:
        raise NoFeedsError()

    return FeedResponse(posts=all_posts[:max_posts])


def _extract_posts_from_page(page: Page, max_posts: int) -> list[ThreadPost]:
    """从当前页面 DOM 提取帖子数据。

    优先尝试读取页面内嵌的 JSON 数据（速度快、结构稳定），
    失败则回退到 DOM 解析。
    """
    # 尝试从页面 script 标签中提取结构化数据
    posts = _try_extract_from_scripts(page, max_posts)
    if posts:
        return posts

    # 回退：DOM 解析
    return _extract_from_dom(page, max_posts)


def _try_extract_from_scripts(page: Page, max_posts: int) -> list[ThreadPost]:
    """尝试从所有 script 标签中提取 JSON 数据。

    Threads SSR 页面在多个 script[type="application/json"] 中内嵌结构化数据，
    需要遍历所有 script 标签（尤其是较大的）来找到帖子数据。
    """
    # 获取所有 JSON script 标签（按大小降序，大的更可能包含 feed 数据）
    scripts_json = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            const results = [];
            for (const s of scripts) {
                const text = s.textContent || '';
                // 只处理足够大的 script（忽略小的配置 script）
                if (text.length > 500) {
                    results.push(text);
                }
            }
            // 按大小降序排列，大的先处理
            results.sort((a, b) => b.length - a.length);
            return JSON.stringify(results);
        })()
        """
    )

    if not scripts_json:
        return []

    try:
        scripts = json.loads(scripts_json)
    except Exception:
        return []

    posts: list[ThreadPost] = []
    for raw in scripts:
        if len(posts) >= max_posts:
            break
        try:
            data = json.loads(raw)
            found = _parse_threads_json(data, max_posts - len(posts))
            posts.extend(found)
        except Exception as e:
            logger.debug("解析 script JSON 失败: %s", e)

    return posts[:max_posts]


def _parse_threads_json(data: dict, max_posts: int) -> list[ThreadPost]:
    """递归从 JSON 结构中提取帖子数据。

    Threads 的 JSON 结构可能嵌套较深，通过递归查找关键字段。
    """
    posts: list[ThreadPost] = []

    seen_ids: set[str] = set()

    def _find_posts(obj: object, depth: int = 0) -> None:
        if len(posts) >= max_posts or depth > 20:
            return
        if isinstance(obj, dict):
            # 格式1: thread_items 数组（未登录 SSR / API 格式）
            if "thread_items" in obj:
                for item in obj["thread_items"]:
                    if isinstance(item, dict) and "post" in item:
                        post = _parse_single_post(item["post"])
                        if post and post.post_id not in seen_ids:
                            seen_ids.add(post.post_id)
                            posts.append(post)
            # 格式2: 单条帖子对象（有 pk 和 text_post_app_info）
            elif "pk" in obj and "text_post_app_info" in obj:
                post = _parse_single_post(obj)
                if post and post.post_id not in seen_ids:
                    seen_ids.add(post.post_id)
                    posts.append(post)
            # 格式3: GraphQL Relay edges/node 结构
            elif "edges" in obj and isinstance(obj["edges"], list):
                for edge in obj["edges"]:
                    if isinstance(edge, dict) and "node" in edge:
                        _find_posts(edge["node"], depth + 1)
            # 格式4: Meta Relay __bbox 嵌套
            elif "__bbox" in obj:
                _find_posts(obj["__bbox"], depth + 1)
            else:
                for v in obj.values():
                    _find_posts(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _find_posts(item, depth + 1)

    _find_posts(data)
    return posts[:max_posts]


def _parse_single_post(post_data: dict) -> ThreadPost | None:
    """解析单条帖子数据。"""
    try:
        user_data = post_data.get("user", {})
        user = ThreadsUser(
            user_id=str(user_data.get("pk", user_data.get("id", ""))),
            username=user_data.get("username", ""),
            display_name=user_data.get("full_name", ""),
            avatar_url=user_data.get("profile_pic_url", ""),
            is_verified=user_data.get("is_verified", False),
        )

        # 提取内容文本
        caption = post_data.get("caption") or {}
        if isinstance(caption, dict):
            content = caption.get("text", "")
        else:
            content = str(caption) if caption else ""

        # 提取互动数据
        like_info = post_data.get("like_and_view_counts_disabled", False)
        like_count = "" if like_info else str(post_data.get("like_count", ""))
        reply_count = str(
            post_data.get("text_post_app_info", {}).get("direct_reply_count", "")
        )

        # 提取图片
        images: list[str] = []
        carousel = post_data.get("carousel_media") or []
        for media in carousel:
            if isinstance(media, dict):
                candidates = media.get("image_versions2", {}).get("candidates", [])
                if candidates:
                    images.append(candidates[0].get("url", ""))

        if not carousel:
            candidates = (
                post_data.get("image_versions2", {}).get("candidates", [])
            )
            if candidates:
                images.append(candidates[0].get("url", ""))

        post_id = str(post_data.get("pk", post_data.get("id", "")))
        code = post_data.get("code", "")
        url = f"https://www.threads.net/@{user.username}/post/{code or post_id}"
        # pk 取不到时用 shortcode 作为 postId（首页 Feed JSON 有 code 无 pk）
        if not post_id:
            post_id = code

        return ThreadPost(
            post_id=post_id,
            author=user,
            content=content,
            like_count=like_count,
            reply_count=reply_count,
            created_at=str(post_data.get("taken_at", "")),
            images=images,
            url=url,
        )
    except Exception as e:
        logger.debug("解析帖子失败: %s", e)
        return None


def _extract_from_dom(page: Page, max_posts: int) -> list[ThreadPost]:
    """从 DOM 中提取帖子（降级方案）。

    正确分离正文、时间戳、点赞/评论/引用/转发数。
    基于 ✅ 已验证的选择器：div[data-pressable-container="true"]
    """
    # 通过独立 evaluate 注入 max_posts，避免字符串拼接
    page.evaluate(f"window.__THREADS_MAX_POSTS = {int(max_posts)};")
    posts_data = page.evaluate(
        """
        (() => {
            const maxPosts = window.__THREADS_MAX_POSTS || 20;
            const results = [];
            const containers = document.querySelectorAll('div[data-pressable-container="true"]');
            for (const container of containers) {
                if (results.length >= maxPosts) break;
                try {
                    // 作者用户名
                    const authorLink = container.querySelector('a[href^="/@"]');
                    const usernameHref = authorLink?.getAttribute('href') || '';
                    const username = usernameHref.replace('/@', '').split('/')[0] || '';

                    // 时间戳（datetime 属性是 ISO 格式，textContent 是"21小时"这种）
                    const timeEl = container.querySelector('time');
                    const datetime = timeEl?.getAttribute('datetime') || '';
                    const timeText = timeEl?.textContent?.trim() || '';

                    // 帖子正文：只取不在作者链接内、不在 time 元素内的 span[dir="auto"]
                    const allSpans = container.querySelectorAll('span[dir="auto"]');
                    const contentSpans = Array.from(allSpans).filter(span => {
                        if (authorLink && authorLink.contains(span)) return false;
                        if (timeEl && timeEl.contains(span)) return false;
                        // 排除互动按钮内的 span（点赞数、评论数等）
                        if (span.closest('[role="button"]')) return false;
                        return true;
                    });
                    const content = contentSpans
                        .map(s => s.textContent?.trim())
                        .filter(Boolean)
                        .join('\\n');

                    // 互动数：从 role=button 里按前缀匹配（只取第一个匹配，避免重复）
                    let likeCount = '', replyCount = '', repostCount = '', quoteCount = '';
                    const btns = container.querySelectorAll('[role="button"]');
                    for (const btn of btns) {
                        const t = (btn.textContent || '').trim();
                        if (!likeCount && t.startsWith('赞')) likeCount = t.replace('赞', '').trim();
                        else if (!replyCount && t.startsWith('回复')) replyCount = t.replace('回复', '').trim();
                        else if (!repostCount && t.startsWith('转发')) repostCount = t.replace('转发', '').trim();
                        else if (!quoteCount && t.startsWith('分享')) quoteCount = t.replace('分享', '').trim();
                    }

                    // 帖子链接
                    const postLink = container.querySelector('a[href*="/post/"]');
                    const postHref = postLink?.getAttribute('href') || '';
                    const url = postHref ? 'https://www.threads.net' + postHref : '';

                    if (content || username) {
                        results.push({
                            username, content,
                            datetime, timeText,
                            likeCount, replyCount, repostCount, quoteCount,
                            url,
                        });
                    }
                } catch(e) {}
            }
            return JSON.stringify(results);
        })()
        """
    )

    if not posts_data:
        return []

    try:
        items = json.loads(posts_data)
        posts = []
        for item in items:
            if not (item.get("content") or item.get("username")):
                continue
            url = item.get("url", "")
            # 从 URL 提取 shortcode 作为 postId（如 /post/DVxHauYk1YQ）
            post_id = url.split("/post/")[-1].strip("/") if "/post/" in url else ""
            posts.append(ThreadPost(
                post_id=post_id,
                author=ThreadsUser(username=item.get("username", "")),
                content=_clean_content(item.get("content", "")),
                like_count=item.get("likeCount", ""),
                reply_count=item.get("replyCount", ""),
                repost_count=item.get("repostCount", ""),
                quote_count=item.get("quoteCount", ""),
                created_at=item.get("datetime") or item.get("timeText", ""),
                url=url,
            ))
        return posts
    except Exception:
        return []
