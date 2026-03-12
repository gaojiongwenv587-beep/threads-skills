"""Threads CSS 选择器集中管理。

所有选择器在此文件统一维护，Threads 改版时只改这一个文件。
标注 ✅已验证（inspector.py 实测）/ ⚠️未验证 / ❌已失效

注意：Threads 界面语言跟随账号/系统设置，中文账号用中文 aria-label。
      选择器列表里中英文都加上，由 first_existing() 按顺序尝试。
"""

# ===========================================================================
# 登录检测
# ===========================================================================

# 已登录时存在的元素（任意一个命中即视为已登录）
LOGIN_INDICATORS = [
    'a[href="/"][role="link"]',               # ✅ 首页导航链接（有登录时存在）
    'div[data-pressable-container="true"]',   # ✅ 帖子容器（已登录首页才有内容）
    'svg[aria-label="首页"]',                 # ✅ 中文界面导航图标
    'svg[aria-label="Home"]',                 # ⚠️ 英文界面
]

# 未登录时存在的元素（命中即视为未登录）
LOGOUT_INDICATORS = [
    'a[href*="login"]',                       # ✅ 登录链接（"改用账号登录"）
    'input[name="username"]',                 # ⚠️ Instagram 登录表单
]

# ===========================================================================
# 导航图标（用于辅助判断登录状态和触发操作）
# ===========================================================================

NAV_HOME   = 'svg[aria-label="首页"], svg[aria-label="Home"]'       # ✅ inspector 确认"首页"
NAV_SEARCH = 'svg[aria-label="搜索"], svg[aria-label="Search"]'     # ✅ inspector 确认"搜索"
NAV_CREATE = 'svg[aria-label="创建"], svg[aria-label="Create"]'     # ✅ inspector 确认"创建"
NAV_NOTIFY = 'svg[aria-label="通知"], svg[aria-label="Notifications"]'  # ✅ inspector 确认"通知"
NAV_PROFILE = 'svg[aria-label="主页"], svg[aria-label="Profile"]'   # ✅ inspector 确认"主页"（个人主页入口）

# ===========================================================================
# 帖子容器
# ===========================================================================

# 首页/搜索/用户页 帖子外层容器
POST_CONTAINER = 'div[data-pressable-container="true"]'             # ✅

# 帖子内作者链接（href 形如 /@username）
POST_AUTHOR_LINK = 'a[href^="/@"]'                                  # ✅（从 HTML 结构确认）

# 帖子正文（多层 span/div，dir=auto 是关键特征）
POST_TEXT = 'span[dir="auto"]'                                      # ✅（从 HTML 结构确认）

# 时间戳
POST_TIMESTAMP = 'time, abbr[aria-label*="前"], abbr[aria-label*="ago"]'  # ✅

# ===========================================================================
# 互动按钮
# 注意：按钮是 svg[role=img] 的父元素，点击时应点 svg 或其父 div[role=button]
# ===========================================================================

# 点赞按钮 svg（中文：赞，英文：Like）
LIKE_BUTTON      = 'svg[aria-label="赞"], svg[aria-label="Like"]'   # ✅ 中文已验证（inspector aria-label 枚举确认）
LIKE_BUTTON_ACTIVE = 'svg[aria-label="取消赞"], svg[aria-label="Unlike"]'  # ⚠️ 需点赞后验证

# 回复/评论按钮（中文是"回复"，英文是"Reply"）
REPLY_BUTTON     = 'svg[aria-label="回复"], svg[aria-label="Reply"]'  # ✅ 中文已验证（inspector aria-label 枚举确认）

# 转发按钮（中文：转发，英文：Repost）
REPOST_BUTTON    = 'svg[aria-label="转发"], svg[aria-label="Repost"]'  # ✅ 中文已验证（inspector aria-label 枚举确认）

# 分享按钮
SHARE_BUTTON     = 'svg[aria-label="分享"], svg[aria-label="Share"]'   # ✅ 中文已验证（inspector aria-label 枚举确认）

# ===========================================================================
# 发布 Thread
# ===========================================================================

# 首页发帖入口 —
# ✅ 实测：首页已有 div[role="button"][aria-label*="撰写新帖子"] 直接作为文本输入区，点击即聚焦
# 导航栏"创建"图标也可触发弹框（备用路径）
COMPOSE_TRIGGER = [
    'div[role="button"][aria-label*="撰写新帖子"]',  # ✅ 首页输入区（inspector 确认 aria-label="文本栏为空白。请输入内容，撰写新帖子。"）
    'svg[aria-label="创建"]',                        # ✅ 导航栏"创建"图标（inspector aria-label 枚举确认）
    'svg[aria-label="Create"]',                      # ⚠️ 英文界面
]

# 帖子文本输入区（点击发布入口后出现）
# ✅ 实测：点击 COMPOSE_TRIGGER 后出现 div[contenteditable="true"][data-lexical-editor="true"][role="textbox"]
#    aria-label="文本栏为空白。请输入内容，撰写新帖子。"
THREAD_TEXT_INPUT = [
    'div[contenteditable="true"][data-lexical-editor="true"]',  # ✅ 实测命中（Lexical 编辑器，role=textbox）
    'div[contenteditable="true"][role="textbox"]',              # ✅ 备用（同一元素）
    'div[contenteditable="true"]',                              # ⚠️ 最宽泛 fallback
]

# 发布弹框内的提交按钮（弹框出现后才能找到）
POST_BUTTON = [
    'div[role="dialog"] div[role="button"]:last-child',  # ⚠️
    'div[role="dialog"] [aria-label="发布"]',            # ⚠️
    'div[role="dialog"] [aria-label="Post"]',            # ⚠️
]

# 媒体上传 input（通常隐藏，通过 CDP setFileInputFiles 操作）
FILE_INPUT = 'input[type="file"]'                               # ⚠️

# 发布确认弹框
COMPOSE_MODAL = 'div[role="dialog"]'                            # ⚠️

# ===========================================================================
# 搜索
# ===========================================================================

SEARCH_INPUT = [
    'input[type="search"]',
    'input[placeholder*="搜索"], input[placeholder*="Search"]',
]

# ===========================================================================
# 用户主页
# ===========================================================================

# ✅ 实测：h1 = 用户名（如 "eeinn.babe"），用户页 h1 是 username 而非 displayName
PROFILE_DISPLAY_NAME   = 'h1'                                  # ✅ 用户页 h1 = username
# ✅ 实测：bio 在 span[dir="auto"] 中，通常是第2个较长的 span（需结合长度/位置过滤）
PROFILE_BIO            = 'span[dir="auto"]'                    # ✅（需按长度过滤，第一个长文本即 bio）
# ✅ 实测：无 a[href*="followers"]，粉丝数以 "1,361位粉丝" 格式混在 span[dir="auto"] 中
#    profile.py DOM 降级已改为按"位粉丝"/"followers"文本过滤
PROFILE_FOLLOWER_COUNT = 'span[dir="auto"]'                    # ✅ 需按文本内容过滤（见 profile.py _extract_user_from_dom）
# ✅ 实测：关注按钮 textContent="关注"，取消关注="已关注"/"取消关注"
FOLLOW_BUTTON          = '[role="button"]'                     # ✅ 按 textContent="关注" 匹配
FOLLOWING_BUTTON       = '[role="button"]'                     # ✅ 按 textContent="已关注"/"取消关注" 匹配

# ===========================================================================
# JSON 数据提取（Meta Relay 格式）
# ===========================================================================

# Threads 的 script 数据格式是 Meta 的 ScheduledServerJS/Relay 嵌套格式：
# {"require":[["ScheduledServerJS","handle",null,[{"__bbox":{"require":[["RelayPrefetchedStreamCache",...
# thread_items 和 username 藏在多层 require/__bbox 嵌套里，需要递归搜索。
# feed.py 中的 _find_posts() 已处理此格式，无需在这里定义选择器。

# ===========================================================================
# 工具函数
# ===========================================================================


def first_existing(page, selectors: list[str]) -> str | None:
    """返回列表中第一个在页面上存在的选择器。"""
    for sel in selectors:
        if page.has_element(sel):
            return sel
    return None
