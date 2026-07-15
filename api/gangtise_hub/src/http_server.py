"""Gangtise Hub MCP HTTP/SSE — OAuth/鉴权在本包；路由逻辑来自 mcp/gangtise_hub。

仅 `--transport http|sse|both`（默认 both）。stdio 请用 gangtise-hub-mcp。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import sys
from contextlib import asynccontextmanager, redirect_stdout
from contextvars import copy_context
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple


def _ensure_layer_paths() -> None:
    here = Path(__file__).resolve().parent
    paths = [here]
    if here.name == "src":
        pkg = here.parent.name
        mcps_root = here.parents[2]
        paths.append(mcps_root / "mcp" / pkg / "src")
        for dom in (
            "gangtise_agent",
            "gangtise_data",
            "gangtise_file",
            "gangtise_kb",
            "gangtise_private",
        ):
            paths.append(mcps_root / "mcp" / dom / "src")
    for p in paths:
        s = str(p)
        if p.is_dir() and s not in sys.path:
            sys.path.insert(0, s)


_ensure_layer_paths()

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import EmbeddedResource, TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from authorization import (
    is_auth_configured,
    reset_request_credentials,
    set_request_credentials,
)
from oauth_asgi import oauth_routes
from oauth_tokens import TokenConfigError, decode_access_token, oauth_configured
from domains import DOMAINS, ROUTER_INPUT_SCHEMA, domain_tool_description
from package_loader import preload_all
from result_attachments import with_path_attachments
from router import route

SERVER_NAME = "gangtise-hub-mcp"
SERVER_VERSION = "0.1.0"

_CREDENTIALS_HEADER_NAMES = (
    "x-gts-credentials",
    "gts-credentials",
    "x-gangtise-credentials",
)


def _auth_missing_message() -> str:
    return (
        "未配置 Gangtise 授权（AccessKey / SecretKey）\n"
        "请前往 https://open-platform.gangtise.com/ 进行账号登陆/申请并获取凭证\n"
        "登陆后在`我的账号`->`账号列表`页面最下方查看 Access Key 和 Secret Key\n"
        "再通过环境变量、本地凭证文件或请求头配置后使用"
        "（提示：action=list / read_ref 无需凭证；仅 action=call 需要）"
    )


def _check_auth_env() -> str | None:
    if is_auth_configured():
        return None
    return _auth_missing_message()


def _normalize_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    return str(result)


server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name=d.tool_name,
            description=domain_tool_description(d),
            inputSchema=ROUTER_INPUT_SCHEMA,
        )
        for d in DOMAINS
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: Dict[str, Any]
) -> List[TextContent | EmbeddedResource]:
    args = dict(arguments or {})
    action = str(args.get("action") or "list").strip().lower()

    if action == "call":
        auth_err = _check_auth_env()
        if auth_err:
            return [TextContent(type="text", text=auth_err)]

    text, invoke, _runtime = route(name, args)
    if invoke is None:
        return [TextContent(type="text", text=text or "(empty)")]

    handler, filtered = invoke
    try:
        ctx = copy_context()

        def _invoke():
            buf = io.StringIO()
            with redirect_stdout(buf):
                out = handler(**filtered)
            return out, buf.getvalue()

        result, stdout_text = await asyncio.to_thread(ctx.run, _invoke)
    except TypeError as e:
        return [TextContent(type="text", text=f"参数错误: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"调用失败: {e}")]

    out_text = _normalize_result(result)
    if stdout_text:
        out_text = stdout_text + out_text
    attach = True
    if os.getenv("MCP_ATTACH_FILES", "").lower() in ("0", "false", "no", "off"):
        attach = False
    return with_path_attachments(out_text, enabled=attach)


def _parse_credentials_payload(raw: str) -> Optional[Tuple[str, str]]:
    text = (raw or "").strip()
    if not text:
        return None
    if not text.startswith("{"):
        try:
            decoded = base64.b64decode(text, validate=True).decode("utf-8")
            if decoded.strip().startswith("{"):
                text = decoded.strip()
        except Exception:
            pass
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    ak = data.get("accessKey") or data.get("access_key")
    sk = data.get("secretKey") or data.get("secret_key") or data.get("secretAccessKey")
    if ak and sk:
        return str(ak).strip(), str(sk).strip()
    return None


def _parse_credentials_from_headers(headers: Dict[str, str]) -> Optional[Tuple[str, str]]:
    for hname in _CREDENTIALS_HEADER_NAMES:
        if hname in headers:
            parsed = _parse_credentials_payload(headers[hname])
            if parsed:
                return parsed
    ak = headers.get("accesskey") or headers.get("x-access-key") or headers.get("access-key")
    sk = (
        headers.get("secretkey")
        or headers.get("x-secret-key")
        or headers.get("secret-key")
        or headers.get("secretaccesskey")
    )
    if ak and sk:
        return ak.strip(), sk.strip()
    return None


def _headers_dict(scope: Scope) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in scope.get("headers") or []:
        out[key.decode("latin-1").lower()] = value.decode("latin-1")
    return out


class RequestCredentialsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers_dict(scope)
        creds = None
        auth = headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            bearer = auth[7:].strip()
            if bearer and oauth_configured():
                try:
                    creds = decode_access_token(bearer)
                except TokenConfigError:
                    creds = None
        if not creds:
            creds = _parse_credentials_from_headers(headers)
        token = None
        if creds:
            token = set_request_credentials(creds[0], creds[1])
        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                reset_request_credentials(token)


class _StreamableHTTPASGIApp:
    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


def _normalize_path(path: str, *, trailing_slash: bool = False) -> str:
    p = path if str(path).startswith("/") else f"/{path}"
    if trailing_slash and not p.endswith("/"):
        p = f"{p}/"
    if not trailing_slash and len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def _build_network_app(
    *,
    enable_http: bool,
    enable_sse: bool,
    path: str,
    sse_path: str,
    message_path: str,
    json_response: bool,
    stateless: bool,
) -> ASGIApp:
    path = _normalize_path(path)
    sse_path = _normalize_path(sse_path)
    message_path = _normalize_path(message_path, trailing_slash=True)

    routes: list[Any] = list(oauth_routes())
    session_manager: StreamableHTTPSessionManager | None = None

    if enable_http:
        session_manager = StreamableHTTPSessionManager(
            app=server,
            json_response=json_response,
            stateless=stateless,
        )
        routes.append(Route(path, endpoint=_StreamableHTTPASGIApp(session_manager)))

    if enable_sse:
        sse = SseServerTransport(message_path)

        async def handle_sse(request: Request) -> Response:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # type: ignore[attr-defined]
                await server.run(
                    streams[0],
                    streams[1],
                    server.create_initialization_options(),
                )
            return Response()

        routes.append(Route(sse_path, endpoint=handle_sse, methods=["GET"]))
        routes.append(Mount(message_path, app=sse.handle_post_message))

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        if session_manager is not None:
            async with session_manager.run():
                yield
        else:
            yield

    return RequestCredentialsMiddleware(Starlette(routes=routes, lifespan=lifespan))


def _run_network(**kwargs) -> None:
    import uvicorn
    app = _build_network_app(**{k: kwargs[k] for k in (
        "enable_http", "enable_sse", "path", "sse_path", "message_path", "json_response", "stateless"
    )})
    uvicorn.run(app, host=kwargs["host"], port=kwargs["port"], log_level="info")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="gangtise-hub-api")
    parser.add_argument("--transport", choices=("http", "sse", "both"), default=os.getenv("MCP_TRANSPORT", "both"))
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8000")))
    parser.add_argument("--path", default=os.getenv("MCP_PATH", "/mcp"))
    parser.add_argument("--sse-path", default=os.getenv("MCP_SSE_PATH", "/sse"))
    parser.add_argument("--message-path", default=os.getenv("MCP_MESSAGE_PATH", "/messages/"))
    parser.add_argument("--stateless", action=argparse.BooleanOptionalAction,
                        default=os.getenv("MCP_STATELESS", "true").lower() in ("1", "true", "yes", "on"))
    parser.add_argument("--json-response", action=argparse.BooleanOptionalAction,
                        default=os.getenv("MCP_JSON_RESPONSE", "true").lower() in ("1", "true", "yes", "on"))
    return parser.parse_args(argv)


def _apply_network_gts_save_file_default() -> None:
    os.environ.setdefault("GTS_SAVE_FILE", "False")
    value = os.environ["GTS_SAVE_FILE"]
    for mod_name in (
        "gangtise_agent.utils", "gangtise_data.utils", "gangtise_file.utils",
        "gangtise_kb.utils", "gangtise_private.utils",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "GTS_SAVE_FILE"):
            setattr(mod, "GTS_SAVE_FILE", value)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    preload_all()
    _apply_network_gts_save_file_default()
    transport: Literal["http", "sse", "both"] = args.transport  # type: ignore[assignment]
    _run_network(
        host=args.host,
        port=args.port,
        enable_http=transport in ("http", "both"),
        enable_sse=transport in ("sse", "both"),
        path=args.path,
        sse_path=args.sse_path,
        message_path=args.message_path,
        json_response=args.json_response,
        stateless=args.stateless,
    )


if __name__ == "__main__":
    main()
