# 自我探索测评系统

Vue 3 + TypeScript / Django + PostgreSQL 的双测评项目，支持城市偏好测评（45道原题）与心理年龄测评（30道原题）。两套展示价格均为 **¥9.90（990分）**。默认部署为免费客户测试版。

## 本机 Docker 与公网测试

需要 Docker Desktop 已启动，以及 Python 3。首次启动：

```sh
./scripts/start-local.sh
```

脚本一次性生成密钥和管理账号，构建并启动前端、后端、PostgreSQL、Redis 和 Cloudflare 临时隧道。屏幕上会显示客户测试地址，也保存在 `.runtime/public-url.txt`。

- 本机网站：<http://localhost:18990>
- 本机管理后台：<http://localhost:18991/admin/>
- 管理账号：读取本机 `.runtime/admin-login.txt`，该文件不会提交到 GitHub。
- 客户流程：首页选择测评 → 开始免费体验 → **免付款进入答题** → 保存专属密码 → 答题 → 提交报告。

机器必须保持联网，Docker Desktop 必须运行。macOS 启动脚本通过本次登录会话的 launchd 任务持续运行 `caffeinate -i`，关闭启动终端后仍可防止空闲睡眠；停止脚本会移除该任务。合盖、关机、手动睡眠或网络中断仍会使服务中断。临时隧道进程重建后地址可能变化，重新运行启动脚本并转发新地址。

停止服务并保留数据库：

```sh
./scripts/stop-local.sh
```

查看状态及日志：

```sh
docker compose --profile public ps
docker compose logs --tail 100 backend
docker compose --profile public logs --tail 50 tunnel
```

## 二维码与真实收款

用户提供的原图固定为 `frontend/public/pay-qrcode.jpg`，付款页直接展示它。免费测试不会把订单标记成已付款，也不会创建真实支付记录。

**固定收款码不能自动关联网站订单。** `PAYMENT_MODE=manual` 下，运营方须核对客户提供的订单号和微信付款凭证，在本机后台填写凭证编号、保存订单，再执行“确认真实收款并发放权限”。人工退款也须先在微信完成，再填写退款凭证并执行“登记凭证并撤销权限”；后台操作不会替代资金退款。

收费前须完成题库、评分及报告审核，在版本后台批准内容，然后把 `.env` 的 `TEST_MODE` 改为 `False` 并重建后端。原城市资料中的正式权重矩阵存在空值，因此当前使用明确标注的客户体验规则；心理年龄也采用娱乐性体验规则。默认版本处于 `preview`，未批准时服务器拒绝真实收费下单。

可选微信商户 API 模式已修复签名、解密、商户/应用/金额/币种匹配、重复通知和主动查询。需要真实商户参数、受信平台公钥或证书及挂载密钥；默认未启用，也未做真实资金交易验收。手机当前使用固定图片收款流程，未承诺 JSAPI/H5 商户收银台上线。

## 数据与权限

每张订单固定购买时的商品、金额和题库版本。发布后的题目、选项与评分规则不可直接改写，新内容须创建新版本。客户端只有已保存的答案可以进入下一题，修订号防止多页面静默覆盖；提交和结果生成在同一事务完成。每个密码对应一份答卷，提交后可反复查看同一报告。

匿名写请求也强制校验 CSRF。订单绑定浏览器会话，答卷和结果需要已验证密码的授权。密码采用 HMAC 查询与 Fernet 加密保存；重发会撤销旧密码和旧会话。换浏览器可输入密码，或通过订单页生成一次性、5分钟有效的继续链接。退款会撤销访问权。运营操作有审计记录，公网入口屏蔽管理后台，数据库不开放宿主端口。

备份数据库：

```sh
./scripts/backup.sh
```

数据库备份与原始 `.env` 中的加密密钥必须一起妥善保留，否则无法恢复专属密码。不要使用 `docker compose down -v`，该参数会删除数据卷。旧代码已在本机修复前备份中保留；旧版明文密码由数据迁移加密并清空。

## 验证与维护

```sh
# 容器内真实 PostgreSQL 测试
docker compose exec backend python manage.py test --noinput

# 前端静态检查、测试、生产构建
cd frontend
npm ci
npm run lint
npm test
npm run build
```

后端包含完整题量、计分、访问隔离、CSRF、并发保存/提交、版本冻结、重发、退款、真实签名及金额校验测试；GitHub Actions 在推送时执行同类检查。

公网 API 冒烟测试会创建标注来源的免费测试答卷：

```sh
backend/venv/bin/python scripts/public-smoke.py https://你的地址.trycloudflare.com
```
