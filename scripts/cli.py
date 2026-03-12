#!/usr/bin/env python3
"""Threads 自动化 CLI 入口。

所有输出均为 JSON 格式，exit code: 0=成功，1=未登录，2=错误。
CLI 设计参考 xiaohongshu-skills，保持相同的调用约定。

用法:
    python scripts/cli.py <子命令> [选项]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 将 scripts/ 加入路径
sys.path.insert(0, str(Path(__file__).parent))

from account_manager import (
    add_account,
    get_account_port,
    get_default_account,
    get_profile_dir,
    list_accounts,
    remove_account,
    set_default_account,
)
from chrome_launcher import DEFAULT_PORT, ensure_chrome
from threads.cdp import Browser
from threads.errors import NotLoggedInError, ThreadsError
from threads.login import check_login, ensure_logged_in, open_login_page
from threads.types import PublishContent
from image_downloader import process_images, is_image_url
from replied_posts import has_replied, mark_replied

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


# ========== 输出工具 ==========

_current_page = None  # 用于退出时自动关闭 tab


def _ok(data: dict) -> None:
    _close_current_page()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(0)


def _fail(message: str, code: int = 2) -> None:
    _close_current_page()
    print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
    sys.exit(code)


def _close_current_page() -> None:
    """关闭当前 tab，保持浏览器干净。"""
    global _current_page
    if _current_page is not None:
        try:
            _current_page.close()
        except Exception:
            pass
        _current_page = None


# ========== 浏览器上下文管理 ==========


def _get_browser(host: str, port: int) -> Browser:
    """获取 Browser 实例（不自动启动 Chrome）。"""
    b = Browser(host=host, port=port)
    b.connect()
    return b


def _get_page(args: argparse.Namespace):
    """创建页面并注册到全局，命令结束后自动关闭。"""
    global _current_page
    port = _resolve_port(args)
    b = _get_browser(args.host, port)
    page = b.new_page()
    _current_page = page
    return page


# ========== 子命令处理函数 ==========


def cmd_check_login(args: argparse.Namespace) -> None:
    page = _get_page(args)
    result = check_login(page)
    _ok(result)


def cmd_login(args: argparse.Namespace) -> None:
    page = _get_page(args)
    result = open_login_page(page)
    _ok(result)


def cmd_delete_cookies(args: argparse.Namespace) -> None:
    """清除 Chrome Profile 的 Cookies（退出/切换账号）。"""
    page = _get_page(args)
    page._send_session("Network.clearBrowserCookies")
    page.navigate("https://www.threads.net/")
    _ok({"status": "success", "message": "Cookies 已清除，请重新登录"})


def cmd_list_feeds(args: argparse.Namespace) -> None:
    from threads.feed import list_feeds

    page = _get_page(args)
    ensure_logged_in(page)
    result = list_feeds(page, max_posts=args.limit)
    _ok(result.to_dict())


def cmd_get_thread(args: argparse.Namespace) -> None:
    """获取单条 Thread 详情。"""
    page = _get_page(args)
    ensure_logged_in(page)

    page.navigate(args.url)
    page.wait_for_load(timeout=15)

    from threads.feed import _try_extract_from_scripts
    from threads.human import navigation_delay
    import time

    navigation_delay()
    # 提取主帖 + 回复
    raw = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            for (const s of scripts) {
                try {
                    const d = JSON.parse(s.textContent);
                    if (JSON.stringify(d).includes('thread_items')) return s.textContent;
                } catch(e) {}
            }
            return null;
        })()
        """
    )

    if raw:
        import json as _json
        from threads.feed import _parse_threads_json

        data = _json.loads(raw)
        posts = _parse_threads_json(data, max_posts=50)
        _ok({
            "url": args.url,
            "posts": [p.to_dict() for p in posts],
        })
    else:
        _ok({"url": args.url, "posts": [], "message": "未提取到结构化数据"})


def cmd_user_profile(args: argparse.Namespace) -> None:
    from threads.profile import get_user_profile

    page = _get_page(args)
    ensure_logged_in(page)
    result = get_user_profile(page, args.username, max_posts=args.limit)
    _ok(result.to_dict())


def cmd_search(args: argparse.Namespace) -> None:
    from threads.search import search

    page = _get_page(args)
    ensure_logged_in(page)
    result = search(page, args.query, search_type=args.type, max_results=args.limit)
    _ok(result.to_dict())


def _resolve_images(images: list[str]) -> list[str]:
    """将图片列表中的 URL 下载到本地，返回本地绝对路径列表。"""
    if not images:
        return []
    has_url = any(is_image_url(p) for p in images)
    if not has_url:
        return images
    local_paths = process_images(images)
    return local_paths


def cmd_fill_thread(args: argparse.Namespace) -> None:
    from threads.publish import fill_thread

    content_text = _read_file_or_inline(args.content_file, args.content)
    images = _resolve_images(args.images or [])

    page = _get_page(args)
    ensure_logged_in(page)

    content = PublishContent(content=content_text, image_paths=images)
    result = fill_thread(page, content)
    # fill-thread 不关闭 tab（保留状态供 click-publish 使用）
    global _current_page
    _current_page = None
    _ok(result)


def cmd_click_publish(args: argparse.Namespace) -> None:
    from threads.publish import click_publish

    port = _resolve_port(args)
    b = _get_browser(args.host, port)
    page = b.get_existing_page()
    if not page:
        _fail("未找到已打开的浏览器页面，请先调用 fill-thread")
    global _current_page
    _current_page = page

    # 检查当前页面是否还有发帖弹框（Tab 可能已被关闭或导航走）
    has_dialog = page.evaluate(
        "!!document.querySelector('div[role=\"dialog\"]')"
    )
    if not has_dialog:
        current_url = page.evaluate("location.href")
        _fail(
            f"当前页面没有发帖弹框（当前 URL: {current_url}）。"
            "请重新调用 fill-thread 填写内容后再 click-publish。"
        )

    result = click_publish(page)
    _ok(result)


def cmd_post_thread(args: argparse.Namespace) -> None:
    """一步发布 Thread（fill + publish）。"""
    from threads.publish import publish_thread

    content_text = _read_file_or_inline(args.content_file, args.content)
    images = _resolve_images(args.images or [])

    page = _get_page(args)
    ensure_logged_in(page)

    content = PublishContent(content=content_text, image_paths=images)
    result = publish_thread(page, content)
    _ok(result)


def cmd_reply_thread(args: argparse.Namespace) -> None:
    from threads.interact import reply_thread

    account = getattr(args, "account", None)

    # 防重复：已回复过则跳过
    if has_replied(args.url, account):
        _ok({"status": "skipped", "message": "已回复过该帖子，跳过", "url": args.url})

    content_text = _read_file_or_inline(args.content_file, args.content)
    page = _get_page(args)
    ensure_logged_in(page)

    result = reply_thread(page, args.url, content_text)

    # 回复成功后记录
    if result.success:
        mark_replied(args.url, account)

    _ok(result.to_dict())


def cmd_like_thread(args: argparse.Namespace) -> None:
    from threads.interact import like_thread

    page = _get_page(args)
    ensure_logged_in(page)

    result = like_thread(page, args.url)
    _ok(result.to_dict())


def cmd_repost_thread(args: argparse.Namespace) -> None:
    from threads.interact import repost_thread

    page = _get_page(args)
    ensure_logged_in(page)

    result = repost_thread(page, args.url)
    _ok(result.to_dict())


def cmd_follow_user(args: argparse.Namespace) -> None:
    from threads.interact import follow_user

    page = _get_page(args)
    ensure_logged_in(page)

    result = follow_user(page, args.username)
    _ok(result.to_dict())


def cmd_list_replied(args: argparse.Namespace) -> None:
    from replied_posts import list_replied

    account = getattr(args, "account", None)
    ids = list_replied(account)
    _ok({"count": len(ids), "post_ids": ids})


def cmd_add_account(args: argparse.Namespace) -> None:
    add_account(args.name, args.description or "")
    accts = list_accounts()
    _ok({"status": "success", "accounts": accts})


def cmd_list_accounts(args: argparse.Namespace) -> None:
    _ok({"accounts": list_accounts()})


def cmd_remove_account(args: argparse.Namespace) -> None:
    remove_account(args.name)
    _ok({"status": "success", "message": f"账号 '{args.name}' 已删除"})


def cmd_set_default_account(args: argparse.Namespace) -> None:
    set_default_account(args.name)
    _ok({"status": "success", "message": f"默认账号已设置为 '{args.name}'"})


# ========== 工具函数 ==========


def _resolve_port(args: argparse.Namespace) -> int:
    """根据 --account 或 --port 解析调试端口。"""
    if hasattr(args, "account") and args.account:
        return get_account_port(args.account)
    return args.port


def _read_file_or_inline(file_path: str | None, inline: str | None) -> str:
    """从文件或内联参数读取文本内容。"""
    if file_path:
        path = Path(file_path)
        if not path.is_absolute():
            _fail(f"文件路径必须为绝对路径: {file_path}")
        return path.read_text(encoding="utf-8").strip()
    if inline:
        return inline.strip()
    _fail("必须提供 --content-file 或 --content")
    return ""  # unreachable


# ========== 参数解析 ==========


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Threads 自动化 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 全局选项
    parser.add_argument("--host", default="127.0.0.1", help="Chrome 调试主机")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Chrome 调试端口")
    parser.add_argument("--account", default="", help="指定账号名称")

    sub = parser.add_subparsers(dest="command", required=True)

    # 认证
    sub.add_parser("check-login", help="检查登录状态")
    sub.add_parser("login", help="打开登录页，等待手动登录")
    sub.add_parser("delete-cookies", help="清除 Cookies（退出/切换账号）")

    # 浏览
    p = sub.add_parser("list-feeds", help="获取首页 Feed")
    p.add_argument("--limit", type=int, default=20, help="最多返回条数")

    p = sub.add_parser("get-thread", help="获取 Thread 详情和回复")
    p.add_argument("--url", required=True, help="Thread 完整 URL")

    p = sub.add_parser("user-profile", help="获取用户主页")
    p.add_argument("--username", required=True, help="用户名（可带 @）")
    p.add_argument("--limit", type=int, default=12, help="最多返回帖子数")

    p = sub.add_parser("search", help="搜索 Threads")
    p.add_argument("--query", required=True, help="搜索关键词")
    p.add_argument(
        "--type", default="all",
        choices=["all", "recent", "profiles"],
        help="搜索类型：all=热门(默认), recent=最新, profiles=用户",
    )
    p.add_argument("--limit", type=int, default=20, help="最多返回条数")

    # 发布（分步）
    p = sub.add_parser("fill-thread", help="填写 Thread 内容（不发布）")
    p.add_argument("--content", help="Thread 正文（内联）")
    p.add_argument("--content-file", help="Thread 正文文件（绝对路径）")
    p.add_argument("--images", nargs="*", help="图片文件绝对路径列表")

    sub.add_parser("click-publish", help="确认发布（在 fill-thread 之后调用）")

    # 发布（一步）
    p = sub.add_parser("post-thread", help="一步发布 Thread")
    p.add_argument("--content", help="Thread 正文（内联）")
    p.add_argument("--content-file", help="Thread 正文文件（绝对路径）")
    p.add_argument("--images", nargs="*", help="图片文件绝对路径列表")

    # 互动
    p = sub.add_parser("reply-thread", help="回复 Thread")
    p.add_argument("--url", required=True, help="要回复的 Thread URL")
    p.add_argument("--content", help="回复内容（内联）")
    p.add_argument("--content-file", help="回复内容文件（绝对路径）")

    sub.add_parser("list-replied", help="查看已回复的帖子 ID 列表")

    p = sub.add_parser("like-thread", help="点赞 Thread")
    p.add_argument("--url", required=True, help="Thread URL")

    p = sub.add_parser("repost-thread", help="转发 Thread")
    p.add_argument("--url", required=True, help="Thread URL")

    p = sub.add_parser("follow-user", help="关注用户")
    p.add_argument("--username", required=True, help="用户名（可带 @）")

    # 账号管理
    p = sub.add_parser("add-account", help="添加账号")
    p.add_argument("--name", required=True, help="账号名称")
    p.add_argument("--description", default="", help="账号描述")

    sub.add_parser("list-accounts", help="列出所有账号")

    p = sub.add_parser("remove-account", help="删除账号")
    p.add_argument("--name", required=True, help="账号名称")

    p = sub.add_parser("set-default-account", help="设置默认账号")
    p.add_argument("--name", required=True, help="账号名称")

    return parser


_COMMAND_MAP = {
    "check-login": cmd_check_login,
    "login": cmd_login,
    "delete-cookies": cmd_delete_cookies,
    "list-feeds": cmd_list_feeds,
    "get-thread": cmd_get_thread,
    "user-profile": cmd_user_profile,
    "search": cmd_search,
    "fill-thread": cmd_fill_thread,
    "click-publish": cmd_click_publish,
    "post-thread": cmd_post_thread,
    "reply-thread": cmd_reply_thread,
    "list-replied": cmd_list_replied,
    "like-thread": cmd_like_thread,
    "repost-thread": cmd_repost_thread,
    "follow-user": cmd_follow_user,
    "add-account": cmd_add_account,
    "list-accounts": cmd_list_accounts,
    "remove-account": cmd_remove_account,
    "set-default-account": cmd_set_default_account,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler = _COMMAND_MAP.get(args.command)
    if not handler:
        _fail(f"未知命令: {args.command}")

    try:
        handler(args)
    except NotLoggedInError as e:
        _fail(str(e), code=1)
    except ThreadsError as e:
        _fail(str(e), code=2)
    except ConnectionRefusedError:
        _fail(
            "无法连接到 Chrome（端口被拒绝）。"
            "请先启动 Chrome: python scripts/chrome_launcher.py",
            code=2,
        )
    except Exception as e:
        _fail(f"未知错误: {e}", code=2)


if __name__ == "__main__":
    main()
