"""批量回复助手 — GUI 弹窗逐条填写评论，自动执行 reply-thread。

使用方式：
    uv run python scripts/reply_assistant.py --posts-file /tmp/posts.json
    uv run python scripts/reply_assistant.py --posts-file /tmp/posts.json --port 8666 --account myaccount

输入文件格式（CLI list-feeds / search 输出的 posts 数组子集）：
    [
      {
        "postId": "DVxppvZCAAl",
        "url": "https://www.threads.net/@user/post/DVxppvZCAAl",
        "author": {"username": "bigbigburger1", "displayName": "大大汉堡"},
        "content": "帖子正文内容",
        "likeCount": "1,234",
        "replyCount": "56"
      }
    ]

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
import logging
import queue as q_module
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

THREADS_MAX_CHARS = 500


# ---------------------------------------------------------------------------
# tkinter 可用性检测
# ---------------------------------------------------------------------------

def _check_tkinter() -> None:
    """检测 tkinter 是否可用，不可用时打印提示后退出。"""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print(
            "错误：tkinter 不可用。\n"
            "macOS 请执行：brew install python-tk\n"
            "或：brew install python-tk@3.12（根据实际 Python 版本）",
            file=sys.stderr,
        )
        sys.exit(2)


# ---------------------------------------------------------------------------
# 弹窗对话框
# ---------------------------------------------------------------------------

def show_dialog(post: dict, index: int, total: int) -> Optional[str]:
    """显示单条帖子的回复弹窗。

    Returns:
        str  — 用户输入的评论内容（点击「发布」）
        None — 用户点击「跳过」
        ""   — 用户点击「结束」（空字符串作为哨兵）
    """
    import tkinter as tk
    from tkinter import font as tkfont

    result: list[Optional[str]] = [None]  # 用列表绕过 closure 限制

    author = post.get("author") or {}
    username = author.get("username") or author.get("displayName") or "未知用户"
    content = post.get("content") or ""
    like_count = post.get("likeCount") or "0"
    reply_count = post.get("replyCount") or "0"

    root = tk.Tk()
    root.title(f"批量回復  {index} / {total}  @{username}")
    root.resizable(True, True)
    root.minsize(480, 380)
    root.wm_attributes("-topmost", True)

    # ── 标题栏 ──
    title_frame = tk.Frame(root, bg="#f5f5f5", pady=8)
    title_frame.pack(fill=tk.X)
    tk.Label(
        title_frame,
        text=f"批量回復  {index} / {total}",
        font=tkfont.Font(size=13, weight="bold"),
        bg="#f5f5f5",
    ).pack(side=tk.LEFT, padx=12)
    tk.Label(
        title_frame,
        text=f"@{username}",
        font=tkfont.Font(size=12),
        fg="#888888",
        bg="#f5f5f5",
    ).pack(side=tk.LEFT)

    tk.Frame(root, height=1, bg="#dddddd").pack(fill=tk.X)

    # ── 帖子正文 ──
    content_frame = tk.Frame(root, padx=12, pady=8)
    content_frame.pack(fill=tk.BOTH, expand=False)

    content_text = tk.Text(
        content_frame,
        height=5,
        wrap=tk.WORD,
        state=tk.DISABLED,
        relief=tk.FLAT,
        bg="#fafafa",
        font=tkfont.Font(size=12),
        cursor="arrow",
    )
    content_text.pack(fill=tk.X, expand=True)
    content_text.config(state=tk.NORMAL)
    content_text.insert(tk.END, content)
    content_text.config(state=tk.DISABLED)

    # 互动数
    stats_label = tk.Label(
        content_frame,
        text=f"❤️ {like_count}   💬 {reply_count}",
        font=tkfont.Font(size=11),
        fg="#888888",
        anchor=tk.W,
    )
    stats_label.pack(fill=tk.X, pady=(4, 0))

    tk.Frame(root, height=1, bg="#dddddd").pack(fill=tk.X)

    # ── 评论输入框 ──
    input_frame = tk.Frame(root, padx=12, pady=8)
    input_frame.pack(fill=tk.BOTH, expand=True)

    comment_text = tk.Text(
        input_frame,
        height=5,
        wrap=tk.WORD,
        relief=tk.SOLID,
        font=tkfont.Font(size=12),
    )
    comment_text.pack(fill=tk.BOTH, expand=True)
    comment_text.focus_set()

    # 字符计数标签
    char_var = tk.StringVar(value=f"字符: 0 / {THREADS_MAX_CHARS}")
    char_label = tk.Label(
        input_frame,
        textvariable=char_var,
        font=tkfont.Font(size=10),
        fg="#888888",
        anchor=tk.E,
    )
    char_label.pack(fill=tk.X)

    tk.Frame(root, height=1, bg="#dddddd").pack(fill=tk.X)

    # ── 按钮区 ──
    btn_frame = tk.Frame(root, pady=10)
    btn_frame.pack(fill=tk.X)

    publish_btn = tk.Button(
        btn_frame,
        text="發布",
        width=10,
        state=tk.DISABLED,
        bg="#0095f6",
        fg="white",
        relief=tk.FLAT,
        font=tkfont.Font(size=12, weight="bold"),
    )
    skip_btn = tk.Button(
        btn_frame,
        text="跳過",
        width=10,
        relief=tk.FLAT,
        font=tkfont.Font(size=12),
    )
    end_btn = tk.Button(
        btn_frame,
        text="結束",
        width=10,
        relief=tk.FLAT,
        font=tkfont.Font(size=12),
        fg="#cc0000",
    )

    end_btn.pack(side=tk.RIGHT, padx=8)
    skip_btn.pack(side=tk.RIGHT, padx=4)
    publish_btn.pack(side=tk.RIGHT, padx=4)

    # ── 事件处理 ──
    def _update_char_count(event=None) -> None:
        content_val = comment_text.get("1.0", tk.END).rstrip("\n")
        char_len = len(content_val)
        char_var.set(f"字符: {char_len} / {THREADS_MAX_CHARS}")
        if 0 < char_len <= THREADS_MAX_CHARS:
            publish_btn.config(state=tk.NORMAL, bg="#0095f6")
            char_label.config(fg="#888888")
        elif char_len > THREADS_MAX_CHARS:
            publish_btn.config(state=tk.DISABLED, bg="#cccccc")
            char_label.config(fg="#cc0000")
        else:
            publish_btn.config(state=tk.DISABLED, bg="#cccccc")
            char_label.config(fg="#888888")

    comment_text.bind("<KeyRelease>", _update_char_count)
    comment_text.bind("<<Modified>>", _update_char_count)

    def _on_publish() -> None:
        result[0] = comment_text.get("1.0", tk.END).rstrip("\n")
        root.destroy()

    def _on_skip() -> None:
        result[0] = None
        root.destroy()

    def _on_end() -> None:
        result[0] = ""
        root.destroy()

    publish_btn.config(command=_on_publish)
    skip_btn.config(command=_on_skip)
    end_btn.config(command=_on_end)

    # Ctrl+Enter 发布快捷键
    root.bind("<Control-Return>", lambda e: _on_publish() if publish_btn["state"] == tk.NORMAL else None)
    root.bind("<Escape>", lambda e: _on_skip())

    # 关闭窗口按钮等同于跳过
    root.protocol("WM_DELETE_WINDOW", _on_skip)

    # 居中显示
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{max(w, 520)}x{max(h, 420)}+{(sw - max(w, 520)) // 2}+{(sh - max(h, 420)) // 2}")

    root.mainloop()
    return result[0]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    _check_tkinter()

    parser = argparse.ArgumentParser(description="批量回复助手：GUI 弹窗逐条填写评论")
    parser.add_argument("--posts-file", required=True, help="帖子 JSON 文件路径（必填）")
    parser.add_argument("--port", type=int, default=8666, help="Chrome 调试端口（默认 8666）")
    parser.add_argument("--account", default="", help="账号名（影响 replied_posts 存储路径）")
    args = parser.parse_args()

    # 读取帖子列表
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

    # 导入本地模块
    sys.path.insert(0, str(Path(__file__).parent))
    from replied_posts import has_replied, mark_replied
    from threads.cdp import Browser
    from threads.interact import reply_thread
    from threads.login import ensure_logged_in

    # 連接瀏覽器並驗證登入（在 GUI 開始前確認，失敗早退）
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

    results: dict[str, list[str]] = {
        "replied": [],
        "skipped": [],
        "already_replied": [],
    }
    results_lock = threading.Lock()
    total = len(posts)

    # reply_queue 傳遞 (post, comment)，None 為終止哨兵
    reply_queue: q_module.Queue = q_module.Queue()

    # ── Worker 背景執行緒：從隊列取任務逐一執行回覆 ──
    def worker() -> None:
        while True:
            item = reply_queue.get()
            if item is None:  # 哨兵，退出
                reply_queue.task_done()
                break
            post, comment = item
            post_url = post.get("url", "")
            post_id = post.get("postId", post_url)

            reply_page = browser.new_page()
            try:
                action_result = reply_thread(reply_page, post_url, comment)
            except Exception as e:
                logger.error("回复失败: %s — %s", post_url, e)
                action_result = None
            finally:
                reply_page.close()

            with results_lock:
                if action_result and action_result.success:
                    mark_replied(post_url, args.account)
                    results["replied"].append(post_id)
                else:
                    msg = action_result.message if action_result else "未知错误"
                    logger.warning("回复未成功（%s）: %s", post_id, msg)
                    results["skipped"].append(post_id)

            reply_queue.task_done()

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    # ── GUI 主執行緒：逐條彈窗，填完即入隊，不等 worker ──
    for i, post in enumerate(posts):
        post_url = post.get("url", "")
        post_id = post.get("postId", post_url)

        if has_replied(post_url, args.account):
            with results_lock:
                results["already_replied"].append(post_id)
            continue

        comment = show_dialog(post, i + 1, total)

        if comment == "":  # 用戶點了「結束」
            with results_lock:
                for remaining in posts[i:]:
                    remaining_id = remaining.get("postId", remaining.get("url", ""))
                    remaining_url = remaining.get("url", "")
                    if not has_replied(remaining_url, args.account):
                        if remaining_id not in results["already_replied"]:
                            results["skipped"].append(remaining_id)
            break

        if comment is None:  # 用戶點了「跳過」
            with results_lock:
                results["skipped"].append(post_id)
            continue

        reply_queue.put((post, comment))  # 入隊，立刻繼續下一條

    # GUI 結束，發哨兵，等待 worker 處理完剩餘隊列
    reply_queue.put(None)
    worker_thread.join()
    browser.close()

    summary = {
        "total": total,
        "replied": len(results["replied"]),
        "skipped": len(results["skipped"]),
        "already_replied": len(results["already_replied"]),
        "replied_ids": results["replied"],
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
