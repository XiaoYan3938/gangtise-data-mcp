"""兼容 Docker `python /gateway.py`：转发到 src/http_gateway.py。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "src" / "http_gateway.py"
if not _PATH.is_file():
    # 已安装到 /opt/mcp/gangtise_mcp 时 http_gateway 与本文件同级
    _PATH = Path(__file__).resolve().parent / "http_gateway.py"

_SPEC = importlib.util.spec_from_file_location("http_gateway", _PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"无法加载 {_PATH}")
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
main = _MOD.main

if __name__ == "__main__":
    main()
