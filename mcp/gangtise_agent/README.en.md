<div align="center">

# Gangtise Agent MCP

[简体中文](README.md) | **English**

Research agents: one-pagers, investment logic, peer comparison, earnings review, debates, themes, etc.

> **Recommended**: use the all-in-one package [`gangtise_mcp`](../gangtise_mcp/) for daily work. This page covers this package only.

[Repo overview](../../README.en.md) · [Credentials](https://open-platform.gangtise.com/)

</div>

---

## Tools

`stock_one_pager`, `investment_logic`, `peer_comparison`, `earnings_review`, `viewpoint_debate`, `theme_tracking`, `research_outline`, `stock_one_line_summary`, `hot_topic`, `security_clue`

---

<details>
<summary><b>Install this package (Cursor / WorkBuddy)</b></summary>

Get keys from the [open platform](https://open-platform.gangtise.com/). Requires [uv](https://docs.astral.sh/uv/).

**Cursor** — Prefer sending the JSON below to the Cursor **Agent** to install (Accept when prompted); you can also write `~/.cursor/mcp.json` or project `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gangtise-agent": {
      "command": "uvx",
      "args": [
        "--with",
        "git+https://github.com/XiaoYan3938/gangtise-data-mcp#subdirectory=mcp/gangtise_agent",
        "--from",
        "git+https://github.com/XiaoYan3938/gangtise-data-mcp#subdirectory=mcp/gangtise_agent",
        "gangtise-agent-mcp"
      ],
      "env": {
        "GTS_ACCESS_KEY": "YOUR_ACCESS_KEY",
        "GTS_SECRET_KEY": "YOUR_SECRET_KEY"
      }
    }
  }
}
```

**WorkBuddy** — Send the MCP JSON to the WorkBuddy **agent** to install; then open sidebar **Expert · Skills · Connectors** → **Connectors** → **Custom connectors** / **My MCP**, **Trust** and enable. Prefer the all-in-one package — see [`gangtise_mcp`](../gangtise_mcp/) and [repo README](../../README.en.md).

Full platform folds: [`gangtise_mcp`](../gangtise_mcp/README.en.md) and [repo README](../../README.en.md).

</details>

<details>
<summary><b>Remote HTTP / Docker</b></summary>

- HTTP / SSE / OAuth: [http-sse.en.md](../../docs/http-sse.en.md)
- Docker: all-in-one only — [docker-deploy.en.md](../../docs/docker-deploy.en.md)

</details>


<details>
<summary><b>Run locally (dev)</b></summary>

This package is the **stdio** entry. HTTP/SSE + auth live in [`api/gangtise_agent`](../../api/gangtise_agent/):

```bash
cd gangtise-data-mcp/mcp/gangtise_agent && uv sync && uv run gangtise-agent-mcp   # stdio
cd ../../api/gangtise_agent && uv sync && uv run gangtise-agent-api --transport both --port 8000
```

CLI: [`cli/gangtise_agent`](../../cli/gangtise_agent/). Recommended client package: [`gangtise_mcp`](../gangtise_mcp/).

</details>

Chinese: [README.md](README.md)
