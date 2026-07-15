# HTTP / SSE / OAuth

[简体中文](http-sse.md) | **English**

Remote MCP transport and auth. Client examples target the combined service (`gangtise_mcp` / gateway `/mcp`). Credentials: [open platform](https://open-platform.gangtise.com/).

---

## Transport

| Mode | Endpoint |
|------|----------|
| streamable-http | `POST /mcp` (gateway may use `/mcp/{slug}`) |
| SSE | `GET /sse` + `POST /messages/` |

Gateway health: `GET /health`.

---

<details>
<summary><b>OAuth (recommended for remote clients)</b></summary>

Env:

- `GTS_JWT_SECRET` — JWT HMAC
- `GTS_CRED_ENC_KEY` — Fernet (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- Optional `GTS_OAUTH_ISSUER=https://your-host` (set behind HTTPS reverse proxy)

| Path | Role |
|------|------|
| `/.well-known/oauth-authorization-server` | AS metadata |
| `/.well-known/oauth-protected-resource` | PRM |
| `/authorize` | Consent page (AK/SK) |
| `/token` | authorization_code / refresh_token |
| `/register` | Dynamic client registration (public clients) |

After OAuth, send `Authorization: Bearer <access_token>`.  
Access **1h**, refresh **30d** (refreshed by the **MCP client**). Server decrypts AK/SK and uses existing `loginV2`.

</details>

<details>
<summary><b>Header AK/SK (legacy-compatible)</b></summary>

```http
X-GTS-Credentials: {"accessKey":"...","secretKey":"..."}
```

Or separate `accessKey` / `secretKey` headers.

Without credentials, handshake and `tools/list` still work; tool calls return guidance with the open-platform link.

</details>

<details>
<summary><b>Client connection example</b></summary>

```json
{
  "mcpServers": {
    "gangtise": {
      "url": "https://<host>:<port>/mcp"
    }
  }
}
```

OAuth-capable clients open `/authorize` after connect. Local stdio: see recommended [`gangtise_mcp`](../mcp/gangtise_mcp/README.en.md).

</details>

---

See also: [Docker](docker-deploy.en.md) · [Overview](../README.en.md)
