"""MCP 工具名到可调用实现的注册表。"""
from __future__ import annotations

from typing import Any, Callable, Dict

# 包 __init__ 在导入本模块前已执行完毕，可安全引用其中封装的入口函数。
from gangtise_agent import (
    earnings_review,
    hot_topic,
    investment_logic,
    peer_comparison,
    research_outline,
    security_clue,
    stock_one_line_summary,
    stock_one_pager,
    theme_tracking,
    viewpoint_debate,
)

ToolHandler = Callable[..., Any]

TOOL_HANDLERS: Dict[str, ToolHandler] = {
    "stock_one_pager": stock_one_pager,
    "investment_logic": investment_logic,
    "peer_comparison": peer_comparison,
    "earnings_review": earnings_review,
    "viewpoint_debate": viewpoint_debate,
    "theme_tracking": theme_tracking,
    "research_outline": research_outline,
    "stock_one_line_summary": stock_one_line_summary,
    "hot_topic": hot_topic,
    "security_clue": security_clue,
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
