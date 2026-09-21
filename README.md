# 宽基估值分位定投提醒系统

监控 **沪深300 / 中证500 / 标普500 / 纳斯达克100** 的估值历史分位,在分位数跨越
买入阈值(40%)或卖出阈值(75%)、以及档位加深时,通过 **微信(Server酱)+ 邮件** 推送
定投/止盈提醒。**只提醒,不自动交易。**

- 运行:GitHub Actions 定时任务(北京时间每交易日 18:30),无需服务器,公共仓库零成本
- 查看:GitHub Pages 估值页面(分位卡片 + 近一年走势 + 信号历史),手机电脑均可访问
- 相关文档:需求见 `需求文档.md`,设计见 `技术方案.md`

## 快速部署(约 15 分钟,只需做一次)

以下步骤全部是**你个人需要操作的**,代码无需再改。

### 第 1 步:获取推送密钥(两选一,建议都配)

**Server酱(微信推送,推荐)**

1. 用微信扫码登录 [sct.ftqq.com](https://sct.ftqq.com)
2. 按页面提示关注「方糖服务号」
3. 在「Key&二维码」页面复制你的 **SendKey**(形如 `SCTxxxxxxxxxxx`)

**邮件(免费,推荐与 Server酱同配)**

1. 登录 [QQ 邮箱](https://mail.qq.com) → 设置 → 账号
2. 开启「POP3/IMAP/SMTP 服务」,按提示发短信获取**授权码**(16 位字母,不是 QQ 密码)
3. 发件邮箱就是你自己的 QQ 邮箱;想在微信里也收到邮件提醒,关注「QQ 邮箱提醒」公众号

### 第 2 步:创建 GitHub 仓库并上传代码

1. 在 GitHub 新建一个**公共仓库**(Public——公共仓库 Actions 免费不限量,且 GitHub Pages
   免费托管估值页面;仓库内无任何密钥,公开安全)
2. 把本项目目录所有文件推上去:

```bash
cd valuation-alert
git init && git add -A && git commit -m "init: 估值分位提醒系统"
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 第 3 步:配置 Secrets

仓库页面 → **Settings → Secrets and variables → Actions → New repository secret**,
逐个添加:

| Secret 名称 | 值 | 必需 |
|---|---|---|
| `SERVERCHAN_SENDKEY` | 第 1 步获取的 SendKey | 推荐 |
| `SMTP_USER` | 发件邮箱,如 `xxxx@qq.com` | 推荐 |
| `SMTP_AUTH_CODE` | QQ 邮箱 SMTP 授权码 | 推荐 |
| `SMTP_TO` | 收件邮箱(可与发件相同) | 推荐 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 可选 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可选 |

### 第 4 步:启用估值页面(GitHub Pages)

仓库 → **Settings → Pages** → Source 选 **Deploy from a branch** →
Branch 选 `main`、目录选 `/docs` → Save。
约 1 分钟后页面生效:`https://<用户名>.github.io/<仓库名>/`

### 第 5 步:验证

1. 仓库 → **Actions** 标签 → 选择 `valuation-monitor` → **Run workflow** → 运行
2. 首次正式运行会推送一条**「当前状态基线」**到微信和邮箱,展示四个指数当前所处区间
3. 打开 Pages 页面,应能看到四张估值卡片
4. 想单独测试推送:Run workflow 时选择 `test-push` 模式

之后每个交易日北京时间 18:30 自动运行;**没有信号就不打扰**,有跨越阈值或档位加深时
你会在微信/邮箱收到提醒。

## 日常使用

- **看估值**:打开 Pages 页面(可加到手机主屏幕),数据每交易日收盘后更新
- **改阈值/档位**:编辑 `config/indices.yaml`(买 40 / 卖 75、各档倍数与卖出比例)
- **增删指数**:同上,`source` 可选 `danjuan`(蛋卷)/ `multpl`(标普500)/ `nasdaq`(纳指100)
- **临时测推送**:Actions → Run workflow → 模式选 `test-push`
- **查运行日志**:Actions → 点进某次运行,每步日志完整保留(每源耗时/失败原因/推送结果)

## 本地开发

```bash
pip install -r requirements-dev.txt
python -m pytest                                  # 47 个单元测试(离线 fixtures)
PYTHONPATH=src python -m valuation_alert.main --dry-run    # 真实采集,只打印不推送
```

## 数据口径(重要)

| 指数 | 来源 | 口径 |
|---|---|---|
| 沪深300 / 中证500 | 蛋卷指数估值接口 | PE 近 10 年分位(日频) |
| 标普500 | multpl.com | 月度 PE 近 10 年窗口自算分位 |
| 纳斯达克100 | Nasdaq 官方 API | **收盘价近 10 年分位(代理口径,非 PE)** |

纳斯达克100 无免费 PE 历史序列,系统用价格分位代理并在推送与页面中明确标注;
标普500 的 PE 分位可作联动参考。历史分位不是绝对安全线,低估可能持续很久,
本系统所有输出仅为提醒参考,不构成投资建议。

## 项目结构

```
config/            指数/阈值/档位与推送渠道配置(YAML,改配置不改代码)
src/valuation_alert/
  datasources/     蛋卷 / multpl / Nasdaq 适配器(插件式,可加备用源)
  strategy.py      跨阈值判定与档位映射(纯函数)
  state.py         状态文件读写与幂等
  notify/          Server酱 / SMTP / Telegram 适配器 + 重试降级
  main.py          编排入口(--dry-run / --test-push)
docs/              GitHub Pages 估值页面(纯静态,无构建)
state/             previous_percentiles.json(策略状态,Actions 自动提交)
tests/             单元测试 + 三个数据源真实响应快照
.github/workflows/ monitor(定时+手动)与 test(单测)
```

## 常见问题

- **收不到推送**:先跑 `test-push` 模式看 Actions 日志;SendKey/授权码是否配对、
  是否关注了方糖服务号;Server酱免费版每天 5 条(本系统单日最多 1 条,一般不会触限)
- **页面显示"数据尚未生成"**:先手动 Run 一次 `valuation-monitor`
- **某指数采集失败**:不影响其他指数,消息中会注明"已跳过",下次运行自动重试;
  连续多日失败说明数据源可能改版,查看 Actions 日志定位
- **cron 延迟**:GitHub 定时任务高峰期可能晚几分钟到几十分钟,对收盘后提醒无影响;
  判定基于"上次成功运行"的分位,不会因延迟漏判
