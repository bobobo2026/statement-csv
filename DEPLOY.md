# 部署说明（StatementCSV / BOB-25）

## 当前公网方式（免费子域，无需买域名）

在本机 box 上跑 gunicorn，并用 Cloudflare **Quick Tunnel** 暴露 HTTPS：

```bash
cd /workspace/bob25/bank-statement-csv
bash scripts/deploy-tunnel.sh
cat tmp/live-url.txt
```

- URL 形如 `https://xxxx.trycloudflare.com`
- **不花广告费、不买域名**
- Quick Tunnel **重启后域名会变**；要固定域名需你自己的 Cloudflare/Fly 账号（我不能代登）

## 重新部署

```bash
cd /workspace/bob25/bank-statement-csv
bash scripts/deploy-tunnel.sh
```

改代码后同样再跑一遍即可。

## 可选：持久 PaaS（需你登录）

| 平台 | 配置文件 | 你需要做的 |
|------|----------|------------|
| Fly.io | `fly.toml` + `Dockerfile` | `fly auth login` → `fly launch` / `fly deploy` |
| Render | `render.yaml` + `Dockerfile` | 用 GitHub 连仓库，选 Free Web Service |

推送代码到 GitHub 后，在对应控制台导入即可。注入与 `.env.example` 相同的 Paddle 变量。

## 健康检查

`GET /health` → `{"status":"ok",...}`
