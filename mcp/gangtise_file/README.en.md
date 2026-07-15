<div align="center">

# Gangtise File MCP

[简体中文](README.md) | **English**

Reports, filings, notes, opinions, calendar, and file retrieval.

> **Recommended**: use the all-in-one package [`gangtise_mcp`](../gangtise_mcp/) for daily work. This page covers this package only.

[Repo overview](../../README.en.md) · [Credentials](https://open-platform.gangtise.com/)

</div>

---

## Tools

`report`, `summary`, `opinion`, `announcement`, `foreign_report`, `foreign_opinion`, `official_account`, `management_discuss`, `qa`, `report_image`, `investment_calendar`, `get_file`, `get_chiefs`, `get_institutions`, `get_industries`, `get_regions`, `get_announcement_types`

---

<details>
<summary><b>Install this package (Cursor / WorkBuddy)</b></summary>

Get keys from the [open platform](https://open-platform.gangtise.com/). Requires [uv](https://docs.astral.sh/uv/).

**Cursor** — Prefer sending the JSON below to the Cursor **Agent** to install (Accept when prompted); you can also write `~/.cursor/mcp.json` or project `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gangtise-file": {
      "command": "uvx",
      "args": [
        "--with",
        "git+https://github.com/XiaoYan3938/gangtise-data-mcp#subdirectory=mcp/gangtise_file",
        "--from",
        "git+https://github.com/XiaoYan3938/gangtise-data-mcp#subdirectory=mcp/gangtise_file",
        "gangtise-file-mcp"
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

This package is the **stdio** entry. HTTP/SSE + auth live in [`api/gangtise_file`](../../api/gangtise_file/):

```bash
cd gangtise-data-mcp/mcp/gangtise_file && uv sync && uv run gangtise-file-mcp   # stdio
cd ../../api/gangtise_file && uv sync && uv run gangtise-file-api --transport both --port 8000
```

CLI: [`cli/gangtise_file`](../../cli/gangtise_file/). Recommended client package: [`gangtise_mcp`](../gangtise_mcp/).

</details>

Chinese: [README.md](README.md)
