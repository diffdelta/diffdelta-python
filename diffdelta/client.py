"""DiffDelta client — the main interface for polling intelligence feeds."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests

from diffdelta.cursor import CursorStore
from diffdelta.models import Feed, FeedItem, Head, SourceInfo

DEFAULT_BASE_URL = "https://diffdelta.io"
DEFAULT_TIMEOUT = 15  # seconds


class DiffDelta:
    """Client for polling DiffDelta intelligence feeds.

    Usage::

        from diffdelta import DiffDelta

        dd = DiffDelta()

        # Poll for new items across all sources
        for item in dd.poll():
            print(f"{item.source}: {item.headline}")

        # Poll only security sources
        for item in dd.poll(tags=["security"]):
            print(f"🚨 {item.headline}")

        # Poll a specific source
        for item in dd.poll_source("cisa_kev"):
            print(item.headline)

    Args:
        base_url: DiffDelta API base URL. Defaults to https://diffdelta.io.
        api_key: Optional Pro/Enterprise API key (dd_live_...).
        cursor_path: Path to cursor persistence file. Set to None to disable persistence.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        cursor_path: Optional[str] = "",  # "" = default path, None = disabled
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Set up cursor persistence
        # Priority: explicit arg > DD_CURSOR_PATH env var > default (~/.diffdelta/)
        if cursor_path is None:
            self._cursors: Optional[CursorStore] = None
        else:
            resolved = cursor_path if cursor_path else os.environ.get("DD_CURSOR_PATH", "")
            self._cursors = CursorStore(resolved if resolved else None)

        # Set up HTTP session
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "diffdelta-python/0.1.1"
        if self.api_key:
            self._session.headers["X-DiffDelta-Key"] = self.api_key

    # ── Core polling ──

    def poll(
        self,
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        buckets: Optional[List[str]] = None,
    ) -> List[FeedItem]:
        """Poll the global feed for new items since last poll.

        Checks head.json first (400 bytes). Only fetches the full feed
        if the cursor has changed. Automatically saves the new cursor.

        Args:
            tags: Filter items to these tags (e.g. ["security"]).
            sources: Filter items to these source IDs (e.g. ["cisa_kev", "nist_nvd"]).
            buckets: Which buckets to return. Defaults to ["new", "updated"].
                     Use ["new", "updated", "removed"] to include removals.

        Returns:
            List of FeedItem objects that are new since your last poll.
            Empty list if nothing has changed.
        """
        if buckets is None:
            buckets = ["new", "updated"]

        cursor_key = "global"
        return self._poll_feed(
            head_url=f"{self.base_url}/diff/head.json",
            latest_url=f"{self.base_url}/diff/latest.json",
            cursor_key=cursor_key,
            tags=tags,
            sources=sources,
            buckets=buckets,
        )

    def poll_source(
        self,
        source_id: str,
        buckets: Optional[List[str]] = None,
    ) -> List[FeedItem]:
        """Poll a specific source for new items since last poll.

        More efficient than poll() with sources= filter if you only
        care about one source, since it fetches a smaller payload.

        Args:
            source_id: Source identifier (e.g. "cisa_kev").
            buckets: Which buckets to return. Defaults to ["new", "updated"].

        Returns:
            List of FeedItem objects that are new since your last poll.
        """
        if buckets is None:
            buckets = ["new", "updated"]

        cursor_key = f"source:{source_id}"
        return self._poll_feed(
            head_url=f"{self.base_url}/diff/source/{source_id}/head.json",
            latest_url=f"{self.base_url}/diff/source/{source_id}/latest.json",
            cursor_key=cursor_key,
            tags=None,
            sources=None,
            buckets=buckets,
        )

    def _poll_feed(
        self,
        head_url: str,
        latest_url: str,
        cursor_key: str,
        tags: Optional[List[str]],
        sources: Optional[List[str]],
        buckets: List[str],
    ) -> List[FeedItem]:
        """Internal: poll a feed with cursor comparison."""
        # Step 1: Fetch head.json (~400 bytes)
        head = self.head(head_url)

        # Step 2: Compare cursor
        stored_cursor = self._cursors.get(cursor_key) if self._cursors else None

        if stored_cursor and stored_cursor == head.cursor:
            # Nothing changed — return empty list
            return []

        # Step 3: Fetch full feed
        feed = self.fetch_feed(latest_url)

        # Step 4: Save new cursor
        if self._cursors and feed.cursor:
            self._cursors.set(cursor_key, feed.cursor)

        # Step 5: Filter and return
        items = []
        for item in feed.items:
            # Filter by bucket
            if item.bucket not in buckets:
                continue

            # Filter by source
            if sources and item.source not in sources:
                continue

            # Filter by tags (requires knowing source tags — use source index)
            if tags:
                # We need source metadata to filter by tags
                # Load source info if we haven't yet
                source_tags = self._get_source_tags()
                item_tags = source_tags.get(item.source, [])
                if not any(t in item_tags for t in tags):
                    continue

            items.append(item)

        return items

    # ── Low-level fetch methods ──

    def head(self, url: Optional[str] = None) -> Head:
        """Fetch a head.json pointer.

        Args:
            url: Full URL to head.json. Defaults to global head.

        Returns:
            Head object with cursor, hash, and metadata.
        """
        if url is None:
            url = f"{self.base_url}/diff/head.json"
        data = self._get_json(url)
        return Head.from_raw(data)

    def fetch_feed(self, url: Optional[str] = None) -> Feed:
        """Fetch a full latest.json feed.

        Args:
            url: Full URL to latest.json. Defaults to global latest.

        Returns:
            Feed object with all items, buckets, and metadata.
        """
        if url is None:
            url = f"{self.base_url}/diff/latest.json"
        data = self._get_json(url)
        return Feed.from_raw(data)

    def sources(self) -> List[SourceInfo]:
        """List all available DiffDelta sources.

        Returns:
            List of SourceInfo objects with metadata about each source.
        """
        data = self._get_json(f"{self.base_url}/diff/sources.json")
        return [SourceInfo.from_raw(s) for s in data.get("sources", [])]

    # ── Continuous monitoring ──

    def watch(
        self,
        callback: Callable[[FeedItem], None],
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        interval: Optional[int] = None,
        buckets: Optional[List[str]] = None,
    ) -> None:
        """Continuously poll and call a function for each new item.

        This runs an infinite loop. Use Ctrl+C to stop, or run in a thread.

        Args:
            callback: Function called for each new FeedItem.
            tags: Filter to these tags.
            sources: Filter to these source IDs.
            interval: Seconds between polls. Defaults to feed's TTL (usually 900s).
            buckets: Which buckets to process. Defaults to ["new", "updated"].

        Example::

            def handle(item):
                print(f"🚨 {item.source}: {item.headline}")
                # send_slack_alert(item)

            dd = DiffDelta()
            dd.watch(handle, tags=["security"])  # Runs forever
        """
        if buckets is None:
            buckets = ["new", "updated"]

        # Determine polling interval from feed TTL if not specified
        if interval is None:
            try:
                h = self.head()
                interval = max(h.ttl_sec, 60)  # At least 60 seconds
            except Exception:
                interval = 900  # Default 15 minutes

        print(f"[diffdelta] Watching for changes every {interval}s...")
        print(f"[diffdelta] Press Ctrl+C to stop.")

        while True:
            try:
                items = self.poll(tags=tags, sources=sources, buckets=buckets)
                if items:
                    print(f"[diffdelta] {len(items)} new item(s) found.")
                    for item in items:
                        callback(item)
                else:
                    print(f"[diffdelta] No changes.")
            except KeyboardInterrupt:
                print("\n[diffdelta] Stopped.")
                break
            except Exception as e:
                print(f"[diffdelta] Error: {e}. Retrying in {interval}s...")

            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[diffdelta] Stopped.")
                break

    # ── Cursor management ──

    def reset_cursors(self, source_id: Optional[str] = None) -> None:
        """Reset stored cursors so the next poll returns all current items.

        Args:
            source_id: Reset cursor for a specific source. None = reset all.
        """
        if self._cursors:
            if source_id:
                self._cursors.clear(f"source:{source_id}")
            else:
                self._cursors.clear()

    # ── Internal ──

    def _get_source_tags(self) -> Dict[str, List[str]]:
        """Cache source → tags mapping for tag-based filtering."""
        if not hasattr(self, "_source_tags_cache") or self._source_tags_cache is None:
            try:
                all_sources = self.sources()
                self._source_tags_cache = {
                    s.source_id: s.tags for s in all_sources
                }
            except Exception:
                self._source_tags_cache = {}
        return self._source_tags_cache

    def _get_json(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return parsed JSON."""
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def __repr__(self) -> str:
        tier = "pro" if self.api_key else "free"
        return f"DiffDelta(base_url={self.base_url!r}, tier={tier!r})"
