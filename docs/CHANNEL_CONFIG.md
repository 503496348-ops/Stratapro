# 汇金选股Skill · 推送通道配置

> 更新时间：2026-05-16
> 更新人：小乖
> **v2.0变更**：推送配置已迁移至环境变量，禁止硬编码用户ID

## 当前稳定推送通道

| 通道 | 环境变量 | 状态 |
|------|---------|------|
| **微信** | `WEIXIN_TARGET_USER` | ✅ 已配置（从环境变量读取） |
| **飞书** | `FEISHU_TARGET_USER` | ✅ 已配置（从环境变量读取，降级用） |

## 环境变量配置方法

```bash
# 1. 复制配置模板
cp .env.example .env

# 2. 编辑 .env，填入真实值
nano .env

# 3. 设置环境变量
export QVERIS_API_KEY=sk-cn-YOUR_KEY_HERE
export WEIXIN_TARGET_USER=YOUR_WEIXIN_USER_ID
export FEISHU_TARGET_USER=YOUR_FEISHU_USER_ID

# 4. 运行skill
source .env && python3 scripts/market_report_v8.py
```

## 推送逻辑（v2.0）

```
market_report_v8.py 推送顺序：
1. 优先微信（channel='openclaw-weixin'），目标从 WEIXIN_TARGET_USER 读取
2. 微信失败 → 降级飞书（channel='feishu'），目标从 FEISHU_TARGET_USER 读取
3. 都失败 → 记录 alert_logs/
```

## 安全说明

- ❌ 禁止在代码中硬编码用户ID
- ❌ 禁止在文档中写入真实用户ID（仅写入环境变量名）
- ✅ 用户ID通过环境变量动态读取

## 配置变更记录

| 日期 | 变更内容 |
|------|---------|
| 2026-05-13 | 飞书已配置；微信待接入；C-1修复（降级链路完整） |
| 2026-05-16 | v2.0：推送配置迁移至环境变量，禁止硬编码用户ID |