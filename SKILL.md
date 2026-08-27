---
name: weekly-sales-decline-alert
description: 亚马逊周度销量预警周报。自动从领星 ERP 拉取店铺周度销量、识别环比上周下跌的 SKU/ASIN，可选调用西柚洞察做归因（价格/评分/评论/自然与广告流量两周对比），生成 HTML 报告，并可选通过 AgentMail 发送邮件。用户提到「周报」「销量预警」「销量下跌」「环比下降」「给 xx 发周报/发邮件」「跑一遍销量预警」等表述时使用——即使没有明确说 skill 也应触发。
---

# 周度销量预警周报（Weekly Sales Decline Alert）

把「领星拉销量 → 环比找下跌 → 西柚归因 → HTML 报告 → AgentMail 发送」沉淀为一条可参数化的流水线。核心计算已脚本化，模型负责编排、确认参数、检查输出。

## 前置条件（不满足先检查，缺一项就停下说明）

1. **领星 MCP**：`~/.zcode/cli/config.json` 中存在 `mcp.servers["LingXing-MCP"]`（url + X-Mcp-Key）。脚本会自动从该文件读取密钥。
2. **西柚 MCP**（可选，仅做归因时需要）：`mcp.servers["xydc-mcp"]` 的 Authorization Bearer。
3. **AgentMail CLI**（可选，仅发送时需要）：`agently-cli auth status` 显示已授权；未授权则按 agently-mail skill 的流程引导用户授权。
4. **curl / python3**：脚本依赖。

## 参数（用户每次可指定，未指定用默认值）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--to` 收件人 | 询问用户确认（首次运行时确认默认收件人） | 邮件收件人 |
| `--shop` 店铺 | GreatStar Tools（sid=1） | 领星店铺 |
| `--threshold` 跌幅阈值 | 0（列出全部下跌） | 只列跌幅 ≥ 该比例的 ASIN（如 0.1=10%） |
| `--deep` 西柚归因 | true（Top 10） | 对跌幅 Top N 调用西柚查价格/评分/流量两周对比 |
| `--send` 发送邮件 | true | 是否通过 AgentMail 发送 |
| `--weeks` 对比周期 | 上周 vs 上上周 | 近 7 天 vs 14 天中前 7 天 |

## 工作流

### Step 1 前置检查（30 秒）
- 确认三个依赖可用（见上），MCP 工具不可用时说明"需重启 ZCode 会话注册 MCP 工具"，并改用脚本直连方式（脚本内置 curl 直连，无需 MCP 注册）。

### Step 2 拉取销量数据
```bash
bash ~/.agents/skills/weekly-sales-decline-alert/scripts/fetch_listing.sh <output_dir>
```
- 从 `~/.zcode/cli/config.json` 读取领星密钥，curl 直连分页拉取 `erp_listing`（默认 5 页 × 100 条，覆盖 Top 500 listing），输出到 `<output_dir>/listing_p{0..4}.json`。
- 拉取失败时检查网络/密钥，将错误原文反馈用户，不要静默重试。

### Step 3 计算环比并筛选下跌
```bash
python3 ~/.agents/skills/weekly-sales-decline-alert/scripts/analyze.py <output_dir> --threshold 0 --out <output_dir>/decline.json
```
- 口径：上周 = `average_seven_volume × 7`；上上周 = `fourteen_volume − 上周`；仅统计两周均有销量的 ASIN。
- 输出 `decline.json`：含 ASIN、品名、MSKU、售价、上上周/上周销量、周差、跌幅、负责人。

### Step 4 （可选）西柚归因 Top N
```bash
python3 ~/.agents/skills/weekly-sales-decline-alert/scripts/xiyou_deep.py <output_dir> --top 10
```
- 对跌幅 Top N 逐个调西柚 `get_asin_info_trends`（两周价格/评分/评论）与 `get_asin_traffic_trends_weekly`（自然/广告流量），输出 `deep.json`。
- 归因规则：涨价 $>0 且跌幅大 → 涨价型；自然流量跌 >20% → 自然流量下滑；广告流量跌 >40% → 广告收缩；降价仍跌 → 异常标记；否则 → 查转化/竞争。

### Step 5 生成 HTML 报告
```bash
python3 ~/.agents/skills/weekly-sales-decline-alert/scripts/analyze.py <output_dir> --html --out <output_dir>/report.html [--deep <output_dir>/deep.json]
```
- 报告含：KPI 概览、跌幅 Top10 归因表（如有 deep）、按负责人汇总表、完整下跌清单（按跌幅降序，红/橙/黄/灰分级）。

### Step 6 （可选）发送邮件
- 用 agently-mail skill 的 `agently-cli message +send` 发送（附件为 report.html，正文摘要关键结论）。
- 两阶段确认：先不带 `--confirmation-token` 调用拿到 ctk，展示摘要后**停下等用户确认**，下一轮再带 token 完成；用户明确授权过可 `--confirmed`。
- 正文只写用户要求传达的内容，不加 Agent 签名。

## 输出格式
- 对话内汇报：下跌 ASIN 数 / 跌幅分布 / 周损失合计 / Top10 归因摘要 / 负责人 Top5。
- 文件产物：`<output_dir>/report.html`（自包含单文件，可离线打开）、`decline.json`（结构化数据）。

## 隐私红线（重要）
- **禁止**将任何密钥、token、真实邮箱、员工姓名、内部销售数据写入仓库或文档。
- 脚本从本地 config.json 读取凭证，**永不硬编码**；skill 仓库本身不含任何敏感信息。
- 收件人邮箱只在对话中出现，写进 HTML/邮件正文时不落盘到仓库。
- 若用户要求把 skill 推送到公开仓库，推送前必须扫描（grep 密钥模式/邮箱/姓名）。

## 排错速查
- 领星接口返回 `未知错误`：去掉 `sort_field`/`sort_type` 参数重试（该接口对排序参数敏感）。
- 西柚响应可能是 SSE（`event: message` 前缀）或纯 JSON，解析脚本已兼容两者。
- 附件路径必须相对于当前目录（AgentMail 要求）；发送时 `cd` 到报告所在目录。
- 上下文控制：数据量大时优先用脚本落盘处理，不要把整页 JSON 贴进对话。
