---
license: MIT-0
acceptLicenseTerms: true
name: threads-auth
description: Threads 认证管理。当用户要求登录、检查登录、切换账号时触发。
---
license: MIT-0
acceptLicenseTerms: true

# threads-auth — 认证管理

管理 Threads 登录状态与多账号切换。

## 前置条件：Chrome 必须先启动

所有命令依赖 Chrome 调试端口，使用前确认 Chrome 已运行：

```bash
# 启动 Chrome（默认端口 8666）
python scripts/chrome_launcher.py

# 已有实例时强制重启
python scripts/chrome_launcher.py --restart
```

Chrome 启动后会保持运行，无需每次重启。

## 登录说明

Threads 使用 **Instagram 账号**登录，Cookie 持久化在 `~/.threads/chrome-profile/`，**登录一次长期有效**，无需重复登录。

## 命令

### 检查登录状态

```bash
python scripts/cli.py check-login
```

实测返回（用户名提取有时失败，以 `logged_in` 字段为准）：
```json
{ "logged_in": true, "username": null, "message": "已登录（用户名获取失败）" }
{ "logged_in": false, "username": null, "message": "未登录，请执行 login 命令" }
```

### 登录

```bash
python scripts/cli.py login
```

执行后浏览器自动打开登录页，用户在浏览器中手动输入 Instagram 账号密码完成登录，Cookie 自动保存。登录完成后用 `check-login` 确认。

### 退出 / 切换账号

```bash
python scripts/cli.py delete-cookies
```

清除当前账号 Cookie，执行后需重新 `login`。

### 多账号管理

每个账号使用独立的 Chrome Profile 和调试端口（从 8667 递增），账号间完全隔离。

```bash
# 添加账号（自动分配端口）
python scripts/cli.py add-account --name "work" --description "工作号"

# 列出所有账号（含端口号）
python scripts/cli.py list-accounts

# 指定账号执行任意命令
python scripts/cli.py --account work check-login
python scripts/cli.py --account work post-thread --content "..."

# 设置默认账号
python scripts/cli.py set-default-account --name "work"

# 删除账号
python scripts/cli.py remove-account --name "work"
```

## 决策逻辑

1. **其他操作报错"未登录"** → 先 `check-login`，未登录则引导执行 `login`
2. **用户说"检查登录"** → `check-login`
3. **用户说"登录"** → `login`，提示在浏览器完成后确认
4. **用户说"退出"/"切换账号"** → `delete-cookies` 后 `login`
5. **用户说"换个号操作"** → `--account <name>` 参数，无需切换 Cookie

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 连接 Chrome 失败 | Chrome 未启动或端口错误 | 运行 `python scripts/chrome_launcher.py` |
| `logged_in: false` | Cookie 过期或未登录 | 执行 `login` |
| 登录页卡住 | 可能需要 2FA 或验证码 | 引导用户在浏览器中手动处理 |
