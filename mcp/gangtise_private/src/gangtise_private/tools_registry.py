"""MCP 工具名到可调用实现的注册表。"""
from __future__ import annotations

from typing import Any, Callable, Dict

from .private_cloud import private_cloud_finder as private_cloud
from .private_meeting import private_meeting_finder as private_meeting
from .private_record import private_record_finder as private_record
from .stockpool import stockpool_finder as stockpool
from .wechat_message import wechat_message_finder as wechat_message


ToolHandler = Callable[..., Any]


TOOL_HANDLERS: Dict[str, ToolHandler] = {
    "private_record": private_record,
    "private_meeting": private_meeting,
    "private_cloud": private_cloud,
    "stockpool": stockpool,
    "wechat_message": wechat_message,
}

INTERNAL_PARAMS = frozenset(
    {
        "headers",
        "authorization",
        "append_file_hint",
        "meta",
        "meta_by_id",
        "indicator_meta",
        "kwargs",
    }
)
