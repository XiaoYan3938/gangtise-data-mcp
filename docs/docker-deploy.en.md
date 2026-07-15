# Docker deploy

[简体中文](docker-deploy.md) | **English**

Only the **all-in-one** image (`mcps/Dockerfile`) is supported: `api/*` + `mcp/*` in one container, default gateway. Clients should use **`/mcp`** (full leaf tool set). Protocol/auth: [http-sse.en.md](http-sse.en.md). Entrypoint: [`mcp/gangtise_mcp/entrypoint.sh`](../mcp/gangtise_mcp/entrypoint.sh).

---

<details>
<summary><b>Build and run</b></summary>

```bash
cd gangtise-data-mcp   # the mcps/ directory in the repo
docker build -t gangtise-mcp -f Dockerfile .

# Optional pip mirror, e.g. Tsinghua:
# docker build -t gangtise-mcp -f Dockerfile \
#   --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
#   --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
#   .

docker run -d --name gangtise-mcp -p 8000:8000 \
  -e GTS_JWT_SECRET='change-me' \
  -e GTS_CRED_ENC_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  gangtise-mcp

# Optional: mount domains + hub + full behind the gateway
docker run -d -p 8000:8000 -e MCP_PACKAGE=all \
  -e GTS_JWT_SECRET='change-me' \
  -e GTS_CRED_ENC_KEY='...' \
  gangtise-mcp

curl -sS http://127.0.0.1:8000/health
```

Clients connect to `http://127.0.0.1:8000/mcp`. Do **not** bake open-platform AK/SK into the image; use OAuth consent or runtime headers.

</details>

<details>
<summary><b>Common env vars</b></summary>

| Variable | Default | Notes |
|----------|---------|--------|
| `MCP_TRANSPORT` | `both` | `both` / `http` / `sse` |
| `MCP_LAYOUT` | `gateway` | `gateway` (path proxy) / `unified` (single-process full tools) |
| `MCP_PACKAGE` | `domains` | `domains` / `all` / single-domain slug (e.g. `data`) |
| `GTS_MCP_ROOT` | `/opt/mcp` | contains `api/` and `mcp/` |
| `GTS_JWT_SECRET` | empty | JWT signing; required for OAuth |
| `GTS_CRED_ENC_KEY` | empty | Fernet; encrypts AK/SK in tokens; required for OAuth |
| `GTS_OAUTH_ISSUER` | empty | Public issuer behind HTTPS reverse proxy |
| `MCP_ATTACH_MAX_BYTES` | `33554432` | Inline attachment limit |
| `OBS_*` | empty | Optional large-attachment offload |

Generate a Fernet key:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Without OBS, oversized attachments are dropped. With OBS configured, upload and return a ~1-day URL. Build with `--build-arg INSTALL_OBS=1` to include the OBS SDK.

</details>

---

[HTTP / SSE](http-sse.en.md) · [Overview](../README.en.md)
