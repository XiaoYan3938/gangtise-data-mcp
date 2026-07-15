# HTTP / SSE / OAuth

**简体中文** | [English](http-sse.en.md)

远程 MCP 传输与鉴权说明。客户端示例默认连接整合服务（`gangtise_mcp` / gateway 的 `/mcp`）。账号：[开放平台](https://open-platform.gangtise.com/)。

---

## 传输

| 模式 | 端点 |
|------|------|
| streamable-http | `POST /mcp`（网关可为 `/mcp/{slug}`） |
| SSE | `GET /sse` + `POST /messages/` |

整合网关健康检查：`GET /health`。

---

<details>
<summary><b>OAuth（推荐远程客户端）</b></summary>

环境变量：

- `GTS_JWT_SECRET` — JWT HMAC
- `GTS_CRED_ENC_KEY` — Fernet（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`）
- 可选 `GTS_OAUTH_ISSUER=https://your-host`（反代 HTTPS 时建议设置）

| 路径 | 说明 |
|------|------|
| `/.well-known/oauth-authorization-server` | AS metadata |
| `/.well-known/oauth-protected-resource` | PRM |
| `/authorize` | 同意页（填写 AK/SK） |
| `/token` | authorization_code / refresh_token |
| `/register` | 动态客户端注册（公开客户端） |

客户端完成 OAuth 后带 `Authorization: Bearer <access_token>`。  
access **1 小时**，refresh **30 天**；刷新由 **MCP 客户端**完成。服务端解密 AK/SK 后仍走 `loginV2`。

</details>

<details>
<summary><b>请求头 AK/SK（兼容）</b></summary>

```http
X-GTS-Credentials: {"accessKey":"...","secretKey":"..."}
```

或分头 `accessKey` / `secretKey`。

未带凭证时可完成握手与 `tools/list`；调用工具时返回引导文案（含开放平台链接）。

</details>

<details>
<summary><b>客户端连接示例</b></summary>

Cursor / 多数支持 URL 的客户端：

```json
{
  "mcpServers": {
    "gangtise": {
      "url": "https://<host>:<port>/mcp"
    }
  }
}
```

支持 MCP OAuth 时连接后打开 `/authorize`。WorkBuddy 等本地配置见 [仓库 README](../README.md)。

stdio 本地安装默认用环境变量 AK/SK，见推荐包 [`gangtise_mcp`](../mcp/gangtise_mcp/)。

</details>

---

相关：[Docker 部署](docker-deploy.md) · [总览](../README.md)
