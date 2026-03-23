"""批量回复助手（CLI 版）— 逐条在终端提示输入评论，自动执行 reply-thread。

使用方式：
    uv run python scripts/reply_assistant_cli.py --posts-file /tmp/posts.json
    uv run python scripts/reply_assistant_cli.py --posts-file /tmp/posts.json --port 8666 --account myaccount

stdout 输出摘要 JSON（OpenClaw 读取）：
    {
      "total": 10,
      "replied": 3,
      "skipped": 5,
      "already_replied": 2,
      "replied_ids": ["DVxppvZCAAl", ...]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THREADS_MAX_CHARS = 500


def prompt_reply(post: dict, index: int, total: int) -> str | None:
    """在终端显示帖子信息并提示用户输入评论。

    Returns:
        str  — 用户输入的评论（非空）
        None — 用户跳过（直接回车）
        ""   — 用户结束（输入 q）
    """
    author = post.get("author") or {}
    username = author.get("username") or author.get("displayName") or "未知用户"
    content = post.get("content") or ""
    like_count = post.get("likeCount") or "0"
    reply_count = post.get("replyCount") or "0"

    print(f"\n{'='*60}")
    print(f"帖子 {index}/{total}  @{username}")
    print(f"{'─'*60}")
    print(content)
    print(f"❤️ {like_count}   💬 {reply_count}")
    print(f"{'─'*60}")
    print("输入评论后按 Enter 发布，直接回车跳过，输入 q 结束：")

    try:
        reply = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""

    if reply.lower() == "q":
        return ""
    if not reply:
        return None
    if len(reply) > THREADS_MAX_CHARS:
        print(f"⚠️  超过 {THREADS_MAX_CHARS} 字符限制（当前 {len(reply)}），已跳过")
        return None
    return reply


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回复助手（CLI 版）：逐条终端提示输入评论")
    parser.add_argument("--posts-file", required=True, help="帖子 JSON 文件路径（必填）")
    parser.add_argument("--port", type=int, default=8666, help="Chrome 调试端口（默认 8666）")
    parser.add_argument("--account", default="", help="账号名（影响 replied_posts 存储路径）")
    args = parser.parse_args()

    posts_path = Path(args.posts_file)
    if not posts_path.exists():
        print(json.dumps({"error": f"文件不存在: {args.posts_file}"}, ensure_ascii=False))
        sys.exit(2)

    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"JSON 解析失败: {e}"}, ensure_ascii=False))
        sys.exit(2)

    if not isinstance(posts, list) or not posts:
        print(json.dumps({"error": "posts-file 必须是非空 JSON 数组"}, ensure_ascii=False))
        sys.exit(2)

    sys.path.insert(0, str(Path(__file__).parent))
    from replied_posts import has_replied, mark_replied
    from threads.cdp import Browser
    from threads.interact import reply_thread
    from threads.login import ensure_logged_in

    browser = Browser(port=args.port)
    try:
        browser.connect()
    except Exception as e:
        print(json.dumps({"error": f"无法连接 Chrome（端口 {args.port}）: {e}"}, ensure_ascii=False))
        sys.exit(2)

    login_page = browser.new_page()
    try:
        ensure_logged_in(login_page)
    except Exception as e:
        login_page.close()
        browser.close()
        print(json.dumps({"error": f"未登录: {e}"}, ensure_ascii=False))
        sys.exit(1)
    login_page.close()

    results: dict[str, list[str]] = {"replied": [], "skipped": [], "already_replied": []}
    total = len(posts)

    for i, post in enumerate(posts):
        post_url = post.get("url", "")
        post_id = post.get("postId", post_url)

        if has_replied(post_url, args.account):
            results["already_replied"].append(post_id)
            print(f"\n[{i+1}/{total}] 已回复过，跳过：{post_url}")
            continue

        comment = prompt_reply(post, i + 1, total)

        if comment == "":  # 用户输入 q，结束
            for remaining in posts[i:]:
                r_id = remaining.get("postId", remaining.get("url", ""))
                r_url = remaining.get("url", "")
                if not has_replied(r_url, args.account) and r_id not in results["already_replied"]:
                    results["skipped"].append(r_id)
            break

        if comment is None:  # 跳过
            results["skipped"].append(post_id)
            continue

        print(f"⏳ 发布中...")
        reply_page = browser.new_page()
        try:
            action_result = reply_thread(reply_page, post_url, comment)
        except Exception as e:
            print(f"❌ 回复失败: {e}")
            action_result = None
        finally:
            reply_page.close()

        if action_result and action_result.success:
            mark_replied(post_url, args.account)
            results["replied"].append(post_id)
            print("✅ 发布成功")
        else:
            msg = action_result.message if action_result else "未知错误"
            print(f"❌ 发布未成功: {msg}")
            results["skipped"].append(post_id)

    browser.close()

    summary = {
        "total": total,
        "replied": len(results["replied"]),
        "skipped": len(results["skipped"]),
        "already_replied": len(results["already_replied"]),
        "replied_ids": results["replied"],
    }
    print(f"\n{'='*60}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
