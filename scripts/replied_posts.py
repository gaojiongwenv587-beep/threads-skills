"""已回复帖子记录，防止重复评论。

记录存储在 ~/.threads/replied_posts.json（全局）或
~/.threads/accounts/<name>/replied_posts.json（按账号隔离）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _store_path(account: str | None = None) -> Path:
    base = Path.home() / ".threads"
    if account:
        return base / "accounts" / account / "replied_posts.json"
    return base / "replied_posts.json"


def _load(account: str | None) -> set[str]:
    path = _store_path(account)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def _save(ids: set[str], account: str | None) -> None:
    path = _store_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8")


def extract_post_id(url: str) -> str:
    """从帖子 URL 提取 shortcode。

    例如：https://www.threads.net/@user/post/DVxppvZCAAl → DVxppvZCAAl
    """
    if "/post/" in url:
        return url.split("/post/")[-1].strip("/").split("?")[0]
    return ""


def has_replied(url: str, account: str | None = None) -> bool:
    """检查是否已回复过该帖子。"""
    post_id = extract_post_id(url)
    if not post_id:
        return False
    return post_id in _load(account)


def mark_replied(url: str, account: str | None = None) -> None:
    """将帖子标记为已回复。"""
    post_id = extract_post_id(url)
    if not post_id:
        return
    ids = _load(account)
    ids.add(post_id)
    _save(ids, account)
    logger.info("已记录回复: %s", post_id)


def list_replied(account: str | None = None) -> list[str]:
    """返回已回复的帖子 ID 列表（按字母排序）。"""
    return sorted(_load(account))
