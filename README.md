# A股多源验证选股决策系统

> 🤖 开箱即用的AI智能选股工具，基于动态权重三维评分模型（技术面 × 基本面 × 产业渗透率），支持每日16:00自动推送日报 + 盘中实时预警。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🐂🐻⚖️ 市场自适应 | 自动识别牛/熊/震荡市，动态调整权重配比 |
| 📊 三源数据验证 | 新浪 + 腾讯 + QVeris API 三重保障 |
| 📰 新闻情绪分析 | QVeris实时抓取多头新闻情绪 |
| ⏰ 全自动运行 | Cron定时推送，无需手动操作 |
| 🔔 盘中实时预警 | 每30分钟扫描持仓异动 |
| 📈 权重回测验证 | 2019-2026历史数据验证，熊市防御率+4.44% |

---

## 📁 目录结构

```
Stratapro/
├── SKILL.md              ← 主入口（AI Agent阅读）
├── README.md             ← 本文件
├── docs/
│   ├── PRD_AI智能选股评估系统_v3.1_审计加固版.md   ← 完整产品文档
│   ├── PRIVACY_SECURITY.md   ← 安全隐私说明（必读）
│   └── CHANNEL_CONFIG.md     ← 推送通道配置
├── scripts/
│   ├── market_report_v8.py      ← 日报生成（每日16:00运行）
│   ├── v3_alert_module.py         ← 盘中预警（每30分钟运行）
│   ├── v3_market_cycle_v2.py      ← 权重回测引擎
│   ├── market_state.py            ← 统一市场状态识别
│   ├── skill_paths.py             ← 跨平台路径适配器
│   ├── analyze_stock.py           ← 单股分析工具
│   └── cron_register.py          ← Cron任务注册
├── config/
│   └── weights.json          ← 动态权重配置（可选）
├── data/
│   └── knowledge_backtest/   ← 回测数据（CSV格式）
├── .env.example              ← 环境变量模板
└── .gitignore                ← 隐私文件过滤
```

---

## 🚀 快速开始（5分钟上手）

### 第一步：安装依赖

```bash
# 克隆仓库
git clone https://github.com/503496348-ops/Stratapro.git
cd Stratapro

# 安装Python依赖
pip install requests pandas numpy pillow

# 验证安装
python3 scripts/market_state.py
# 预期输出：市场状态: ⚖️震荡市(mixed)
```

### 第二步：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入真实值（参考下方说明）
nano .env
```

`.env` 文件需要配置以下三个环境变量：

| 环境变量 | 说明 | 获取方式 |
|---------|------|---------|
| `QVERIS_API_KEY` | QVeris API密钥（必须） | 联系 QVeris 服务商申请 |
| `WEIXIN_TARGET_USER` | 微信用户ID（必须） | OpenClaw 微信插件中查看 |
| `FEISHU_TARGET_USER` | 飞书用户ID（可选，降级用） | 飞书「我的ID」应用 |

### 第三步：运行日报

```bash
# 设置环境变量
export QVERIS_API_KEY=你的QVeris密钥
export WEIXIN_TARGET_USER=你的微信用户ID
export FEISHU_TARGET_USER=你的飞书用户ID

# 生成今日日报
python3 scripts/market_report_v8.py
```

成功后会看到：
- 完整日报输出（大盘指数 + 赛道排名 + 领头羊 + 新闻情绪）
- 自动存档到 `diary/YYYY-MM-DD.md`

---

## 📊 功能说明

### 1. 日报模块（market_report_v8.py）

**运行方式**：
```bash
python3 scripts/market_report_v8.py
```

**输出内容**：
- 大盘指数（上证/深证/创业板/科创50）
- 市场状态判定（🐂牛市/🐻熊市/⚖️震荡）
- 动态权重配置
- 11大赛道景气度排名
- 重点板块领头羊
- 新闻情绪快讯

**定时自动运行**（可选）：
```bash
# 添加到 crontab
crontab -e

# 每日16:00自动生成日报（周一至周五）
0 16 * * 1-5 cd /path/to/Stratapro && python3 scripts/market_report_v8.py
```

### 2. 盘中预警模块（v3_alert_module.py）

**运行方式**：
```bash
python3 scripts/v3_alert_module.py
```

**预警类型**：

| 预警类型 | 触发条件 | 优先级 |
|---------|---------|--------|
| 🚀 涨停预警 | 涨幅 ≥ 9.8% | P0 |
| 🔴 持仓警戒 | 持仓股下跌 ≥ 5% | P0 |
| 🟢 价格异动·上涨 | 涨幅 ≥ 3% | P1 |
| 🔴 价格异动·下跌 | 跌幅 ≥ 2% | P1 |
| 🔵 量能异动 | 成交量 ≥ 5日均量3倍 | P2 |
| 🐂🐻 市场状态切换 | 周期变化时 | P0 |

**定时自动运行**（可选）：
```bash
# 添加到 crontab
crontab -e

# 交易时段每30分钟预警（周一至周五9:30-14:50）
30,0 9-14 * * 1-5 cd /path/to/Stratapro && python3 scripts/v3_alert_module.py
```

### 3. 单股分析工具（analyze_stock.py）

**运行方式**：
```bash
python3 scripts/analyze_stock.py sz002384
# 或
python3 scripts/analyze_stock.py sh600105
```

**输出内容**：
- 实时行情（现价/涨跌幅）
- 技术面分析（5日/20日/60日涨跌）
- 三维评分（技术面/基本面/产业渗透率）
- 市场状态判定
- 综合结论

---

## ⚙️ 动态权重配置

系统根据市场状态自动调整三维评分权重：

| 市场状态 | 判断条件 | 技术面 | 基本面 | 产业渗透率 |
|---------|---------|--------|--------|-----------|
| 🐂 牛市 | 价格>MA20 且 均线向上 | 60% | 25% | 15% |
| 🐻 熊市 | 价格<MA20 且 均线向下 | 25% | 50% | 25% |
| ⚖️ 震荡市 | 其他情况 | 40% | 35% | 25% |

**自定义权重**（可选）：
编辑 `config/weights.json`，覆盖默认权重配置。

---

## 🔒 安全与隐私

### 隐私保护措施

| 措施 | 说明 |
|------|------|
| ✅ 环境变量加载 | API Key和用户ID通过环境变量读取，禁止硬编码 |
| ✅ .gitignore 过滤 | `.env`/diary/alert_logs 等敏感文件不会被提交 |
| ✅ 降噪发布 | 仓库版本不包含任何真实密钥或用户ID |

### 禁止事项

- ❌ 禁止将真实 API Key 硬编码到代码中
- ❌ 禁止将真实用户ID 硬编码到代码中
- ❌ 禁止将 `.env` 文件提交到版本控制

---

## ❓ 常见问题

**Q: 运行时提示「环境变量 QVERIS_API_KEY 未设置」？**
A: 确保已执行 `source .env` 或手动 `export QVERIS_API_KEY=你的密钥`

**Q: QVeris额度耗尽后日报还能生成吗？**
A: 可以，系统会自动降级到新浪单一数据源，报告中会标注「降级运行」

**Q: 非交易时间运行会怎样？**
A: 日报正常生成（无实时交易数据）；盘中预警会静默退出，不输出

**Q: 如何查看历史日报？**
A: 打开 `diary/` 目录，按日期查找对应 `.md` 文件

**Q: 怎么回测验证策略效果？**
A: 运行 `python3 scripts/v3_market_cycle_v2.py`，输出9种权重组合准确率对比

---

## 📝 免责声明

⚠️ 本系统所有输出仅供研究参考，不构成任何投资建议。用户据此操作，风险自担。股市有风险，投资需谨慎。

---

## 📄 许可证

MIT License — 可自由使用、修改和分发

---

## 🔗 相关链接

- [QVeris API 申请](https://qveris.cn) — 指数行情和新闻情绪数据源
- [OpenClaw 文档](https://docs.openclaw.ai) — AI Agent 运行框架

---

> 📌 **AI Agent 使用说明**：本仓库的 `SKILL.md` 是主入口文件，AI Agent 会自动读取并按照文件中的规范执行选股决策流程。人类用户请参考本 README 文件进行安装和配置。