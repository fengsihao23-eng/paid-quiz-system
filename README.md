# 自我探索测评系统

完整的城市偏好（45题）与心理年龄（30题）娱乐测评。两套分别售卖，每套 **¥9.90（990分）**。支持固定微信码付款、人工核对收款、领取专属密码、保存与续答、一次提交以及反复查看同一报告。另有无需付款的客户测试版。

前端 Vue 3 + TypeScript，后端 Django + PostgreSQL，Docker 部署于本机，通过 Cloudflare 临时隧道提供 HTTPS 访问。

## 完整收费版

Docker Desktop 启动后，在项目目录执行：

```sh
./scripts/start-paid.sh
```

启动脚本生成独立密钥与管理账号，验证并发布完整娱乐测评内容，启动前端、后端、数据库、Redis 与隧道。公开网址保存于 `.runtime/paid-public-url.txt`。

- 本机网站：<http://localhost:18992>
- 收费版后台：<http://localhost:18993/admin/>
- 后台账号：本机 `.runtime/paid-admin-login.txt`，不会上传到 GitHub。
- 收费版配置：`.runtime/paid.env`，不会上传到 GitHub。

客户流程：选择测评 → 购买测评 → 扫描固定收款码支付 ¥9.90 → 将订单号与付款凭证发给商家 → 商家核对并开通 → 领取密码 → 答题 → 提交报告。

**固定微信收款码需要人工核对真实到账。** 当前 `PAYMENT_MODE=manual` 不会把点击「我已付款」当作付款确认。后台操作：

1. 使用收费版后台账号登录，搜索客户提供的订单号。
2. 核对微信实际到账记录和金额，填写「收款凭证编号」，保存订单。
同一收款凭证只能开通一张订单；已确认的凭证在后台锁定。

3. 回到订单列表，选中该单，执行「核对凭证后：确认真实收款并发放权限」。
4. 客户保持订单页打开，约10秒内会进入领取密码；也可点击「我已付款，查询开通」。

人工退款须先在微信完成，再填写「退款凭证编号」、保存并执行「登记凭证并撤销权限」。后台登记不会替代资金退款。密码丢失可在后台重发，旧密码与旧会话同时失效。

停止收费版并保留数据：

```sh
./scripts/stop-paid.sh
```

收费版数据库备份：

```sh
./scripts/backup.sh --paid
```

查看收费版服务状态：

```sh
docker compose -p paid-quiz-paid --env-file .runtime/paid.env -f docker-compose.yml -f docker-compose.paid.yml --profile public ps
```

## 免费客户测试版

```sh
./scripts/start-local.sh
```

公开网址保存于 `.runtime/public-url.txt`。本机网站 <http://localhost:18990>，管理后台 <http://localhost:18991/admin/>，后台账号保存在 `.runtime/admin-login.txt`。客户点击「开始免费体验 → 免付款进入答题」，无需扫码。

```sh
./scripts/stop-local.sh
./scripts/backup.sh
```

收费版和免费版使用不同数据库、密钥、后台账号、浏览器Cookie与公网地址。免费测试不会记为真实收款，测试密码属于免费版。收费版启动不会中断原来的客户测试入口。

## 本机服务器与数据

电脑需保持联网，Docker Desktop 必须运行。macOS 通过本次登录会话的 launchd 任务运行 `caffeinate -i` 防止空闲睡眠；关闭启动终端后仍可运行。合盖、关机、手动睡眠或网络中断仍会中断服务。两个停止脚本会在另一版本也停止后关闭防休眠。

临时隧道重建后网址可能变化，重新运行相应启动脚本并转发新地址。

数据库使用持久卷。备份数据库时须同时妥善保留该版本的配置与加密密钥，否则无法恢复专属密码。不要使用 `docker compose down -v` 删除数据卷。

## 内容与访问权限

保留完整原题，城市报告使用完整的逐题选项亲和矩阵、16座候选城市与11个维度；心理报告使用逐题显式计分、16至60岁的娱乐性映射与5种报告类型。内容用于娱乐与自我观察，不属于科学预测或专业心理评估。

完整收费版发布时核验题量、选项、评分覆盖与报告摘要，并记录运营账号及原因。新版本仍须通过发布校验；已发布题目、选项、评分和历史答卷不直接改写。每张订单固定购买时的题库版本、价格和货币。

匿名写请求强制校验 CSRF。订单绑定浏览器会话，答卷与报告须通过密码授权。密码采用 HMAC 查询和 Fernet 加密保存。修订号防止多页面覆盖答案；提交与报告生成在同一事务完成。退款撤销访问权限。公网入口关闭管理后台，数据库不开放宿主端口。

可选微信商户 API 模式已实现签名、解密、商户/应用/金额/币种匹配、重复通知与主动查询，需要真实商户参数和受信平台密钥。当前完整收费版采用用户提供的固定收款图片与人工确认流程。

## 验证

```sh
# 容器内实际 PostgreSQL 测试（隔离测试数据库，不涉及客户资金）
docker compose -p paid-quiz-paid --env-file .runtime/paid.env -f docker-compose.yml -f docker-compose.paid.yml exec backend python manage.py test --noinput

# 前端
cd frontend
npm ci
npm run lint
npm test
npm run build
```

后端覆盖免费与收费完整流程、45/30题报告、未付款禁领码、版本发布与审计、CSRF、权限隔离、并发保存与提交、内容冻结、重发、退款与商户签名验证。GitHub Actions 在推送时执行检查。

公网验收脚本：

```sh
backend/venv/bin/python scripts/paid-smoke.py
backend/venv/bin/python scripts/public-smoke.py
```

收费版公网脚本只创建带验收来源标记的待付款订单，不确认收款、不发生资金转账。完整收款确认及报告链在隔离测试数据库中验证。
