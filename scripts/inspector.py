#!/usr/bin/env python3
"""Threads DOM 探针 — 自动发现实际 CSS 选择器。

用法：
    # 1. 先启动 Chrome
    python scripts/chrome_launcher.py

    # 2. 在 Chrome 里打开 threads.net 并登录

    # 3. 运行探针（自动探查当前页面）
    python scripts/inspector.py

    # 探查特定页面
    python scripts/inspector.py --url "https://www.threads.net/"
    python scripts/inspector.py --url "https://www.threads.net/@username"

输出结果直接告诉你哪些选择器命中、哪些失效，复制到 selectors.py 替换即可。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from chrome_launcher import DEFAULT_PORT
from threads.cdp import Browser


def inspect_page(page, url: str | None = None) -> None:
    if url:
        print(f"\n>>> 导航到: {url}")
        page.navigate(url)
        page.wait_for_load(timeout=20)
        import time; time.sleep(3)

    current_url = page.evaluate("window.location.href") or "(unknown)"
    print(f"当前 URL: {current_url}\n")

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("1. 登录状态探查")
    print("=" * 60)
    _probe_selectors(page, "LOGIN_INDICATORS（任一命中=已登录）", [
        'a[href="/"][role="link"]',
        'svg[aria-label="Home"]',
        '[aria-label="New thread"]',
        'div[data-pressable-container="true"]',
        # Instagram 登录后的头像区域
        'img[data-testid="user-avatar"]',
        'a[href*="/profile"]',
        # 尝试提取用户名
        'a[href*="/@"][class*="nav"]',
    ])
    _probe_selectors(page, "LOGOUT_INDICATORS（任一命中=未登录）", [
        'a[href="/login"]',
        'input[name="username"]',
        'button[data-testid="login-button"]',
        'a[href*="login"]',
    ])

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("2. 帖子容器探查（首页 Feed）")
    print("=" * 60)
    candidates = [
        'div[data-pressable-container="true"]',
        'article',
        'div[role="article"]',
        '[data-testid="post-container"]',
        'div[class*="Thread"]',
        'div[class*="thread"]',
    ]
    _probe_selectors_with_count(page, "POST_CONTAINER 候选", candidates)

    # 找到帖子后，深入分析第一个帖子的结构
    _dump_first_post_structure(page, candidates)

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("3. 发布入口探查")
    print("=" * 60)
    _probe_selectors(page, "COMPOSE_TRIGGER 候选", [
        '[aria-label="New thread"]',
        '[aria-label="Create"]',
        '[aria-label="新帖子"]',
        '[aria-label="发布"]',
        'svg[aria-label*="thread" i]',
        '[data-testid="create-post-button"]',
        '[data-testid="new-post-button"]',
    ])

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("4. 互动按钮探查")
    print("=" * 60)
    _probe_selectors(page, "LIKE_BUTTON", [
        'svg[aria-label="Like"]',
        '[aria-label="Like"]',
        '[data-testid="like-button"]',
        'span[aria-label*="like" i]',
    ])
    _probe_selectors(page, "REPLY_BUTTON", [
        'svg[aria-label="Reply"]',
        '[aria-label="Reply"]',
        '[data-testid="reply-button"]',
    ])
    _probe_selectors(page, "REPOST_BUTTON", [
        'svg[aria-label="Repost"]',
        '[aria-label="Repost"]',
        '[aria-label="Rethread"]',
        '[data-testid="repost-button"]',
    ])

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("5. 文本输入框探查（需先打开发帖弹框）")
    print("=" * 60)
    _probe_selectors(page, "THREAD_TEXT_INPUT", [
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"]',
        'textarea[placeholder*="thread" i]',
        'div[aria-label*="thread" i]',
    ])

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("6. script JSON 数据探查")
    print("=" * 60)
    _probe_json_scripts(page)

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("7. aria-label 完整枚举（所有带 aria-label 的元素）")
    print("=" * 60)
    _dump_aria_labels(page)

    # -----------------------------------------------------------------------
    print("=" * 60)
    print("8. 关键 data-testid 枚举")
    print("=" * 60)
    _dump_testids(page)


def _probe_selectors(page, label: str, selectors: list[str]) -> None:
    print(f"\n  [{label}]")
    any_hit = False
    for sel in selectors:
        exists = page.has_element(sel)
        status = "✅ 命中" if exists else "❌ 未找到"
        if exists:
            # 尝试获取文本
            text = page.get_element_text(sel) or ""
            text_preview = text.strip()[:40].replace("\n", " ") if text else ""
            print(f"    {status}  {sel!r:55s}  text={text_preview!r}")
            any_hit = True
        else:
            print(f"    {status}  {sel!r}")
    if not any_hit:
        print("    ⚠️  所有候选均未命中，需要手动检查 DOM")


def _probe_selectors_with_count(page, label: str, selectors: list[str]) -> None:
    print(f"\n  [{label}]")
    for sel in selectors:
        count = page.get_elements_count(sel)
        status = f"✅ {count} 个" if count > 0 else "❌ 0 个"
        print(f"    {status:12s}  {sel!r}")


def _dump_first_post_structure(page, container_candidates: list[str]) -> None:
    """深入分析第一个帖子容器的 HTML 结构。"""
    print("\n  [第一个帖子容器 HTML 结构（前 2000 字符）]")
    for sel in container_candidates:
        if page.get_elements_count(sel) > 0:
            html = page.evaluate(
                f"document.querySelector({json.dumps(sel)})?.outerHTML?.substring(0, 2000)"
            )
            if html:
                print(f"    容器选择器: {sel!r}")
                print(f"    HTML 片段:\n{html}\n")
                # 分析子元素
                _analyze_post_children(page, sel)
            break
    else:
        print("    ❌ 未找到任何帖子容器")


def _analyze_post_children(page, container_sel: str) -> None:
    """分析帖子容器内的子元素结构。"""
    print("\n  [帖子内部关键子元素]")
    child_probes = {
        "作者链接": "a[href*='/@']",
        "正文文字": "span[dir='auto'], div[dir='auto'], span[data-lexical-text]",
        "点赞区域": "[aria-label*='like' i], [aria-label*='Like']",
        "回复区域": "[aria-label*='reply' i], [aria-label*='Reply']",
        "时间戳": "time, [datetime]",
    }
    for name, child_sel in child_probes.items():
        full_sel = f"{container_sel} {child_sel}"
        count = page.get_elements_count(full_sel)
        if count > 0:
            text = page.get_element_text(full_sel) or ""
            print(f"    ✅ {name:10s}: {full_sel!r}  ({count}个)  text={text.strip()[:30]!r}")
        else:
            print(f"    ❌ {name:10s}: {full_sel!r}")


def _probe_json_scripts(page) -> None:
    """检查页面中的 JSON script 标签，确认数据结构。"""
    result = page.evaluate(
        """
        (() => {
            const scripts = document.querySelectorAll('script[type="application/json"]');
            const results = [];
            for (const s of scripts) {
                try {
                    const d = JSON.parse(s.textContent);
                    const str = JSON.stringify(d);
                    results.push({
                        size: s.textContent.length,
                        hasThreadItems: str.includes('thread_items'),
                        hasUsername: str.includes('"username"'),
                        hasFollowerCount: str.includes('follower_count'),
                        preview: str.substring(0, 200),
                    });
                } catch(e) {
                    results.push({ error: e.message, size: s.textContent.length });
                }
            }
            return JSON.stringify(results);
        })()
        """
    )

    if not result:
        print("  ❌ 未发现 script[type=application/json] 标签")
        return

    scripts = json.loads(result)
    print(f"  发现 {len(scripts)} 个 JSON script 标签：")
    for i, s in enumerate(scripts):
        if "error" in s:
            print(f"    [{i}] ❌ 解析失败: {s['error']} (size={s['size']})")
        else:
            flags = []
            if s.get("hasThreadItems"):
                flags.append("✅ thread_items")
            if s.get("hasUsername"):
                flags.append("✅ username")
            if s.get("hasFollowerCount"):
                flags.append("✅ follower_count")
            print(f"    [{i}] size={s['size']:6d}  {', '.join(flags) or '(无关键字段)'}")
            print(f"         preview: {s['preview'][:100]}")


def _dump_aria_labels(page) -> None:
    """枚举页面所有带 aria-label 的元素。"""
    labels = page.evaluate(
        """
        (() => {
            const els = document.querySelectorAll('[aria-label]');
            const seen = new Set();
            const result = [];
            for (const el of els) {
                const label = el.getAttribute('aria-label');
                const tag = el.tagName.toLowerCase();
                const key = tag + ':' + label;
                if (!seen.has(key) && result.length < 60) {
                    seen.add(key);
                    result.push({ tag, label, role: el.getAttribute('role') || '' });
                }
            }
            return JSON.stringify(result);
        })()
        """
    )

    if not labels:
        print("  ❌ 未找到带 aria-label 的元素")
        return

    items = json.loads(labels)
    print(f"  共 {len(items)} 个唯一 aria-label（最多显示 60 个）：")
    for item in items:
        role = f" role={item['role']!r}" if item["role"] else ""
        print(f"    <{item['tag']}{role}> aria-label={item['label']!r}")


def _dump_testids(page) -> None:
    """枚举页面所有 data-testid。"""
    testids = page.evaluate(
        """
        (() => {
            const els = document.querySelectorAll('[data-testid]');
            const seen = new Set();
            const result = [];
            for (const el of els) {
                const id = el.getAttribute('data-testid');
                if (!seen.has(id) && result.length < 40) {
                    seen.add(id);
                    result.push({ tag: el.tagName.toLowerCase(), testid: id });
                }
            }
            return JSON.stringify(result);
        })()
        """
    )

    if not testids:
        print("  ❌ 未找到带 data-testid 的元素（Meta 可能不用这个属性）")
        return

    items = json.loads(testids)
    print(f"  共 {len(items)} 个唯一 data-testid：")
    for item in items:
        print(f"    <{item['tag']}> data-testid={item['testid']!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Threads DOM 探针")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--url", default=None, help="要探查的 URL（留空=使用当前页面）")
    args = parser.parse_args()

    print(f"连接 Chrome: {args.host}:{args.port}")
    b = Browser(host=args.host, port=args.port)
    b.connect()
    page = b.get_or_create_page()

    inspect_page(page, url=args.url)

    print("\n" + "=" * 60)
    print("探查完成。")
    print("根据上面的 ✅ 命中结果，更新 scripts/threads/selectors.py 中的选择器。")
    print("=" * 60)


if __name__ == "__main__":
    main()
