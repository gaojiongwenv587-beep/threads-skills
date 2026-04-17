# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a Vulnerability

如發現安全漏洞，**請勿直接開 Issue**，以避免漏洞在修復前被利用。

請通過以下方式私下回報：

- **GitHub**: 使用 [Private Vulnerability Reporting](https://github.com/gaojiongwenv587-beep/threads-skills/security/advisories/new)
- 收到回報後，我們將在 **72 小時內**確認並回覆修復計劃。

## Security Considerations

本項目基於 Chrome CDP 操控真實瀏覽器，請注意：

- **Cookie 安全**：Chrome Profile 存放在 `~/.threads/`，請勿將此目錄同步至公共雲端
- **命令行參數**：敏感內容（如帖子正文）通過文件傳遞，不建議直接寫入命令行參數（避免被 shell history 記錄）
- **多帳號隔離**：每個帳號使用獨立 Chrome Profile 和調試端口，帳號 Cookie 相互隔離
- **操作頻率**：請勿設置過高的自動化頻率，以避免觸發平台風控

## Scope

安全回報適用範圍：

- ✅ Cookie 或憑證洩露風險
- ✅ 命令注入漏洞
- ✅ 依賴項中的已知 CVE
- ❌ 平台封號風險（屬使用者責任，非代碼漏洞）
