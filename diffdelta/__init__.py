"""
DiffDelta — Agent-ready intelligence feeds.

    from diffdelta import DiffDelta

    dd = DiffDelta()
    for item in dd.poll(tags=["security"]):
        print(f"{item.source}: {item.headline}")

Full docs: https://diffdelta.io/#quickstart
"""

from diffdelta.client import DiffDelta
from diffdelta.models import FeedItem, SourceInfo, Feed, Head

__version__ = "0.1.0"
__all__ = ["DiffDelta", "FeedItem", "SourceInfo", "Feed", "Head"]
