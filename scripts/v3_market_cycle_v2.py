"""
v3.0 市场周期识别模型 + 动态权重切换（修复版）
"""
import pandas as pd
import numpy as np
import os, sys
from skill_paths import get_knowledge_dir, SKILL_CONFIG

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_PATH = os.path.join(get_knowledge_dir(), 'backtest_data_50stocks.csv')
OUT_DIR   = get_knowledge_dir()

# 加载数据
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df['date'] = pd.to_datetime(df['date'])
df['code'] = df['code'].astype(str)  # 统一转字符串
df = df.sort_values(['code', 'date']).reset_index(drop=True)

print(f'加载完成: {len(df)}条, {df["code"].nunique()}只股票')

# 用510300（沪深300ETF）作为大盘代理
hs300 = df[df['code'] == '510300'][['date', 'close']].copy()
hs300 = hs300.sort_values('date').reset_index(drop=True)
hs300['ma20'] = hs300['close'].rolling(20).mean()
hs300['ma20_slope'] = hs300['ma20'].diff()
hs300 = hs300.dropna()

print(f'沪深300ETF: {len(hs300)}条, {hs300["date"].min().strftime("%Y-%m-%d")}~{hs300["date"].max().strftime("%Y-%m-%d")}')

# 市场周期分类
def classify_market(row):
    above = row['close'] > row['ma20']
    rising = row['ma20_slope'] > 0
    falling = row['ma20_slope'] < 0
    if above and rising: return '牛市'
    elif not above and falling: return '熊市'
    else: return '震荡市'

hs300['state'] = hs300.apply(classify_market, axis=1)
state_counts = hs300['state'].value_counts()
print('\n市场状态分布:')
for s, cnt in state_counts.items():
    print(f'  {s}: {cnt}天 ({cnt/len(hs300)*100:.1f}%)')

# 动态权重配置表
WEIGHT_TABLE = {
    '牛市':    {'tech': 0.60, 'basic': 0.25, 'industry': 0.15},
    '熊市':    {'tech': 0.25, 'basic': 0.50, 'industry': 0.25},
    '震荡市':  {'tech': 0.40, 'basic': 0.35, 'industry': 0.25},
}

# 日期→状态映射
date_state = dict(zip(hs300['date'], hs300['state']))

# 因子计算（2019年后）
df = df[df['date'] >= '2019-01-01'].copy()
df = df.sort_values(['code', 'date']).reset_index(drop=True)

df['ret_20d'] = df.groupby('code')['close'].pct_change(20)
df['ret_5d']  = df.groupby('code')['close'].pct_change(5)
df['up_day']  = (df['close'] > df.groupby('code')['close'].shift(1)).astype(int)
df['streak']  = df.groupby('code')['up_day'].transform(lambda x: x.rolling(5, min_periods=1).sum())
df['ret_1y']  = df.groupby('code')['close'].pct_change(252)
df['ret_6m']  = df.groupby('code')['close'].pct_change(120)
df['price_rank'] = df.groupby('date')['close'].rank(pct=True)
df['industry'] = (1 - df['price_rank']) * 100
df = df.fillna(0)

# 截面标准化
unique_dates = sorted(df['date'].unique())
print(f'\n因子计算中({len(unique_dates)}个交易日)...')

for k, d in enumerate(unique_dates):
    if k % 500 == 0: print(f'  {k}/{len(unique_dates)}...')
    mask = df['date'] == d
    for col in ['ret_20d', 'ret_5d', 'streak', 'ret_1y', 'ret_6m']:
        v = df.loc[mask, col]
        m, s = v.mean(), v.std()
        if s > 0.001:
            df.loc[mask, f'{col}_z'] = (v - m) / s
        else:
            df.loc[mask, f'{col}_z'] = 0

df['tech']  = (df['ret_20d_z']*0.4 + df['ret_5d_z']*0.3 + df['streak_z']*0.3).clip(-3, 3)
df['tech']  = (df['tech'] + 3) / 6 * 100
df['basic'] = (df['ret_1y_z']*0.6 + df['ret_6m_z']*0.4).clip(-3, 3)
df['basic'] = (df['basic'] + 3) / 6 * 100
df['tech']  = df['tech'].clip(0, 100)
df['basic'] = df['basic'].clip(0, 100)

print('因子完成')

# ==================== 回测 ====================
REBALANCE_DAYS = 5
TOP_PCT = 0.20
trade_dates = unique_dates[::REBALANCE_DAYS]
print(f'调仓次数: {len(trade_dates)-1}')

def run_backtest(weight_func):
    correct, total = 0, 0
    rets = []
    for k in range(len(trade_dates) - 1):
        d0, d1 = trade_dates[k], trade_dates[k+1]
        w_t, w_b, w_i = weight_func(d0)
        day_df = df[df['date'] == d0].copy()
        if len(day_df) < 5: continue
        day_df['comp'] = day_df['tech']*w_t + day_df['basic']*w_b + day_df['industry']*w_i
        threshold = day_df['comp'].quantile(1 - TOP_PCT)
        selected = set(day_df[day_df['comp'] >= threshold]['code'].tolist())
        next_df = df[(df['date'] == d1) & (df['code'].isin(selected))]
        if len(next_df) == 0: continue
        avg_ret = next_df['pct_change'].mean()
        correct += 1 if avg_ret > 0 else 0
        total += 1
        if not np.isnan(avg_ret): rets.append(avg_ret)
    acc = correct / total if total > 0 else 0
    avg_r = np.mean(rets) if rets else 0
    return acc, correct, total, avg_r

# 测试
acc_fixed1, c1, t1, r1 = run_backtest(lambda d: (0.50, 0.30, 0.20))
acc_fixed2, c2, t2, r2 = run_backtest(lambda d: (0.40, 0.35, 0.25))
acc_dyn,    c3, t3, r3 = run_backtest(lambda d: WEIGHT_TABLE.get(date_state.get(d, '震荡市'), WEIGHT_TABLE['震荡市']).values())

print(f'\n固定(50/30/20): 准确率={acc_fixed1:.2%}({c1}/{t1}), 均收益={r1:.2f}%')
print(f'固定(40/35/25): 准确率={acc_fixed2:.2%}({c2}/{t2}), 均收益={r2:.2f}%')
print(f'动态权重:       准确率={acc_dyn:.2%}({c3}/{t3}), 均收益={r3:.2f}%')

# 分市场状态对比
print('\n=== 各市场状态准确率 ===')
print('| 市场状态 | 天数 | 动态权重 | 固定(50/30/20) | 差值 |')
print('|---------|------|---------|--------------|-----|')
for state in ['牛市', '熊市', '震荡市']:
    sub_dates = [d for d in trade_dates if date_state.get(d, '') == state]
    if len(sub_dates) < 5: continue
    
    c_d, t_d = 0, 0
    for d0 in sub_dates[:-1]:
        d1_idx = trade_dates.index(d0) + 1
        if d1_idx >= len(trade_dates): continue
        d1 = trade_dates[d1_idx]
        cfg = WEIGHT_TABLE[state]
        day_df = df[df['date'] == d0].copy()
        if len(day_df) < 5: continue
        day_df['comp'] = day_df['tech']*cfg['tech'] + day_df['basic']*cfg['basic'] + day_df['industry']*cfg['industry']
        threshold = day_df['comp'].quantile(1-TOP_PCT)
        selected = set(day_df[day_df['comp'] >= threshold]['code'].tolist())
        next_df = df[(df['date'] == d1) & (df['code'].isin(selected))]
        if len(next_df) == 0: continue
        c_d += 1 if next_df['pct_change'].mean() > 0 else 0
        t_d += 1
    
    c_f, t_f = 0, 0
    for d0 in sub_dates[:-1]:
        d1_idx = trade_dates.index(d0) + 1
        if d1_idx >= len(trade_dates): continue
        d1 = trade_dates[d1_idx]
        day_df = df[df['date'] == d0].copy()
        if len(day_df) < 5: continue
        day_df['comp'] = day_df['tech']*0.50 + day_df['basic']*0.30 + day_df['industry']*0.20
        threshold = day_df['comp'].quantile(1-TOP_PCT)
        selected = set(day_df[day_df['comp'] >= threshold]['code'].tolist())
        next_df = df[(df['date'] == d1) & (df['code'].isin(selected))]
        if len(next_df) == 0: continue
        c_f += 1 if next_df['pct_change'].mean() > 0 else 0
        t_f += 1
    
    acc_d = c_d/t_d if t_d > 0 else 0
    acc_f = c_f/t_f if t_f > 0 else 0
    state_days = sum(1 for d in trade_dates if date_state.get(d, '') == state)
    diff = acc_d - acc_f
    better = '✅' if diff > 0 else '⬜' if abs(diff) < 0.005 else '❌'
    print(f'| {state} | {state_days}天 | {acc_d:.2%} | {acc_f:.2%} | {diff:+.2%} {better} |')

print(f'\n动态权重 vs 固定(50/30/20): {acc_dyn-acc_fixed1:+.2%}')
print(f'动态权重 vs 固定(40/35/25): {acc_dyn-acc_fixed2:+.2%}')

out_text = f"""v3.0 市场周期识别模型 - 实测结果
================================
回测区间: 2019-01-01 ~ 2026-05-11
调仓频率: 每{REBALANCE_DAYS}个交易日

市场状态分布:
{state_counts.to_string()}

动态权重配置:
牛市: 技术60% / 基本面25% / 产业15%
熊市: 技术25% / 基本面50% / 产业25%
震荡市: 技术40% / 基本面35% / 产业25%

回测结果:
- 固定权重(50/30/20): 准确率={acc_fixed1:.2%}
- 固定权重(40/35/25): 准确率={acc_fixed2:.2%}
- 动态权重(市场自适应): 准确率={acc_dyn:.2%}

结论: {'动态权重有效，建议采用' if acc_dyn > max(acc_fixed1, acc_fixed2) else '动态权重效果不明显，维持固定权重'}
"""
with open(os.path.join(OUT_DIR, 'v3_market_cycle_results.txt'), 'w', encoding='utf-8') as f:
    f.write(out_text)
print(f'\n结果已保存')