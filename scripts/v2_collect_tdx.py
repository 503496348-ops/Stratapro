"""
v2.0 第1周：使用通达信本地日线数据（.day格式）收集50只股票历史数据
数据路径: D:\new_tdx\vipdoc\sz\lday 和 D:\new_tdx\vipdoc\sh\lday
格式：通达信.day，每条记录32字节
  0-3:   日期（4字节整数，YYYYMMDD）
  4-7:   开盘价（4字节整数，÷100）
  8-11:  最高价（4字节整数，÷100）
  12-15: 最低价（4字节整数，÷100）
  16-19: 收盘价（4字节整数，÷100）
  20-23: 成交额（4字节整数）
  24-27: 成交量（4字节整数）
  28-31: 保留（4字节）
"""
import struct
import pandas as pd
import os, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 通达信.day每条记录32字节
DAY_RECORD_SIZE = 32

# 代码映射：股票代码 -> 通达信文件名
STOCKS = [
    ('002281', '光迅科技', 'sz', 'sz002281'), ('300308', '中际旭创', 'sz', 'sz300308'),
    ('600498', '烽火通信', 'sh', 'sh600498'), ('002463', '东方电缆', 'sz', 'sz002463'),
    ('600584', '长电科技', 'sh', 'sh600584'), ('002156', '通富微电', 'sz', 'sz002156'),
    ('002185', '华天科技', 'sz', 'sz002185'), ('603005', '晶方科技', 'sh', 'sh603005'),
    ('688521', '芯原股份', 'sh', 'sh688521'),
    ('300124', '汇川技术', 'sz', 'sz300124'), ('002472', '双环传动', 'sz', 'sz002472'),
    ('688017', '绿的谐波', 'sh', 'sh688017'), ('000837', '秦川机床', 'sz', 'sz000837'),
    ('600862', '航天电器', 'sh', 'sh600862'), ('002544', '杰赛科技', 'sz', 'sz002544'),
    ('300008', '天银机电', 'sz', 'sz300008'), ('601698', '中国卫星', 'sh', 'sh601698'),
    ('688981', '中芯国际', 'sh', 'sh688981'), ('002371', '北方华创', 'sz', 'sz002371'),
    ('688396', '华润微', 'sh', 'sh688396'), ('688012', '中微公司', 'sh', 'sh688012'),
    ('002230', '科大讯飞', 'sz', 'sz002230'), ('600522', '中天科技', 'sh', 'sh600522'),
    ('002897', '意华股份', 'sz', 'sz002897'), ('300735', '光库科技', 'sz', 'sz300735'),
    ('301175', '中科海讯', 'sz', 'sz301175'),
    ('000977', '浪潮信息', 'sz', 'sz000977'), ('603019', '中科曙光', 'sh', 'sh603019'),
    ('688787', '海天瑞声', 'sh', 'sh688787'), ('300166', '东方国信', 'sz', 'sz300166'),
    ('002594', '比亚迪', 'sz', 'sz002594'), ('300750', '宁德时代', 'sz', 'sz300750'),
    ('688005', '容百科技', 'sh', 'sh688005'), ('002812', '恩捷股份', 'sz', 'sz002812'),
    ('000568', '泸州老窖', 'sz', 'sz000568'), ('600519', '贵州茅台', 'sh', 'sh600519'),
    ('002304', '洋河股份', 'sz', 'sz002304'),
    ('510300', '沪深300ETF', 'sh', 'sh510300'), ('159915', '创业板ETF', 'sz', 'sz159915'),
    ('588000', '科创50ETF', 'sh', 'sh588000'),
    ('600036', '招商银行', 'sh', 'sh600036'), ('601318', '中国平安', 'sh', 'sh601318'),
    ('000001', '平安银行', 'sz', 'sz000001'),
    ('300760', '迈瑞医疗', 'sz', 'sz300760'), ('688111', '金山办公', 'sh', 'sh688111'),
    ('300059', '东方财富', 'sz', 'sz300059'),
]

# 路径映射
TDX_BASE = r'D:\new_tdx\vipdoc'

def read_day_file(filepath):
    """读取通达信.day文件，返回数据列表"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    records = []
    n = len(raw) // DAY_RECORD_SIZE
    for i in range(n):
        off = i * DAY_RECORD_SIZE
        chunk = raw[off:off+DAY_RECORD_SIZE]
        # 解包：小端序
        date_int = struct.unpack('<I', chunk[0:4])[0]
        open_i   = struct.unpack('<I', chunk[4:8])[0]
        high_i   = struct.unpack('<I', chunk[8:12])[0]
        low_i    = struct.unpack('<I', chunk[12:16])[0]
        close_i  = struct.unpack('<I', chunk[16:20])[0]
        amount_i = struct.unpack('<I', chunk[20:24])[0]  # 成交额（万元）
        vol_i    = struct.unpack('<I', chunk[24:28])[0]  # 成交量（手）
        
        if date_int == 0 or date_int < 19900101:
            continue
        
        year = date_int // 10000
        month = (date_int % 10000) // 100
        day = date_int % 100
        try:
            from datetime import date
            d = date(year, month, day)
        except:
            continue
        
        # 价格：÷100
        open_p   = open_i / 100.0
        high_p   = high_i / 100.0
        low_p    = low_i / 100.0
        close_p  = close_i / 100.0
        
        records.append({
            'date': d,
            'open': open_p,
            'high': high_p,
            'low': low_p,
            'close': close_p,
            'volume': vol_i,        # 成交量（手）
            'amount': amount_i,      # 成交额（万元）
        })
    return records

# 先测试一只股票
print('=== 测试通达信数据 ===')
test_file = os.path.join(TDX_BASE, 'sz', 'lday', 'sz300124.day')
if os.path.exists(test_file):
    test_records = read_day_file(test_file)
    if test_records:
        print(f'✅ sz300124(汇川技术): {len(test_records)}条')
        print(f'   范围: {test_records[0]["date"]} ~ {test_records[-1]["date"]}')
        print(f'   最新: 收={test_records[-1]["close"]} 开={test_records[-1]["open"]}')
    else:
        print('❌ 无数据')
else:
    print(f'文件不存在: {test_file}')
    # 列出sz/lday目录下的3001xx文件
    sz_lday = os.path.join(TDX_BASE, 'sz', 'lday')
    matches = [f for f in os.listdir(sz_lday) if f.startswith('sz300')]
    print(f'sz/lday下sz300xxx文件: {matches[:10]}')

# 正式收集
print(f'\n=== 开始收集{len(STOCKS)}只股票 ===')
print('='*50)
all_data = []
failed = []

for i, (code, name, market, fname) in enumerate(STOCKS):
    daypath = os.path.join(TDX_BASE, market, 'lday', f'{fname}.day')
    print(f'[{i+1}/{len(STOCKS)}] {code} {name} ({market})...', end=' ', flush=True)
    
    if not os.path.exists(daypath):
        print('❌ 文件不存在')
        failed.append(f'{code}({name})')
        continue
    
    records = read_day_file(daypath)
    if not records or len(records) < 200:
        print(f'❌ 数据不足({len(records) if records else 0}条)')
        failed.append(f'{code}({name})')
        continue
    
    # 计算涨跌幅
    df = pd.DataFrame(records)
    df = df.sort_values('date').reset_index(drop=True)
    df['pct_change'] = df['close'].pct_change() * 100
    df['code'] = code
    df['name'] = name
    df['market'] = market
    
    all_data.append(df)
    print(f'✅ {len(df)}条 ({df["date"].iloc[0]} ~ {df["date"].iloc[-1]})')

print('='*50)

if all_data:
    result = pd.concat(all_data, ignore_index=True)
    cols = ['code', 'name', 'market', 'date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'pct_change']
    result = result[[c for c in cols if c in result.columns]]
    result = result.sort_values(['code', 'date']).reset_index(drop=True)
    
    out_dir = r'C:\Users\86173\.openclaw\workspace-baisheng\knowledge_backtest'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'backtest_data_50stocks.csv')
    result.to_csv(out_path, index=False, encoding='utf-8-sig')
    
    print(f'\n✅ 成功: {len(all_data)}/{len(STOCKS)}只股票，共{len(result)}条记录')
    print(f'📁 保存至: {out_path}')
    
    # 完整性报告
    stats = result.groupby('code').agg(count=('date', 'count'), start=('date', 'min'), end=('date', 'max')).reset_index()
    stats['name'] = stats['code'].map({c: n for c, n, _, _ in STOCKS})
    stats['status'] = stats['count'].apply(lambda x: '✅' if x >= 1200 else '🟡' if x >= 600 else '❌')
    print('\n数据完整性报告（3年≈1200个交易日）：')
    print(f'{"状态":<4} {"代码":<8} {"名称":<10} {"条数":<6} {"开始":<12} {"结束":<12}')
    print('-'*54)
    for _, row in stats.iterrows():
        print(f'{row["status"]:<4} {row["code"]:<8} {row["name"]:<10} {row["count"]:<6} {str(row["start"]):<12} {str(row["end"]):<12}')
    fail_count = len(stats[stats['count'] < 600])
    print(f'\n数据不完整（<600条）: {fail_count}只 / 完全失败: {len(failed)}只')
    if failed: print(f'失败股票: {failed}')
else:
    print('\n❌ 无数据')