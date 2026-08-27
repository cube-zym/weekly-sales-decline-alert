# weekly-sales-decline-alert

亚马逊周度销量预警 Skill：自动从**领星 ERP** 拉取店铺周度销量 → 识别环比下跌 SKU/ASIN → 可选调用**西柚洞察**做归因（价格/评分/评论、自然/广告流量两周对比）→ 生成 HTML 报告 → 可选通过 **AgentMail** 发送邮件。

## 目录结构

```
weekly-sales-decline-alert/
├── SKILL.md               # Skill 定义（触发条件 + 参数化工作流 + 隐私红线）
├── scripts/
│   ├── fetch_listing.sh   # 拉取领星 erp_listing 分页数据（curl 直连）
│   ├── analyze.py         # 环比计算 + 筛选下跌 + 负责人聚合 + HTML 生成
│   └── xiyou_deep.py      # 西柚 TopN 归因（价格/评分/流量两周对比）
└── README.md
```

## 安装

```bash
# 方式一：克隆到用户级 skill 目录（跨工具可用）
git clone https://github.com/cube-zym/weekly-sales-decline-alert.git ~/.agents/skills/weekly-sales-decline-alert

# 方式二：仅作为普通仓库使用
git clone https://github.com/cube-zym/weekly-sales-decline-alert.git
```

## 前置条件

| 依赖 | 用途 | 检查方式 |
|---|---|---|
| 领星 MCP | 销量数据 | `~/.zcode/cli/config.json` 中 `mcp.servers["LingXing-MCP"]` |
| 西柚 MCP（可选） | 归因分析 | `mcp.servers["xydc-mcp"]` |
| AgentMail CLI（可选） | 发送邮件 | `agently-cli auth status` |
| curl / python3 | 脚本运行 | — |

> **凭证安全**：所有脚本从本地 `~/.zcode/cli/config.json` 动态读取密钥，**仓库内不包含任何密钥**。公开部署无需担心泄露。

## 使用示例（对 AI 助手说）

- 「跑一下本周销量预警周报」
- 「给运营发一份上周环比下跌的 ASIN 清单」
- 「销量预警，跌幅超过 20% 的单独标出，不发邮件只生成报告」

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| 收件人 | 每次确认 | 邮件收件人 |
| 跌幅阈值 | 0（全部下跌） | 只列跌幅 ≥ 该值的 ASIN |
| 西柚归因 | Top 10 | 对跌幅 Top N 做两周归因 |
| 发送邮件 | 是 | 是否 AgentMail 发送 |
| 对比周期 | 上周 vs 上上周 | 近 7 天 vs 14 天前段 |

## 数据口径

- 上周销量 = `average_seven_volume × 7`
- 上上周销量 = `fourteen_volume − 上周`
- 仅统计两周均有销量的 ASIN；覆盖 Top 500 listing（约 478 个有销量 ASIN）

## 隐私声明

- 本仓库公开，**不含**任何密钥、token、真实邮箱、员工姓名或业务数据。
- 使用中请勿将上述信息写入任何会被推送的文件；邮件收件人仅在运行时由用户提供。
