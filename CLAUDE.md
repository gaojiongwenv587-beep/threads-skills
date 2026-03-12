# threads-skills

Threads 自动化 Claude Code Skills，基于 Python CDP 浏览器自动化引擎。

## 开发命令

```bash
uv sync                    # 安装依赖
uv run ruff check .        # Lint 检查
uv run ruff format .       # 代码格式化
uv run pytest              # 运行测试
```

## 架构

双层结构：`scripts/` 是 Python CDP 自动化引擎，`skills/` 是 Claude Code Skills 定义（SKILL.md 格式）。

- `scripts/threads/` — 核心自动化库（模块化，每个功能一个文件）
- `scripts/cli.py` — 统一 CLI 入口，JSON 结构化输出
- `skills/*/SKILL.md` — 指导 Claude 如何调用 scripts/

### 调用方式

```bash
python scripts/cli.py check-login
python scripts/cli.py list-feeds
python scripts/cli.py post-thread --content "Hello Threads"
python scripts/cli.py search --query "关键词"
```

## 选择器维护流程（Threads 改版时）

所有 CSS 选择器集中在 `scripts/threads/selectors.py`，标注 ✅已验证 / ⚠️未验证。

**验证/更新流程：**
```bash
# 1. 启动 Chrome 并在浏览器里手动打开 threads.net
python scripts/chrome_launcher.py

# 2. 运行探针脚本（探查当前页面实际 DOM 结构）
uv run python scripts/inspector.py

# 探查登录页
uv run python scripts/inspector.py --url "https://www.threads.net/login"

# 3. 根据探针输出的 ✅命中 结果，更新 selectors.py 中对应选择器
# 4. 把 ⚠️未验证 标注改为 ✅已验证
```

探针脚本会输出：
- 每个候选选择器是否命中（✅/❌）
- 页面中所有 `aria-label` 和 `data-testid` 的枚举
- script 标签中 JSON 数据的结构摘要
- 第一个帖子容器的 HTML 片段

## 代码规范

- 行长度上限 100 字符
- 完整 type hints，使用 `from __future__ import annotations`
- 异常继承 `ThreadsError`（`threads/errors.py`）
- CLI exit code：0=成功，1=未登录，2=错误
- 用户可见错误信息使用中文
- JSON 输出 `ensure_ascii=False`

### 安全约束

- 发布类操作必须有用户确认机制
- 敏感内容通过文件传递，不内联到命令行参数
- Chrome Profile 目录隔离账号 cookies（存放在 `~/.threads/`）

## CLI 子命令

| CLI 子命令 | 分类 | 说明 |
|--|--|--|
| `check-login` | 认证 | 检查登录状态 |
| `login` | 认证 | 打开登录页等待用户手动登录 |
| `delete-cookies` | 认证 | 清除 cookies |
| `list-feeds` | 浏览 | 获取首页 Feed |
| `get-thread` | 浏览 | 获取单条 Thread 详情和回复 |
| `user-profile` | 浏览 | 获取用户主页 |
| `search` | 浏览 | 搜索 Threads |
| `post-thread` | 发布 | 发布新 Thread |
| `reply-thread` | 互动 | 回复 Thread |
| `like-thread` | 互动 | 点赞 Thread |
| `repost-thread` | 互动 | 转发 Thread |
| `follow-user` | 互动 | 关注用户 |
| `add-account` | 账号 | 添加账号 |
| `list-accounts` | 账号 | 列出账号 |
| `remove-account` | 账号 | 删除账号 |
| `set-default-account` | 账号 | 设置默认账号 |
