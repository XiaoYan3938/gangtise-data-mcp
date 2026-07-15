# Docker 部署

**简体中文** | [English](docker-deploy.en.md)

仅提供 **整合镜像**（`mcps/Dockerfile`）：同一容器内装入 `api/*` + `mcp/*`，默认 gateway，客户端连 **`/mcp`**（全量叶子工具）。协议与鉴权见 [http-sse.md](http-sse.md)。入口：[`mcp/gangtise_mcp/entrypoint.sh`](../mcp/gangtise_mcp/entrypoint.sh)。

构建时分两类「源」：

| 类型 | 用途 | 国内怎么用 |
|------|------|------------|
| **基础镜像** `BASE_IMAGE` | 拉取官方 `python:3.11.9`（Docker Hub） | 默认即可。加速请在 **Docker Desktop / daemon** 配置 `registry-mirrors`，不要改成第三方镜像名当前缀（许多站点对匿名 `FROM` 已返回 **401**） |
| **pip 索引** | 安装 Python 依赖 | 文档示例统一用 **清华源** |

清华源只管 PyPI，**不能**代替 Docker Hub 拉基础镜像。

---

<details>
<summary><b>构建与运行</b></summary>

```bash
cd gangtise-data-mcp   # 即仓库中的 mcps/ 目录

docker build -t gangtise-mcp -f Dockerfile \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
  .

docker run -d --name gangtise-mcp -p 8000:8000 \
  -e GTS_JWT_SECRET='change-me' \
  -e GTS_CRED_ENC_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  gangtise-mcp

# 可选：网关同时挂载五域 + hub + 全量
docker run -d -p 8000:8000 -e MCP_PACKAGE=all \
  -e GTS_JWT_SECRET='change-me' \
  -e GTS_CRED_ENC_KEY='...' \
  gangtise-mcp

curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/.well-known/oauth-authorization-server | head
```

Docker Hub 拉不动时（超时 / 限流）：Docker Desktop → Settings → Docker Engine，加入例如：

```json
{
  "registry-mirrors": [
    "https://docker.xuanyuan.me",
    "https://docker.1ms.run"
  ]
}
```

Apply & restart 后再构建（`FROM` 仍写 `python:3.11.9`）。公共镜像站变动频繁，以你环境实测为准；公司内网请用自有镜像仓。

客户端连接 `http://127.0.0.1:8000/mcp`。**不要**把开放平台 AK/SK 写进镜像；用 OAuth 同意页或运行时请求头。

</details>

<details>
<summary><b>常用环境变量</b></summary>

| 变量 | 默认 | 说明 |
|------|------|------|
| `MCP_TRANSPORT` | `both` | `both` / `http` / `sse` |
| `MCP_LAYOUT` | `gateway` | `gateway`（子进程按路径反代）/ `unified`（单进程全量工具） |
| `MCP_PACKAGE` | `domains` | `domains` / `all` / 单域 slug（如 `data`） |
| `GTS_MCP_ROOT` | `/opt/mcp` | 下含 `api/` 与 `mcp/` |
| `GTS_JWT_SECRET` | 空 | OAuth JWT 签名；启用 OAuth 时必需 |
| `GTS_CRED_ENC_KEY` | 空 | Fernet，加密 token 内 AK/SK；启用 OAuth 时必需 |
| `GTS_OAUTH_ISSUER` | 空 | 对外 issuer（反代 HTTPS 时建议） |
| `MCP_ATTACH_MAX_BYTES` | `33554432` | 嵌入附件上限 |
| `OBS_*` | 空 | 超大附件外置（可选） |

生成 Fernet key：

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

未配置 OBS 时超出上限的附件会被舍弃；已配置则上传并返回约 1 天链接。构建安装 OBS SDK：`--build-arg INSTALL_OBS=1`。

</details>

---

[HTTP / SSE](http-sse.md) · [总览](../README.md)
