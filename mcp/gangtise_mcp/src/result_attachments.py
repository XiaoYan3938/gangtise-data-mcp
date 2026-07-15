"""从工具文本结果中提取本地路径，并以 MCP EmbeddedResource 附带返回。

- 单文件：原样传输（不压缩），按扩展名推断 mimeType
- 目录：打成 zip 后传输
- 文本中的 `` `/abs/path` `` 就地替换为 ``附件: `附件名` ``；
  准备失败则替换为失败说明；超过 ``_MAX_ATTACH_BYTES`` 时若配置了 OBS
  则上传并在正文给出 1 天有效期下载链接，否则说明过大已跳过
"""
from __future__ import annotations

import base64
import io
import mimetypes
import os
import re
import zipfile
from typing import List, Tuple, Union
from urllib.parse import quote

from mcp.types import BlobResourceContents, EmbeddedResource, TextContent

from obs_upload import is_configured as obs_is_configured
from obs_upload import try_upload_bytes

ContentItem = Union[TextContent, EmbeddedResource]

# 反引号包裹的 Unix 绝对路径：`/abs/path`（服务部署于 Linux / macOS）
_TICK_PATH_RE = re.compile(r"`(/[^`\n]+)`")
# 兼容尚未加反引号的 Unix 绝对路径
_BARE_ABS_RE = re.compile(r"(?<![`\w:])(/(?:[^\s`\"'<>|]+))")

# 默认最大嵌入附件体积；超出则改走 OBS（若已配置）
_MAX_ATTACH_BYTES = int(os.getenv("MCP_ATTACH_MAX_BYTES", str(32 * 1024 * 1024)))


def extract_local_paths(text: str) -> List[Tuple[str, str]]:
    """提取 (原文路径, 规范化绝对路径)，反引号优先，去重保序。"""
    if not text:
        return []
    found: List[Tuple[str, str]] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        p = raw.strip().rstrip(".,;:)")
        if not p.startswith("/") or p.startswith("//"):
            return
        try:
            norm = os.path.abspath(p)
        except Exception:
            return
        if norm in seen:
            return
        seen.add(norm)
        found.append((p, norm))

    for m in _TICK_PATH_RE.finditer(text):
        _add(m.group(1))
    for m in _BARE_ABS_RE.finditer(text):
        _add(m.group(1))
    return found


# 常见扩展名补充（部分环境 mimetypes 未收录）
_EXTRA_MIME = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
}


def _guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in _EXTRA_MIME:
        return _EXTRA_MIME[ext]
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, ext = os.path.splitext(name)
    i = 1
    while f"{stem}({i}){ext}" in used:
        i += 1
    out = f"{stem}({i}){ext}"
    used.add(out)
    return out


def _display_name(path: str, *, is_dir: bool = False) -> str:
    base = os.path.basename(path.rstrip("/")) or "attachment"
    if is_dir and not base.endswith(".zip"):
        return f"{base}.zip"
    return base


def _read_file_attachment(path: str) -> Tuple[str, str, bytes]:
    """单文件原样读取，返回 (文件名, mimeType, 字节)。"""
    name = os.path.basename(path) or "attachment.bin"
    with open(path, "rb") as f:
        data = f.read()
    return name, _guess_mime(name), data


def _zip_directory(path: str) -> Tuple[str, bytes]:
    """目录打 zip，返回 (zip 文件名, 字节)。"""
    base = os.path.basename(path.rstrip("/")) or "attachment"
    zip_name = f"{base}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(path):
            for fn in files:
                full = os.path.join(root, fn)
                if not os.path.isfile(full):
                    continue
                arc = os.path.join(base, os.path.relpath(full, path))
                zf.write(full, arcname=arc.replace("\\", "/"))
    return zip_name, buf.getvalue()


def _label_ok(name: str) -> str:
    return f"附件: `{name}`"


def _label_fail(name: str, reason: str) -> str:
    return f"附件: `{name}` {reason}"


def _label_obs(name: str, url: str) -> str:
    return f"附件: `{name}` 过大已上传 OBS（1天有效，到期自动删除）: {url}"


def _rewrite_paths(text: str, replacements: List[Tuple[str, str, str]]) -> str:
    """将文本中的绝对路径替换为标签。replacements: (原文路径, 规范化路径, 替换文本)。"""
    out = text
    # 先替换更长路径，避免前缀误伤
    ordered = sorted(replacements, key=lambda x: max(len(x[0]), len(x[1])), reverse=True)
    for raw, norm, label in ordered:
        for path in dict.fromkeys((raw, norm)):
            out = out.replace(f"`{path}`", label)
            # 裸路径仅做整段替换时风险较高，仅额外替换尚未被反引号包裹的完整路径 token
            out = re.sub(
                rf"(?<![`\w:]){re.escape(path)}(?![`\w])",
                label,
                out,
            )
    return out


def build_path_attachments(
    text: str,
    *,
    enabled: bool = True,
    max_bytes: int = _MAX_ATTACH_BYTES,
) -> Tuple[str, List[EmbeddedResource]]:
    """
    扫描文本中的本地路径并附带返回：
    - 成功：正文路径 → ``附件: `附件名` ``，并附 EmbeddedResource
    - 过大且已配 OBS：正文给出下载链接（对象 1 天后自动删除），不附 blob
    - 失败/过大未配 OBS：正文路径 → 准备失败 / 过大已跳过
    返回 (改写后文本, 附件列表)
    """
    if not enabled:
        return text or "", []

    attachments: List[EmbeddedResource] = []
    replacements: List[Tuple[str, str, str]] = []
    used_names: set[str] = set()

    for raw, norm in extract_local_paths(text):
        if not os.path.exists(norm):
            continue
        try:
            if os.path.isfile(norm):
                name, mime, data = _read_file_attachment(norm)
                name = _unique_name(name, used_names)
            elif os.path.isdir(norm):
                name, data = _zip_directory(norm)
                name = _unique_name(name, used_names)
                mime = "application/zip"
            else:
                continue
        except Exception as e:
            hint = _display_name(norm, is_dir=os.path.isdir(norm))
            replacements.append((raw, norm, _label_fail(hint, f"准备失败：{e}")))
            continue

        if len(data) > max_bytes:
            if obs_is_configured():
                try:
                    url = try_upload_bytes(data, name, content_type=mime)
                    if url:
                        replacements.append((raw, norm, _label_obs(name, url)))
                        continue
                except Exception as e:
                    replacements.append(
                        (
                            raw,
                            norm,
                            _label_fail(
                                name,
                                f"过大且 OBS 上传失败（{len(data)} bytes）：{e}",
                            ),
                        )
                    )
                    continue
            replacements.append(
                (
                    raw,
                    norm,
                    _label_fail(
                        name, f"过大已跳过（{len(data)} bytes，上限 {max_bytes}）"
                    ),
                )
            )
            continue

        safe_name = quote(name, safe="._-")
        attachments.append(
            EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    uri=f"attachment://{safe_name}",
                    mimeType=mime,
                    blob=base64.b64encode(data).decode("ascii"),
                ),
            )
        )
        replacements.append((raw, norm, _label_ok(name)))

    rewritten = _rewrite_paths(text or "", replacements)
    return rewritten, attachments


def with_path_attachments(
    text: str,
    *,
    enabled: bool = True,
) -> List[ContentItem]:
    """文本结果 + 可选路径附件；正文中的绝对路径就地替换为附件标签。"""
    body, attachments = build_path_attachments(text, enabled=enabled)
    items: List[ContentItem] = [TextContent(type="text", text=body)]
    items.extend(attachments)
    return items
