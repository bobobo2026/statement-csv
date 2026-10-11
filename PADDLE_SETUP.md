# Paddle 开户与接收银（你本人完成）

代码已接好 Overlay Checkout：填环境变量后定价页按钮会打开 Paddle 结账。
**我不能替你注册商户或上传证件**——下面每一步都要你自己在浏览器完成。

## 你需要做的（按顺序）

1. 打开 [Paddle Sandbox 注册](https://sandbox-login.paddle.com/signup)（先沙盒，不要直接上正式环境）。
2. 用你的邮箱完成注册与邮箱验证。
3. 在 Dashboard 填写卖家资料（个人/sole trader 或公司）。大陆个人能否过审**未核验**，被拒就改走 Lemon Squeezy→PayPal 备选（见 `/workspace/cn-individual-payout-compare.md`）。
4. 按提示上传身份/地址证明（KYC）——**停在这里等你**：我无法代传证件。
5. **Catalog → Products**：建一个产品，例如 `StatementCSV page credits`。
6. 为该产品建三个 **Price**（一次性）：
   - Starter · $9 · 100 pages → 记下 `pri_…`
   - Pro · $29 · 400 pages → 记下 `pri_…`
   - Bulk · $79 · 1500 pages → 记下 `pri_…`
7. **Developer tools → Authentication → Client-side tokens**：创建沙盒 token（以 `test_` 开头）。
8. **Checkout → Default payment link**：沙盒可填 `localhost`；上线后把公网域名加入 Website approval。
9. 把值写进项目根目录 `.env`（可从 `.env.example` 复制）：

```bash
PADDLE_ENV=sandbox
PADDLE_CLIENT_TOKEN=test_你的token
PADDLE_PRICE_STARTER=pri_xxx
PADDLE_PRICE_PRO=pri_yyy
PADDLE_PRICE_BULK=pri_zzz
```

10. 重启服务：`bash scripts/deploy-tunnel.sh`（或你的 PaaS 重启并注入同样环境变量）。
11. 打开 `/pricing`，点 Buy，用 [Paddle 测试卡](https://developer.paddle.com/concepts/payment-methods/credit-debit-card) 走通沙盒。
12. 沙盒 OK 后再开 **Live** 工作区，换 `live_` token 与正式 `pri_`，设 `PADDLE_ENV=production`。

## 我已做好的部分

- 定价页 Paddle.js Overlay Checkout
- 环境变量注入（无假凭证）
- 未配置时按钮保持 disabled，转换工具仍可免费用

## 还没做（接好收银后再做）

- 购买成功后的「页数额度」记账与扣减
- Paddle webhook 验签与履约邮件
