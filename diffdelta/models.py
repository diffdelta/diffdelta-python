"""Data models for DiffDelta feeds."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FeedItem:
    """A single item from a DiffDelta feed.

    Attributes:
        source: Source identifier (e.g. "cisa_kev", "nist_nvd").
        id: Unique item ID within the source.
        headline: Human/agent-readable headline.
        url: Link to the original source.
        excerpt: Summary text extracted from the source.
        published_at: When the item was originally published.
        updated_at: When the item was last updated.
        bucket: Which change bucket: "new", "updated", or "removed".
        provenance: Raw provenance data (fetched_at, evidence_urls, content_hash).
        raw: The full raw item dict from the feed.
    """

    source: str
    id: str
    headline: str
    url: str = ""
    excerpt: str = ""
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    bucket: str = "new"  # "new" | "updated" | "removed"
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, data: Dict[str, Any], bucket: str = "new") -> "FeedItem":
        """Create a FeedItem from a raw feed item dict."""
        content = data.get("content", {})
        excerpt = ""
        if isinstance(content, dict):
            excerpt = content.get("excerpt_text", "") or content.get("summary", "")
        elif isinstance(content, str):
            excerpt = content

        return cls(
            source=data.get("source", ""),
            id=data.get("id", ""),
            headline=data.get("headline", ""),
            url=data.get("url", ""),
            excerpt=excerpt,
            published_at=data.get("published_at"),
            updated_at=data.get("updated_at"),
            bucket=bucket,
            provenance=data.get("provenance", {}),
            raw=data,
        )

    def __repr__(self) -> str:
        return f"FeedItem(source={self.source!r}, id={self.id!r}, headline={self.headline!r}, bucket={self.bucket!r})"


@dataclass
class Head:
    """The lightweight head pointer for change detection.

    Attributes:
        cursor: Opaque cursor string for change detection.
        hash: Content hash of the latest feed.
        changed: Whether content has changed since last generation.
        generated_at: When this head was generated.
        ttl_sec: Recommended polling interval in seconds.
    """

    cursor: str
    hash: str = ""
    changed: bool = False
    generated_at: str = ""
    ttl_sec: int = 900

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "Head":
        return cls(
            cursor=data.get("cursor", ""),
            hash=data.get("hash", ""),
            changed=data.get("changed", False),
            generated_at=data.get("generated_at", ""),
            ttl_sec=data.get("ttl_sec", 900),
        )


@dataclass
class Feed:
    """A full DiffDelta feed response.

    Attributes:
        cursor: The new cursor (save this for next poll).
        prev_cursor: The previous cursor.
        source_id: Source ID (if per-source feed) or "global".
        generated_at: When this feed was generated.
        items: All items across all buckets.
        new: Items in the "new" bucket.
        updated: Items in the "updated" bucket.
        removed: Items in the "removed" bucket.
        narrative: Human-readable summary of what changed.
        raw: The full raw feed dict.
    """

    cursor: str
    prev_cursor: str = ""
    source_id: str = ""
    generated_at: str = ""
    items: List[FeedItem] = field(default_factory=list)
    new: List[FeedItem] = field(default_factory=list)
    updated: List[FeedItem] = field(default_factory=list)
    removed: List[FeedItem] = field(default_factory=list)
    narrative: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "Feed":
        buckets = data.get("buckets", {})

        new_items = [FeedItem.from_raw(i, "new") for i in buckets.get("new", [])]
        updated_items = [FeedItem.from_raw(i, "updated") for i in buckets.get("updated", [])]
        removed_items = [FeedItem.from_raw(i, "removed") for i in buckets.get("removed", [])]
        all_items = new_items + updated_items + removed_items

        return cls(
            cursor=data.get("cursor", ""),
            prev_cursor=data.get("prev_cursor", ""),
            source_id=data.get("source_id", ""),
            generated_at=data.get("generated_at", ""),
            items=all_items,
            new=new_items,
            updated=updated_items,
            removed=removed_items,
            narrative=data.get("batch_narrative", ""),
            raw=data,
        )


@dataclass
class SourceInfo:
    """Metadata about an available DiffDelta source.

    Attributes:
        source_id: Unique source identifier (e.g. "cisa_kev").
        name: Human-readable display name.
        tags: List of tags (e.g. ["security"]).
        description: Brief description of the source.
        homepage: URL of the source's homepage.
        enabled: Whether the source is currently active.
        status: Health status ("ok", "degraded", "error").
        head_url: Path to the source's head.json.
        latest_url: Path to the source's latest.json.
    """

    source_id: str
    name: str
    tags: List[str] = field(default_factory=list)
    description: str = ""
    homepage: str = ""
    enabled: bool = True
    status: str = "ok"
    head_url: str = ""
    latest_url: str = ""

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "SourceInfo":
        return cls(
            source_id=data.get("source_id", ""),
            name=data.get("name", ""),
            tags=data.get("tags", []),
            description=data.get("description", ""),
            homepage=data.get("homepage", ""),
            enabled=data.get("enabled", True),
            status=data.get("status", "ok"),
            head_url=data.get("head_url", ""),
            latest_url=data.get("latest_url", ""),
        )

    def __repr__(self) -> str:
        return f"SourceInfo(source_id={self.source_id!r}, name={self.name!r}, status={self.status!r})"
