# 部署说明（StatementCSV / BOB-25）

## 当前线上地址（免费子域，未买域名）

**https://statementcsv.spacebit.qzz.io**

- 跑在用户 Mac：`~/Projects/statement-csv`（gunicorn `127.0.0.1:8765`）
- 经已有 Cloudflare 命名隧道 `dsh-mac`（UUID `385790e0-…`）公网暴露
- launchd：`ai.statementcsv.app`（KeepAlive）
- DNS：`statementcsv.spacebit.qzz.io` → 该隧道（CNAME 已加）
- **未改动** DSH 认证门；本产品主机名直连 Flask，无 basic-auth

健康检查：`GET /health`

## 重新部署（改代码后）

在 Mac 上：

```bash
cd ~/Projects/statement-csv
git pull
source .venv/bin/activate
pip install -r requirements.txt
launchctl kickstart -k gui/$(id -u)/ai.statementcsv.app
curl -sS http://127.0.0.1:8765/health
curl -sS https://statementcsv.spacebit.qzz.io/health
```

若只改了隧道路由（少见）：

```bash
# 编辑 ~/.cloudflared/config.yml 后
launchctl kickstart -k gui/$(id -u)/ai.deepseek.dsh-tunnel
```

## Paddle 环境变量

复制 `.env.example` → `.env`，填入你在 Paddle 控制台拿到的 token / price id，然后：

```bash
# launchd 不会自动读 .env；可把变量写进 plist EnvironmentVariables，或：
set -a; source .env; set +a
launchctl kickstart -k gui/$(id -u)/ai.statementcsv.app
```

详见 [PADDLE_SETUP.md](PADDLE_SETUP.md)。

## 可选 PaaS（需你登录）

| 平台 | 配置 | 说明 |
|------|------|------|
| Fly.io | `fly.toml` + `Dockerfile` | `fly auth login` 后 `fly deploy` |
| Render | `render.yaml` | 连 GitHub 仓库 Free Web Service |

仓库：https://github.com/bobobo2026/statement-csv
