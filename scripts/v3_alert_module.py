# -*- coding: utf-8 -*-
"""
v3.0 盘中实时预警模块
基于v3.0研究成果：动态权重 + 市场周期识别
监控内容：价格异动 / 市场周期变化 / 成交量异常 / 持仓警戒
盘中每30分钟检查一次（9:30-14:50）
"""
import requests, re, sys, os, json, time
from datetime import datetime, time as dtime
from pathlib import Path
from skill_paths import get_alert_dir, SKILL_CONFIG

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 预警阈值配置 ──────────────────────────────────────────
PRICE_ALERT_RISE_PCT  = 3.0   # 上涨超过3%预警
PRICE_ALERT_FALL_PCT  = 2.0   # 下跌超过2%预警
VOLUME_MULTIPLE       = 3.0   # 成交量超过5日均量3倍预警
HOLDING_FALL_PCT      = 5.0   # 持仓股票下跌5%预警

def _load_weights():
    """从config/weights.json加载权重配置，不存在则用内置默认值"""
    weights_path = os.path.join(SKILL_CONFIG['skill_root'], 'config', 'weights.json')
    if os.path.exists(weights_path):
        try:
            with open(weights_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {
                '牛市': {'tech': cfg['bull']['technical'], 'basic': cfg['bull']['fundamental'], 'industry': cfg['bull']['industry'], 'emoji': '🐂', 'label': '上涨趋势'},
                '熊市': {'tech': cfg['bear']['technical'], 'basic': cfg['bear']['fundamental'], 'industry': cfg['bear']['industry'], 'emoji': '🐻', 'label': '下跌趋势'},
                '震荡市': {'tech': cfg['mixed']['technical'], 'basic': cfg['mixed']['fundamental'], 'industry': cfg['mixed']['industry'], 'emoji': '⚖️', 'label': '震荡整理'},
            }
        except: pass
    return {
        '牛市': {'tech':0.60,'basic':0.25,'industry':0.15,'emoji':'🐂','label':'上涨趋势'},
        '熊市': {'tech':0.25,'basic':0.50,'industry':0.25,'emoji':'🐻','label':'下跌趋势'},
        '震荡市': {'tech':0.40,'basic':0.35,'industry':0.25,'emoji':'⚖️','label':'震荡整理'},
    }

# ── 市场周期检测（统一模块）──────────────────────────
def detect_market_state():
    """"使用统一的市场状态识别模块（兼容版，优先调用统一模块）"""
    try:
        # 尝试使用统一模块
        scripts_dir = os.path.join(SKILL_CONFIG['skill_root'], 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from market_state import detect_market_state as unified_detect, get_market_state_info
        state_en = unified_detect()  # 'bull'|'bear'|'mixed'
        state_map = {'bull': '牛市', 'bear': '熊市', 'mixed': '震荡市'}
        state = state_map.get(state_en, '震荡市')
        info = get_market_state_info()
        w_table = _load_weights()
        cfg = w_table.get(state, w_table['震荡市'])
        label = f"{info['emoji']}{info['label']}"
        return state, cfg, label
    except Exception as e:
        # 回退逻辑
        try:
            kr = requests.get(
                'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sh510300&scale=240&datalen=25&ma=no',
                headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            kdata = kr.json() if kr.status_code == 200 else []
            if not kdata or len(kdata) < 20:
                return '震荡市', _load_weights()['震荡市'], '⚖️震荡整理'
            closes = [float(d.get('close', 0)) for d in kdata]
            ma20 = sum(closes[-20:]) / 20
            cur = closes[-1]
            slope_positive = (sum(closes[-5:]) / 5) > (sum(closes[-20:-5]) / 15)
            above_ma = cur > ma20
            if above_ma and slope_positive: state = '牛市'
            elif not above_ma and not slope_positive: state = '熊市'
            else: state = '震荡市'
            w_table = _load_weights()
            cfg = w_table.get(state, w_table['震荡市'])
            return state, cfg, f"{cfg['emoji']}{cfg['label']}"
        except Exception:
            return '震荡市', _load_weights()['震荡市'], '⚖️震荡整理'

# ── 腾讯实时行情（免费，无需额度）───────────────────────────
TENCENT_HEADERS = {'Referer': 'https://finance.qq.com', 'User-Agent': 'Mozilla/5.0'}

def tencent_realtime(codes):
    """返回{code: {price, prev_close, volume, vol_avg5}}"""
    url = f'https://qt.gtimg.cn/q={",".join(codes)}'
    try:
        r = requests.get(url, headers=TENCENT_HEADERS, timeout=10)
        r.encoding = 'gbk'
        result = {}
        for line in r.text.split(';'):
            m = re.search(r'v_(\w+)="([^"]+)"', line)
            if not m: continue
            code = m.group(1)
            parts = m.group(2).split('~')
            if len(parts) < 45: continue
            try:
                price = float(parts[3])
                prev_close = float(parts[4])
                volume = float(parts[6])
                vol5_avg = float(parts[44]) if len(parts) > 44 and parts[44] else volume
                result[code] = {
                    'price': price,
                    'prev_close': prev_close,
                    'pct': (price - prev_close) / prev_close * 100,
                    'volume': volume,
                    'vol5_avg': vol5_avg if vol5_avg > 0 else volume,
                    'name': parts[1],
                }
            except: continue
        return result
    except: return {}

def tencent_kline(code, count=5):
    """获取最近N日K线数据（用于计算5日均量）"""
    url = f'https://web.ifzq.gtimg.cn/appstock/app/kline/kline?_var=kline_dayqfq&param={code},day,,,{count},qfq&r=0.1'
    try:
        r = requests.get(url, timeout=10)
        text = r.text
        s = text.find('=')
        if s < 0: return []
        j = json.loads(text[s+1:])
        return j.get('data', {}).get('day', [])
    except: return []

# ── 监控股票池（可配置）───────────────────────────────────
# 格式：(代码, 名称, 市场, 是否持仓)
WATCH_STOCKS = [
    ('sz002384', '东山精密', '持仓'),
    ('sh600105', '永鼎股份', '持仓'),
    ('sh600576', '汇金银行', '持仓'),
    ('sz300124', '汇川技术', '持仓'),
    ('sh688017', '绿的谐波', '持仓'),
    ('sz002281', '光迅科技', '关注'),
    ('sz300308', '中际旭创', '关注'),
    ('sz002156', '通富微电', '关注'),
    ('sh600584', '长电科技', '关注'),
    ('sh600522', '中天科技', '关注'),
    ('sz002025', '航天电器', '关注'),
    ('sz000001', '平安银行', '关注'),
]

# 核心关注（快速扫描）
CORE_WATCH = [s for s in WATCH_STOCKS if s[2] == '持仓']
ALL_WATCH  = WATCH_STOCKS

def check_price_alerts(stock_data, kline_data):
    """价格异动预警"""
    alerts = []
    for code, name, tag in ALL_WATCH:
        d = stock_data.get(code)
        if not d: continue
        pct = d['pct']
        price = d['price']
        
        # 持仓股票下跌预警
        if tag == '持仓' and pct <= -HOLDING_FALL_PCT:
            alerts.append(f"🔴【持仓警戒】{name}({tag}) 现价{price:.2f}，跌幅{pct:.1f}%，建议关注是否触发止损")
        elif pct >= PRICE_ALERT_RISE_PCT:
            alerts.append(f"🟢【价格异动·上涨】{name} 现价{price:.2f}，涨幅{pct:.1f}%，放量突破关注")
        elif pct <= -PRICE_ALERT_FALL_PCT:
            alerts.append(f"🔴【价格异动·下跌】{name} 现价{price:.2f}，跌幅{pct:.1f}%，注意风险")
    return alerts

def check_volume_alerts(stock_data):
    """成交量异常预警"""
    alerts = []
    for code, name, tag in ALL_WATCH:
        d = stock_data.get(code)
        if not d: continue
        vol = d['volume']
        vol_avg = d.get('vol5_avg', 0)
        if vol_avg > 0 and vol / vol_avg >= VOLUME_MULTIPLE:
            pct = d['pct']
            direction = '▲放量上涨' if pct > 0 else '▼放量下跌'
            alerts.append(f"🔵【量能异动】{name} 成交量达5日均量的{vol/vol_avg:.1f}倍，{direction}")
    return alerts

def check_limit_up(code, stock_data):
    """涨停预警（股价>9.8%且在交易时间内）"""
    alerts = []
    for c, name, tag in ALL_WATCH:
        d = stock_data.get(c)
        if not d: continue
        if d['pct'] >= 9.8:
            alerts.append(f"🚀【涨停预警】{name} 涨幅{d['pct']:.1f}%，接近涨停板！")
    return alerts

def check_market_state_change(last_state):
    """市场周期变化预警"""
    current_state, cfg, label = detect_market_state()
    alerts = []
    if last_state and current_state != last_state:
        if current_state == '熊市':
            alerts.append(f"🐻【市场状态切换】进入熊市权重：技术25% / 基本面50% / 产业25%，注意防御")
        elif current_state == '牛市':
            alerts.append(f"🐂【市场状态切换】进入牛市权重：技术60% / 基本面25% / 产业15%，顺势而为")
        else:
            alerts.append(f"⚖️【市场状态切换】进入震荡市权重：技术40% / 基本面35% / 产业25%")
    return alerts, current_state

# ── 盘中预警主函数 ──────────────────────────────────────────
def run_intraday_alerts():
    now = datetime.now()
    
    # 只在交易时间运行（9:30-14:50，周一至周五）
    current_time = now.time()
    market_start = dtime(9, 30)
    market_end   = dtime(14, 50)
    is_trading = (
        now.weekday() < 5
        and market_start <= current_time <= market_end
    )
    
    time_str = now.strftime('%H:%M')
    
    # 读取上次市场状态
    state_file = os.path.join(SKILL_CONFIG['skill_root'], 'last_market_state.json')
    last_state = None
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                last_state = json.load(f).get('state')
        except: pass
    
    # 检测市场状态变化
    state_alerts, current_state = check_market_state_change(last_state)
    
    # 保存当前状态
    with open(state_file, 'w') as f:
        json.dump({'state': current_state, 'time': now.isoformat()}, f)
    
    # 获取实时行情
    all_codes = [s[0] for s in ALL_WATCH]
    stock_data = tencent_realtime(all_codes)
    
    if not stock_data:
        return f"[{time_str}] 行情数据获取失败"
    
    # 执行各项检查
    all_alerts = []
    
    # 1. 价格异动
    price_alerts = check_price_alerts(stock_data, {})
    all_alerts.extend(price_alerts)
    
    # 2. 涨停预警
    limit_alerts = check_limit_up(None, stock_data)
    all_alerts.extend(limit_alerts)
    
    # 3. 成交量异常（简化版，不调用额外K线）
    vol_alerts = []
    for code, name, tag in ALL_WATCH:
        d = stock_data.get(code)
        if not d: continue
        # 成交量用腾讯实时数据的量指标
        if d['volume'] > 50000000 and abs(d['pct']) > 2:  # 5000万股+2%波动
            vol_alerts.append(f"🔵【量价配合】{name} 量增价{d['pct']:+.1f}%，成交{d['volume']/10000:.0f}万股")
    all_alerts.extend(vol_alerts[:3])  # 最多3条
    
    # 4. 市场状态变化
    all_alerts.extend(state_alerts)
    
    # 汇总报告
    report_lines = [f"📡 [{time_str}] 盘中预警报告"]
    report_lines.append(f"   当前状态：{detect_market_state()[2]}")
    report_lines.append(f"   监控股票：{len(ALL_WATCH)}只")
    
    if all_alerts:
        report_lines.append("")
        # 按优先级排序：持仓下跌 > 涨停 > 价格异动 > 量能 > 市场状态
        for alert in all_alerts:
            if '持仓警戒' in alert or '涨停' in alert:
                report_lines.insert(3, f"  ⚠️ {alert}")
            elif '市场状态' in alert:
                report_lines.insert(4 if len(report_lines) > 4 else 3, f"  {alert}")
            else:
                report_lines.append(f"  {alert}")
    else:
        report_lines.append("  ✅ 暂无明显预警信号")
    
    report = '\n'.join(report_lines)
    
    # 存档
    alert_dir = get_alert_dir()
    os.makedirs(alert_dir, exist_ok=True)
    today = now.strftime('%Y-%m-%d')
    log_path = os.path.join(alert_dir, f'{today}.txt')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[{time_str}]\n{report}\n")
    
    # 复盘存档（D:\汇金日报复盘）
    review_path = os.path.join(get_alert_dir(), f'{today}_盘中预警.txt')
    try:
        with open(review_path, 'a', encoding='utf-8') as f:
            f.write(f"\n[{time_str}]\n{report}\n")
    except: pass
    
    return report

def get_market_summary():
    """盘中行情速览（不发送，只返回）"""
    now = datetime.now()
    time_str = now.strftime('%H:%M')
    
    state, cfg, label = detect_market_state()
    
    # 沪深300指数速览
    hs300_data = tencent_realtime(['sh510300'])
    hs300_info = hs300_data.get('sh510300', {})
    
    # 持仓股票快速快照
    holding_data = {}
    for code, name, tag in CORE_WATCH:
        d = tencent_realtime([code]).get(code, {})
        if d:
            holding_data[name] = d
    
    lines = [f"📊 [{time_str}] 行情速览"]
    lines.append(f"   市场状态: {label}")
    if hs300_info:
        pct = hs300_info['pct']
        lines.append(f"   沪深300ETF: {hs300_info['price']:.2f}（{pct:+.2f}%）{'🟢' if pct>=0 else '🔴'}")
    
    if holding_data:
        lines.append("   持仓股票:")
        for name, d in holding_data.items():
            pct = d['pct']
            emoji = '🟢' if pct >= 0 else '🔴'
            lines.append(f"   {emoji} {name}: {d['price']:.2f}（{pct:+.2f}%）")
    
    return '\n'.join(lines)

# ── 手动触发（汇金问"现在行情"时调用）──────────────────────
def quick_report():
    return run_intraday_alerts()

# ── 测试运行 ──────────────────────────────────────────
if __name__ == '__main__':
    result = run_intraday_alerts()
    print(result)
    print("\n" + "="*40)
    print(get_market_summary())