"""Threads 数据类型定义。

沿用 xiaohongshu-skills 的 dataclass 建模模式，
字段根据 Threads 平台实际结构重新定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ========== 用户 ==========


@dataclass
class ThreadsUser:
    user_id: str = ""
    username: str = ""
    display_name: str = ""
    avatar_url: str = ""
    is_verified: bool = False
    follower_count: str = ""
    following_count: str = ""
    bio: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ThreadsUser:
        return cls(
            user_id=d.get("id", d.get("pk", "")),
            username=d.get("username", ""),
            display_name=d.get("full_name", d.get("display_name", "")),
            avatar_url=d.get("profile_pic_url", d.get("avatar_url", "")),
            is_verified=d.get("is_verified", False),
            follower_count=str(d.get("follower_count", "")),
            following_count=str(d.get("following_count", "")),
            bio=d.get("biography", d.get("bio", "")),
        )

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "username": self.username,
            "displayName": self.display_name,
            "avatarUrl": self.avatar_url,
            "isVerified": self.is_verified,
            "followerCount": self.follower_count,
            "followingCount": self.following_count,
            "bio": self.bio,
        }


# ========== Thread 帖子 ==========


@dataclass
class ThreadPost:
    post_id: str = ""
    author: ThreadsUser = field(default_factory=ThreadsUser)
    content: str = ""
    like_count: str = ""
    reply_count: str = ""
    repost_count: str = ""
    quote_count: str = ""
    created_at: str = ""
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    is_liked: bool = False
    is_reposted: bool = False
    url: str = ""
    replies: list[ThreadPost] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ThreadPost:
        return cls(
            post_id=d.get("id", d.get("post_id", "")),
            author=ThreadsUser.from_dict(d.get("author", d.get("user", {}))),
            content=d.get("content", d.get("caption", d.get("text", ""))),
            like_count=str(d.get("like_count", d.get("likeCount", ""))),
            reply_count=str(d.get("reply_count", d.get("replyCount", ""))),
            repost_count=str(d.get("repost_count", d.get("repostCount", ""))),
            quote_count=str(d.get("quote_count", d.get("quoteCount", ""))),
            created_at=d.get("created_at", d.get("timestamp", "")),
            images=d.get("images", []),
            videos=d.get("videos", []),
            is_liked=d.get("has_liked", d.get("isLiked", False)),
            is_reposted=d.get("has_reposted", d.get("isReposted", False)),
            url=d.get("url", ""),
        )

    def to_dict(self) -> dict:
        result: dict = {
            "postId": self.post_id,
            "author": self.author.to_dict(),
            "content": self.content,
            "likeCount": self.like_count,
            "replyCount": self.reply_count,
            "repostCount": self.repost_count,
            "quoteCount": self.quote_count,
            "createdAt": self.created_at,
            "isLiked": self.is_liked,
            "isReposted": self.is_reposted,
            "url": self.url,
        }
        if self.images:
            result["images"] = self.images
        if self.videos:
            result["videos"] = self.videos
        if self.replies:
            result["replies"] = [r.to_dict() for r in self.replies]
        return result


# ========== Feed ==========


@dataclass
class FeedResponse:
    posts: list[ThreadPost] = field(default_factory=list)
    has_more: bool = False
    cursor: str = ""

    def to_dict(self) -> dict:
        return {
            "posts": [p.to_dict() for p in self.posts],
            "hasMore": self.has_more,
            "cursor": self.cursor,
        }


# ========== 搜索 ==========


@dataclass
class SearchResult:
    posts: list[ThreadPost] = field(default_factory=list)
    users: list[ThreadsUser] = field(default_factory=list)
    query: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "posts": [p.to_dict() for p in self.posts],
            "users": [u.to_dict() for u in self.users],
        }


# ========== 用户主页 ==========


@dataclass
class UserProfile:
    user: ThreadsUser = field(default_factory=ThreadsUser)
    posts: list[ThreadPost] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "user": self.user.to_dict(),
            "posts": [p.to_dict() for p in self.posts],
        }


# ========== 发布 ==========


@dataclass
class PublishContent:
    """Thread 发布内容。"""

    content: str = ""
    image_paths: list[str] = field(default_factory=list)
    reply_to_post_id: str = ""  # 回复目标，空表示独立新帖


# ========== 互动结果 ==========


@dataclass
class ActionResult:
    """通用动作响应（点赞/转发/关注等）。"""

    post_id: str = ""
    success: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "postId": self.post_id,
            "success": self.success,
            "message": self.message,
        }
