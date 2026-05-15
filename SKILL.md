# AI智能选股评估系统 · SKILL.md
> Skill Name：AI智能选股评估系统（动态权重版）
> Version：v3.1（跨平台版）
> Author：汇金金融研究团队
> Created：2026-05-12
> Updated：2026-05-12
> Prerequisites：无（零基础可安装）
> Channel：通用（微信/飞书/命令行均支持）
> Platform：Windows / Linux / macOS 全平台支持

---

## 一、Skill定位与能力边界

### 1.1 是什么

AI智能选股评估系统是一套**以数据驱动为核心**的量化选股工具，基于三维评估模型（技术面×基本面×产业渗透率）和动态权重配置（市场周期自适应），为投资者提供每日赛道排名和强势股点评。

### 1.2 不是什么

- ❌ **不预测个股具体价格**（禁止任何形式的价格预测）
- ❌ **不提供具体买卖建议**（只提供客观评分参考）
- ❌ **不替代投资决策**（用户自行判断，投资风险自担）
- ❌ **不保证准确率100%**（任何系统均有错误风险）

### 1.3 核心能力

| 能力 | 实现状态 | 触发方式 |
|------|---------|---------|
| 每日16:00自动推送日报 | ✅ 已上线 | Cron自动运行 |
| 盘中实时预警 | ✅ 已上线 | Cron每30分钟自动运行 |
| 市场周期自动识别 | ✅ 已上线 | 每次日报/预警自动触发 |
| 动态权重赛道排名 | ✅ 已上线 | 集成在日报中 |
| 用户手动查询 | ✅ 已上线 | 用户发送"现在行情"/"盘中预警" |
| 历史日报复盘 | ✅ 已上线 | 用户访问 `diary/` 目录 |
| 权重敏感性回测 | ✅ 已上线 | 运行 `v3_market_cycle_v2.py` |

---

## 二、快速开始（5分钟上手）

### 2.1 安装（零基础）

```bash
# 解压ZIP包到任意目录
unzip stock-analysis_v3.1.zip
cd stock-analysis

# 安装Python依赖（如有需要）
pip install requests pandas numpy pillow

# 验证安装
python scripts/skill_paths.py          # 路径配置验证
python scripts/market_report_v8.py     # 生成日报测试
python scripts/v3_alert_module.py      # 预警模块测试
```

### 2.2 日常使用

| 操作 | 操作方式 | 响应 |
|------|---------|------|
| 接收每日日报 | 等待16:00 Cron推送 | 微信收到完整日报 |
| 查询盘中状态 | 对小虾说："现在行情" | 实时快照（持仓+大盘） |
| 查询盘中预警 | 对小虾说："盘中预警" | 预警报告（如有） |
| 复盘历史 | 打开 `diary/` 目录 | 查看每日日报md文件 |
| 回测研究 | 运行 `v3_market_cycle_v2.py` | 权重敏感性分析输出 |

---

## 三、文件结构（v3.1跨平台版）

```
stock-analysis/
├── SKILL.md                          ← 【主入口】本文件
├── README.md                         ← 安装与使用说明
├── REQUIREMENTS.txt                   ← Python依赖列表
├── TEMPLATE.md                       ← PRD文档模板
├── VERSION.md                         ← 版本更新日志
├── scripts/
│   ├── skill_paths.py               ← 【核心】跨平台路径适配器
│   ├── market_report_v8.py           ← 日报生成主脚本
│   ├── v3_alert_module.py           ← 盘中预警模块
│   ├── v3_market_cycle_v2.py        ← 动态权重回测引擎
│   └── v2_collect_tdx.py            ← 通达信数据采集（可选）
├── docs/
│   └── PRD_AI智能选股评估系统_v3.0_正式版.md  ← 完整PRD文档
├── data/
│   └── knowledge_backtest/          ← 回测数据（CSV格式）
│       ├── backtest_data_50stocks.csv
│       └── backtest_data_mainboard.csv
└── diary/                          ← 日报自动存档目录
```

---

## 四、核心脚本说明

### 4.1 skill_paths.py（路径适配器）

自动检测当前OS，智能配置路径，无需手动修改：

```python
from skill_paths import SKILL_CONFIG
print(SKILL_CONFIG['skill_root'])    # skill包根目录
print(SKILL_CONFIG['diary_dir'])      # 日报存档目录
print(SKILL_CONFIG['is_windows'])     # True/False
print(SKILL_CONFIG['is_linux'])       # True/False
```

| 配置项 | 说明 |
|--------|------|
| `skill_root` | skill包根目录 |
| `scripts_dir` | 脚本目录 |
| `data_dir` | 数据目录（自动选择） |
| `diary_dir` | 日报存档 |
| `alert_dir` | 预警日志存档 |
| `knowledge_dir` | 回测数据目录 |
| `is_windows` | Windows系统标志 |
| `is_linux` | Linux/macOS系统标志 |

### 4.2 market_report_v8.py（日报）

```bash
python scripts/market_report_v8.py
# 输出：完整日报（赛道排名+动态权重标注）
# 存档：自动保存到 diary/YYYY-MM-DD.md
```

### 4.3 v3_alert_module.py（盘中预警）

```bash
python scripts/v3_alert_module.py
# 输出：有预警→报告 / 无预警→静默
```

### 4.4 v3_market_cycle_v2.py（回测引擎）

```bash
python scripts/v3_market_cycle_v2.py
# 输出：9种权重组合准确率对比 + 分市场状态分析
```

---

## 五、动态权重配置（v3.0核心成果）

### 5.1 三档权重配置

| 市场状态 | 技术面 | 基本面 | 产业渗透率 | 触发条件 |
|---------|-------|-------|-----------|---------|
| 🐂 牛市 | 60% | 25% | 15% | 价格>MA20 且 均线向上 |
| 🐻 熊市 | 25% | 50% | 25% | 价格<MA20 且 均线向下 |
| ⚖️ 震荡市 | 40% | 35% | 25% | 其他情况 |

### 5.2 回测结果（2019-2026，355次调仓）

| 方法 | 准确率 | vs 固定(50/30/20) |
|------|--------|-------------------|
| 固定(50/30/20) | 50.14% | — |
| **动态权重(市场自适应)** | **51.83%** | **+1.69%** |

**分市场状态：**
- 牛市：动态权重53.15% vs 固定51.75%（+1.40%）
- **熊市：动态权重53.33% vs 固定48.89%（+4.44%）** ✅ 熊市防御显著
- 震荡市：动态权重46.67% vs 固定48.00%（-1.33%）

---

## 六、监控股票池

### 6.1 持仓股票

| 代码 | 名称 | 赛道 |
|------|------|------|
| sz002384 | 东山精密 | 光通信/EML |
| sh600105 | 永鼎股份 | CW光源 |
| sh600576 | 汇金银行 | 银行 |
| sz300124 | 汇川技术 | 机器人伺服 |
| sh688017 | 绿的谐波 | 谐波减速器 |

### 6.2 关注股票

光迅科技/中际旭创/通富微电/长电科技/中天科技/航天电器/平安银行

---

## 七、数据源

| 数据源 | 优先级 | 说明 |
|--------|-------|------|
| 新浪财经 | 1st | 日报主力数据源 |
| 腾讯行情 | 2nd | 预警备用 |
| QVeris API | 3rd | 需API Key（额度受限） |
| 通达信本地 | 4th | 仅Windows回测 |

---

## 八、故障排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| QVeris额度耗尽 | API额度不足 | 自动降级到新浪单一数据源 |
| 数据获取失败 | 网络问题 | 使用腾讯单源降级，已实现 |
| 股票无数据 | 停牌或数据缺失 | 标注⚪，自动跳过 |
| Linux路径错误 | skill_paths未运行 | 先 `from skill_paths import *` |

---

## 九、更新日志

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v3.0 | 2026-05-12 | 动态权重正式方案，盘中预警模块上线 |
| **v3.1** | **2026-05-12** | **跨平台支持（Windows/Linux/macOS），脚本打包进skill包** |

---

> ⚠️ 免责声明：本skill所有输出仅供研究参考，不构成任何投资建议。用户据此操作，风险自担。
