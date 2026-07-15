# gangtise-file-api

HTTP / SSE 形态的 Gangtise MCP（含 OAuth 与请求头鉴权）。

业务工具与脚本真源在对应 [`mcp/gangtise_file`](../../mcp/gangtise_file/)；本包依赖该 mcp 包并提供网络传输。

```bash
cd gangtise-data-mcp/api/gangtise_file
uv sync
uv run gangtise-file-api --transport both --host 0.0.0.0 --port 8000
```

stdio 本地接入请用 mcp 包入口，勿在本包寻找 `--transport stdio`。
