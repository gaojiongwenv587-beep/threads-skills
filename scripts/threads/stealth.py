"""反检测配置：UA / Client Hints / Chrome 启动参数。

从 xiaohongshu-skills 提取。Threads 反爬机制较轻，主要保留：
- Chrome 启动参数（STEALTH_ARGS）— 完全通用
- UA 覆盖（build_ua_override）— 完全通用
- 基础 JS 注入 — 移除 webdriver 标志、伪造 chrome.runtime

关键原则：UA、navigator.platform、Client Hints 必须与实际平台一致。
"""

from __future__ import annotations

import platform as _platform

# Chrome 版本号 — 定期更新以匹配主流版本
_CHROME_VER = "136"
_CHROME_FULL_VER = "136.0.0.0"


def _build_platform_config() -> dict:
    """根据实际操作系统生成一致的 UA / Client Hints 配置。"""
    system = _platform.system()

    brands = [
        {"brand": "Chromium", "version": _CHROME_VER},
        {"brand": "Google Chrome", "version": _CHROME_VER},
        {"brand": "Not-A.Brand", "version": "24"},
    ]
    full_version_list = [
        {"brand": "Chromium", "version": _CHROME_FULL_VER},
        {"brand": "Google Chrome", "version": _CHROME_FULL_VER},
        {"brand": "Not-A.Brand", "version": "24.0.0.0"},
    ]

    if system == "Darwin":
        return {
            "ua": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{_CHROME_FULL_VER} Safari/537.36"
            ),
            "nav_platform": "MacIntel",
            "ua_metadata": {
                "brands": brands,
                "fullVersionList": full_version_list,
                "platform": "macOS",
                "platformVersion": "14.5.0",
                "architecture": "arm" if _platform.machine() == "arm64" else "x86",
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False,
            },
        }

    if system == "Windows":
        return {
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{_CHROME_FULL_VER} Safari/537.36"
            ),
            "nav_platform": "Win32",
            "ua_metadata": {
                "brands": brands,
                "fullVersionList": full_version_list,
                "platform": "Windows",
                "platformVersion": "15.0.0",
                "architecture": "x86",
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False,
            },
        }

    # Linux
    return {
        "ua": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{_CHROME_FULL_VER} Safari/537.36"
        ),
        "nav_platform": "Linux x86_64",
        "ua_metadata": {
            "brands": brands,
            "fullVersionList": full_version_list,
            "platform": "Linux",
            "platformVersion": "6.5.0",
            "architecture": "x86",
            "model": "",
            "mobile": False,
            "bitness": "64",
            "wow64": False,
        },
    }


PLATFORM_CONFIG = _build_platform_config()
REALISTIC_UA = PLATFORM_CONFIG["ua"]


def build_ua_override(chrome_full_ver: str | None = None) -> dict:
    """构建 Emulation.setUserAgentOverride 参数。

    Args:
        chrome_full_ver: Chrome 完整版本号（从 CDP /json/version 接口获取）。

    Returns:
        可直接传给 Emulation.setUserAgentOverride 的参数字典。
    """
    ver = chrome_full_ver or _CHROME_FULL_VER
    major = ver.split(".")[0]
    system = _platform.system()

    brands = [
        {"brand": "Chromium", "version": major},
        {"brand": "Google Chrome", "version": major},
        {"brand": "Not-A.Brand", "version": "24"},
    ]
    full_version_list = [
        {"brand": "Chromium", "version": ver},
        {"brand": "Google Chrome", "version": ver},
        {"brand": "Not-A.Brand", "version": "24.0.0.0"},
    ]

    if system == "Darwin":
        arch = "arm" if _platform.machine() == "arm64" else "x86"
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"
        )
        nav_platform, ua_platform, platform_ver = "MacIntel", "macOS", "14.5.0"
    elif system == "Windows":
        arch = "x86"
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"
        )
        nav_platform, ua_platform, platform_ver = "Win32", "Windows", "15.0.0"
    else:
        arch = "x86"
        ua = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"
        )
        nav_platform, ua_platform, platform_ver = "Linux x86_64", "Linux", "6.5.0"

    return {
        "userAgent": ua,
        "platform": nav_platform,
        "userAgentMetadata": {
            "brands": brands,
            "fullVersionList": full_version_list,
            "platform": ua_platform,
            "platformVersion": platform_ver,
            "architecture": arch,
            "model": "",
            "mobile": False,
            "bitness": "64",
            "wow64": False,
        },
    }


# 基础反检测 JS（移除 navigator.webdriver 标志，补全 chrome.runtime）
# Threads 反爬较轻，无需 XHS 那样的重型注入
STEALTH_JS = """
(() => {
    // 1. 移除 navigator.webdriver 标志
    const wd = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    if (wd && wd.get) {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: new Proxy(wd.get, { apply: () => false }),
            configurable: true,
        });
    }

    // 2. chrome.runtime — headless 模式下可能缺失
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) {
        window.chrome.runtime = { connect: () => {}, sendMessage: () => {} };
    }

    // 3. navigator.vendor
    Object.defineProperty(navigator, 'vendor', {
        get: () => 'Google Inc.',
        configurable: true,
    });
})();
"""

# Chrome 启动参数（通用反检测，与平台无关）
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-component-update",
    "--disable-extensions",
    "--disable-sync",
]
