"""Threads 自动化异常体系。

从 xiaohongshu-skills 的异常层级设计移植，保留通用结构，替换平台特定内容。
"""


class ThreadsError(Exception):
    """Threads 自动化基础异常。"""


class NotLoggedInError(ThreadsError):
    """未登录。"""

    def __init__(self) -> None:
        super().__init__("未登录，请先在浏览器中登录 Threads")


class PageNotAccessibleError(ThreadsError):
    """页面不可访问。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"页面不可访问: {reason}")


class PostNotFoundError(ThreadsError):
    """帖子不存在或已删除。"""

    def __init__(self) -> None:
        super().__init__("帖子不存在或已被删除")


class PublishError(ThreadsError):
    """发布失败。"""


class ContentTooLongError(PublishError):
    """内容超过长度限制（Threads 上限 500 字符）。"""

    def __init__(self, current: int, maximum: int = 500) -> None:
        self.current = current
        self.maximum = maximum
        super().__init__(f"内容长度 {current} 超过上限 {maximum} 字符")


class RateLimitError(ThreadsError):
    """操作频率过高。"""

    def __init__(self) -> None:
        super().__init__("操作太频繁，请稍后再试")


class CDPError(ThreadsError):
    """CDP 通信异常。"""


class ElementNotFoundError(ThreadsError):
    """页面元素未找到。"""

    def __init__(self, selector: str) -> None:
        self.selector = selector
        super().__init__(f"未找到元素: {selector}")


class NoFeedsError(ThreadsError):
    """未捕获到 Feed 数据。"""

    def __init__(self) -> None:
        super().__init__("未捕获到 Feed 数据")


class UploadTimeoutError(ThreadsError):
    """媒体上传超时。"""
