# -*- coding: utf-8 -*-
"""
汇金金融市场每日报告 v8（动态权重版）
=========================================
基于v3.0研究成果：
  市场周期识别 → 动态权重配置 → 赛道排名优化

市场周期划分：
  牛市：沪深300 > 20日均线 AND 均线向上 → 技术60% / 基本面25% / 产业15%
  熊市：沪深300 < 20日均线 AND 均线向下 → 技术25% / 基本面50% / 产业25%
  震荡市：其他 → 技术40% / 基本面35% / 产业25%

每日16:00自动推送，存档至diary/
"""
import requests, re, sys, os, json, subprocess
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── QVeris API（环境变量加载，禁止硬编码）──────────────────
QVERIS_API_KEY = os.environ.get('QVERIS_API_KEY', '')
if not QVERIS_API_KEY:
    raise RuntimeError('环境变量 QVERIS_API_KEY 未设置，请联系skill维护者获取API密钥')
QVERIS_BASE = 'https://qveris.cn/api/v1'
QVERIS_HEADERS = {'Authorization': f'Bearer {QVERIS_API_KEY}', 'Content-Type': 'application/json'}

# ── 动态权重配置（v3.0研究成果） ──────────────────────────
WEIGHT_TABLE = {
    '牛市':    {'tech': 0.60, 'basic': 0.25, 'industry': 0.15, 'emoji': '🐂', 'label': '上涨趋势'},
    '熊市':    {'tech': 0.25, 'basic': 0.50, 'industry': 0.25, 'emoji': '🐻', 'label': '下跌趋势'},
    '震荡市':  {'tech': 0.40, 'basic': 0.35, 'industry': 0.25, 'emoji': '⚖️', 'label': '震荡整理'},
}

def _load_weights():
    """从config/weights.json加载权重配置，不存在则用内置WEIGHT_TABLE"""
    weights_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'weights.json')
    if os.path.exists(weights_path):
        try:
            with open(weights_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {
                '牛市':    {'tech': cfg['bull']['technical'], 'basic': cfg['bull']['fundamental'], 'industry': cfg['bull']['industry'], 'emoji': '🐂', 'label': '上涨趋势'},
                '熊市':    {'tech': cfg['bear']['technical'], 'basic': cfg['bear']['fundamental'], 'industry': cfg['bear']['industry'], 'emoji': '🐻', 'label': '下跌趋势'},
                '震荡市':  {'tech': cfg['mixed']['technical'], 'basic': cfg['mixed']['fundamental'], 'industry': cfg['mixed']['industry'], 'emoji': '⚖️', 'label': '震荡整理'},
            }
        except: pass
    return WEIGHT_TABLE

def detect_market_state():
    """用510300（沪深300ETF）判断市场周期（兼容版，优先调用统一模块）"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
        from market_state import detect_market_state as unified_detect
        state_en = unified_detect()
        state_map = {'bull': '牛市', 'bear': '熊市', 'mixed': '震荡市'}
        state = state_map.get(state_en, '震荡市')
        w_table = _load_weights()
        cfg = w_table.get(state, w_table['震荡市'])
        return state, cfg
    except Exception:
        pass
    
    # 回退逻辑：本地实现
    try:
        url = 'https://hq.sinajs.cn/list=sh510300'
        r = requests.get(url, headers={'Referer':'https://finance.sina.com.cn','User-Agent':'Mozilla/5.0'}, timeout=10)
        r.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', r.text)
        if not m: return '震荡市', _load_weights()['震荡市']
        parts = m.group(1).split(',')
        if len(parts) < 4: return '震荡市', _load_weights()['震荡市']
        current_price = float(parts[3])
        prev_close = float(parts[2])
        ma20 = None
        k_url = 'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sh510300&scale=240&datalen=25&ma=no'
        kr = requests.get(k_url, headers={'Referer':'https://finance.sina.com.cn','User-Agent':'Mozilla/5.0'}, timeout=10)
        kdata = kr.json() if kr.status_code == 200 else []
        if kdata and len(kdata) >= 20:
            ma20 = sum(float(d.get('close', 0)) for d in kdata[-20:]) / 20
        else:
            return '震荡市', _load_weights()['震荡市']
        cur = float(parts[3])
        recent_closes = [float(d.get('close',0)) for d in kdata[-5:]]
        older_closes = [float(d.get('close',0)) for d in kdata[-20:-5]]
        slope_positive = (sum(recent_closes)/5) > (sum(older_closes)/15) if older_closes else False
        above_ma = cur > ma20
        if above_ma and slope_positive:
            state = '牛市'
        elif not above_ma and not slope_positive:
            state = '熊市'
        else:
            state = '震荡市'
        w_table = _load_weights()
        cfg = w_table.get(state, w_table['震荡市'])
        return state, cfg
    except Exception as e:
        return '震荡市', _load_weights()['震荡市']

def _qv_execute(tool_id, params):
    r = requests.post(f'{QVERIS_BASE}/tools/execute?tool_id={tool_id}',
        headers=QVERIS_HEADERS, json={'parameters': params}, timeout=30)
    return r.json()

def _qv_find_rows(d, depth=0):
    if not isinstance(d, dict) or depth > 15: return []
    if 'rows' in d and isinstance(d['rows'], list): return d['rows']
    for v in d.values():
        r = _qv_find_rows(v, depth+1)
        if r is not None: return r
    return []

def qv_index(codes):
    qv_codes = []
    for c in codes:
        c = c.replace('s_sh', '').replace('s_sz', '').replace('sh', '').replace('sz', '')
        qv_codes.append(c)
    r = _qv_execute('hangseng_polysource.index.livequote.query.v2.2730eef8', {'indexObject': qv_codes})
    if not r.get('success'): return []
    result_obj = r.get('result', {})
    rows = result_obj.get('data', {}).get('data', {}).get('data', {}).get('rows', [])
    return [{'name': it.get('indexName', ''), 'code': it.get('indexCode', ''),
             'price': it.get('latestPrice'), 'pct': it.get('changePCT', 0),
             'up': it.get('upCount', 0), 'down': it.get('downCount', 0),
             'vol': it.get('turnoverValue', '')} for it in rows]

def qv_news(keyword, limit=5, emotion='多头'):
    today = datetime.now().strftime('%Y%m%d')
    r = _qv_execute('hangseng_polysource.pubsentiment.news.query.v2.2aff0be5', {
        'keyword': keyword, 'emotion': emotion, 'startdate': today, 'enddate': today, 'limit': limit
    })
    if not r.get('success'): return []
    full_url = r.get('result', {}).get('full_content_file_url', '')
    if full_url:
        try:
            fc = requests.get(full_url, timeout=30); fc.encoding = 'utf-8'
            rows = json.loads(fc.text).get('data', {}).get('data', {}).get('rows', [])
        except: rows = []
    else:
        rows = _qv_find_rows(r.get('result', {}))
    return [{'title': (it.get('title') or it.get('sourceTitle') or ''),
             'time': it.get('publishTime', ''),
             'source': it.get('mediaName', ''),
             'abstract': (it.get('contentAbstract') or '')[:150]} for it in rows]

# ── 数据源 ──────────────────────────────────────────
SINA_HEADERS = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}

INDICES = [
    ('上证指数', 's_sh000001', 's_sh000001'),
    ('深证成指', 's_sz399001', 's_sz399001'),
    ('创业板指', 's_sz399006', 's_sz399006'),
    ('科创50',   's_sh000688', 's_sh000688'),
]

SECTOR_LEADERS = {
    '半导体':     [('中芯国际', 'sh688041'), ('北方华创', 'sz002371'), ('韦尔股份', 'sh603501')],
    '军工':       [('航发动力', 'sz000738'), ('中航沈飞', 'sh600760'), ('紫光国微', 'sz002049')],
    '电力':       [('长江电力', 'sh600900'), ('中国核电', 'sh601985'), ('国电南瑞', 'sh600406')],
    '商业航天':   [('航天电器', 'sz002025'), ('中航光电', 'sz002413'), ('振华科技', 'sz000733')],
}

ETF_CODES = {'半导体':'sh512480','军工':'sh512660','电力':'sh512580','商业航天':'sh502024'}

SECTOR_STOCKS = {
    'AI算力/半导体': [
        ('海光信息', 'sh688041'), ('寒武纪', 'sh688256'), ('长电科技', 'sh600584'),
        ('通富微电', 'sz002156'), ('北方华创', 'sz002371'), ('澜起科技', 'sh688008'),
    ],
    '光通信/CPO': [
        ('中际旭创', 'sz300308'), ('新易盛', 'sz300502'), ('天孚通信', 'sz300570'),
        ('光迅科技', 'sz002281'), ('永鼎股份', 'sh600105'), ('东山精密', 'sz002384'),
        ('大族激光', 'sz002008'), ('剑桥科技', 'sh603083'),
    ],
    '商业航天': [
        ('中国卫星', 'sh600118'), ('航天电器', 'sz002025'), ('天银机电', 'sh300342'),
    ],
    '储能/锂电': [
        ('阳光电源', 'sz300274'), ('锦浪科技', 'sz300763'), ('德方纳米', 'sz300769'), ('天齐锂业', 'sz002466'),
    ],
    '算电协同/电力': [
        ('长江电力', 'sh600900'), ('国电南瑞', 'sh600406'), ('许继电气', 'sz000400'),
    ],
    '人形机器人': [
        ('绿的谐波', 'sh688017'), ('埃斯顿', 'sz002747'), ('汇川技术', 'sz300124'),
        ('双环传动', 'sz002472'), ('秦川机床', 'sz000837'),
    ],
    '创新药/医药': [
        ('药明康德', 'sh603259'), ('恒瑞医药', 'sh600276'), ('百济神州', 'sh688235'),
    ],
    '新能源/光伏': [
        ('隆基绿能', 'sh601012'), ('通威股份', 'sh600438'), ('TCL中环', 'sz002129'), ('福斯特', 'sh603806'),
    ],
    '消费电子/AI终端': [
        ('立讯精密', 'sz002475'), ('歌尔股份', 'sz002241'), ('蓝思科技', 'sz300433'),
        ('工业富联', 'sh601138'), ('传音控股', 'sh688036'),
    ],
    '银行': [
        ('招商银行', 'sh600036'), ('宁波银行', 'sz002142'), ('平安银行', 'sz000001'), ('兴业银行', 'sh601166'),
    ],
    '有色/稀土': [
        ('北方稀土', 'sh600111'), ('中国稀土', 'sz000831'), ('紫金矿业', 'sh601899'), ('洛阳钼业', 'sh603993'),
    ],
}

def get_skill_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_diary_dir():
    base = get_skill_root()
    diary = os.path.join(base, 'diary')
    os.makedirs(diary, exist_ok=True)
    return diary

def get_alert_dir():
    base = get_skill_root()
    alert = os.path.join(base, 'alert_logs')
    os.makedirs(alert, exist_ok=True)
    return alert

def tencent_fetch(codes):
    """腾讯行情（大盘指数专用，兼容s_前缀）"""
    results = {}
    for code in codes:
        tc = code[2:] if code.startswith('s_') else code
        url = f'https://qt.gtimg.cn/q={tc}'
        try:
            r = requests.get(url, timeout=10)
            for line in r.text.strip().split('\n'):
                parts = line.split('=')
                if len(parts) < 2: continue
                code_key = parts[0].replace('v_', '')
                code_key = code_key[2:] if code_key.startswith('s_') else code_key
                fields = parts[1].replace('"', '').split('~')
                if len(fields) > 32:
                    results[code_key] = fields
        except:
            pass
    return results

def sina_fetch(codes):
    """新浪行情（备用，大盘指数用）"""
    url = f'https://hq.sinajs.cn/list={",".join(codes)}'
    try:
        r = requests.get(url, headers=SINA_HEADERS, timeout=10)
        r.encoding = 'gbk'
        results = {}
        for m in re.finditer(r'hq_str_(\w+)="([^"]+)"', r.text):
            results[m.group(1)] = m.group(2).split(',')
        return results
    except:
        return {}

def get_kline(code, count=25):
    url = f'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={code}&scale=240&datalen={count}&ma=no'
    r = requests.get(url, headers=SINA_HEADERS, timeout=10)
    try: return r.json()
    except: return []

def get_index_with_confidence():
    """大盘指数：腾讯主链（新浪/QVeris额度留给个股）"""
    tencent_data = tencent_fetch([c[1] for c in INDICES])
    lines = []
    for name, sc, tc in INDICES:
        tc_key = sc[2:] if sc.startswith('s_') else sc
        t = tencent_data.get(tc_key, [])
        price_t = chg_pct_t = None
        if len(t) >= 33:
            try:
                price_t = float(t[3])
                chg_pct_t = float(t[32])
            except: pass
        if price_t:
            emoji = '🟢' if chg_pct_t >= 0 else '🔴'
            lines.append(f"  {emoji} {name}: {price_t:.2f}（{chg_pct_t:+.2f}%）")
        else:
            lines.append(f"  ⚪ {name}: 数据获取失败")
    return lines

def calc_stock_score(code, w_t, w_b, w_i):
    """动态权重版评分：技术×w_t + 基本面×w_b + 产业渗透率×w_i"""
    kdata = get_kline(code, 60)
    if not kdata or len(kdata) < 10: return None
    closes = [float(d.get('close', 0)) for d in kdata if d.get('close')]
    if len(closes) < 10: return None
    
    ret_5d  = (closes[-1] - closes[-6]) / closes[-6] * 100 if closes[-6] > 0 else 0
    ret_20d = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 and closes[-21] > 0 else (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 else 0
    up_count = sum(1 for i in range(1, min(11, len(closes))) if closes[-i] > closes[-i-1])
    streak = up_count / 10.0
    
    ret_1y = (closes[-1] - closes[-252]) / closes[-252] * 100 if len(closes) >= 252 and closes[-252] > 0 else (closes[-1] - closes[-120]) / closes[-120] * 100 if len(closes) >= 120 else (closes[-1] - closes[-60]) / closes[-60] * 100 if len(closes) >= 60 else 0
    ret_6m = (closes[-1] - closes[-120]) / closes[-120] * 100 if len(closes) >= 120 and closes[-120] > 0 else ret_20d
    
    tech_raw = ret_20d * 0.4 + ret_5d * 0.3 + streak * 20 * 0.3
    basic_raw = ret_1y * 0.6 + ret_6m * 0.4
    
    tech_score = max(0, min(100, (tech_raw / 10 + 5) * 10))
    basic_score = max(0, min(100, (basic_raw / 10 + 5) * 10))
    price_factor = max(0, min(100, 50 - (closes[-1] / 2)))
    composite = tech_score * w_t + basic_score * w_b + price_factor * w_i
    
    return {
        'score': composite, 'tech_score': tech_score, 'basic_score': basic_score,
        'industry_score': price_factor, 'ret_20d': ret_20d, 'ret_5d': ret_5d,
        'streak': streak, 'close': closes[-1]
    }

def get_sector_ranking(w_t, w_b, w_i):
    """动态权重版赛道排名"""
    sector_results = {}
    for sector, stocks in SECTOR_STOCKS.items():
        valid = [(n, c, calc_stock_score(c, w_t, w_b, w_i)) for n, c in stocks]
        valid = [(n, c, r) for n, c, r in valid if r]
        if valid:
            best = max(valid, key=lambda x: x[2]['score'])
            avg = sum(s[2]['score'] for s in valid) / len(valid)
            sector_results[sector] = {'best': best, 'avg_score': avg, 'stocks': valid}
    
    sorted_sectors = sorted(sector_results.items(), key=lambda x: x[1]['avg_score'], reverse=True)
    lines = []
    
    if not sorted_sectors: return lines
    
    top = sorted_sectors[0]
    bottom = sorted_sectors[-1]
    t20_top = top[1]['best'][2]['ret_20d']
    t20_bot = bottom[1]['best'][2]['ret_20d']
    
    if t20_top > 10:   top_c = f"{top[0]}强势，20日+{t20_top:.0f}%"
    elif t20_top > 3:  top_c = f"{top[0]}偏强，20日+{t20_top:.0f}%"
    else:              top_c = f"{top[0]}平稳，20日{t20_top:+.0f}%"
    if t20_bot < -5:   bot_c = f"{bottom[0]}偏弱，20日{t20_bot:.0f}%"
    elif t20_bot < 0:  bot_c = f"{bottom[0]}调整中"
    else:              bot_c = f"{bottom[0]}趋势走弱"
    
    lines.append(f"  【今日简评】{top_c}；{bot_c}。")
    lines.append("")
    lines.append(f"  【赛道景气度排名】（权重:技术{int(w_t*100)}%/基本面{int(w_b*100)}%/产业{int(w_i*100)}%）")
    lines.append("")
    
    for i, (sector, info) in enumerate(sorted_sectors):
        name, code, best_data = info['best']
        score = best_data['score']
        t20 = best_data['ret_20d']
        close = best_data['close']
        emoji = '🟢' if t20 >= 0 else '🔴'
        rank_bar = '▓' * max(0, min(10, int(score / 10))) + '░' * max(0, 10 - int(score / 10))
        lines.append(f"  {emoji} {i+1:>2}. {sector:<15} {rank_bar} 均分{score:.0f} {close:.1f}元 20日{t20:+.1f}%")
        for sn, sc, sd in sorted(info['stocks'], key=lambda x: x[2]['score'], reverse=True)[:2]:
            s_t20 = sd['ret_20d']
            se = '🟢' if s_t20 >= 0 else '🔴'
            lines.append(f"     {se} {sn:<8} 20日{s_t20:+.1f}%")
    return lines

def get_sector_with_leaders(all_stock_codes):
    stock_data = sina_fetch(all_stock_codes)
    report = []
    for sector, leaders in SECTOR_LEADERS.items():
        code = ETF_CODES.get(sector, '')
        etf_parts = stock_data.get(code, []) if code else []
        if len(etf_parts) >= 4:
            try:
                ep = float(etf_parts[1]); epct = float(etf_parts[3])
                emoji = '🟢' if epct >= 0 else '🔴'
                report.append(f"  {emoji} {sector}: {ep:.3f}（{epct:+.2f}%）")
            except:
                report.append(f"  ⚪ {sector}: 数据异常")
        else:
            report.append(f"  ⚪ {sector}: 暂无数据")
        for label, sc in leaders:
            parts = stock_data.get(sc, [])
            if len(parts) >= 4:
                try:
                    price = float(parts[1]); prev_close = float(parts[3])
                    pct = (price - prev_close) / prev_close * 100
                    emoji = '🟢' if pct >= 0 else '🔴'
                    report.append(f"    {emoji} {label}: {price:.2f}（{pct:+.2f}%）")
                except:
                    report.append(f"    ⚪ {label}: 数据异常")
            else:
                report.append(f"    ⚪ {label}: 暂无数据")
        report.append("")
    return report

def get_news_emotion(keyword, label, limit=3):
    rows = qv_news(keyword, limit=limit, emotion='多头')
    if not rows: return []
    lines = [f"  📰 {label}新闻情绪:"]
    for row in rows[:limit]:
        title = row['title'] or row['abstract'] or ''
        if title:
            lines.append(f"    · {title[:50]}")
    return lines

def generate_report():
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日 %H:%M')
    
    state, cfg = detect_market_state()
    w_t = cfg.get('tech', 0.40)
    w_b = cfg.get('basic', 0.35)
    w_i = cfg.get('industry', 0.25)
    state_emoji = cfg.get('emoji', '⚖️')
    state_label = cfg.get('label', '震荡整理')
    
    idx_lines = get_index_with_confidence()
    ranking_lines = get_sector_ranking(w_t, w_b, w_i)
    all_leader_codes = list(sum([[sc for _, sc in v] for v in SECTOR_LEADERS.values()], []))
    leader_lines = get_sector_with_leaders(all_leader_codes)
    
    news_lines = []
    for kw, lbl in [('AI算力', 'AI'), ('光模块', '光模块'), ('机器人', '机器人'), ('商业航天', '商业航天')]:
        news_lines.extend(get_news_emotion(kw, lbl))
        news_lines.append("")
    
    report = f"""
═══════════════════════════════════════
📊 汇金金融市场每日报告 v8（动态权重版）
{date_str} · {state_emoji}当前市场状态：{state_label}
═══════════════════════════════════════

⚠️ 本报告仅供参考，不构成投资建议。

【大盘指数】（双源验证）
{chr(10).join(idx_lines)}

【市场周期权重配置】（v3.0研究成果）
{state_emoji} {state_label} → 技术{int(w_t*100)}% / 基本面{int(w_b*100)}% / 产业{int(w_i*100)}%
  · 牛市：顺势而为，提高技术面权重
  · 熊市：防御为主，提高基本面权重

{chr(10).join(ranking_lines)}

【重点板块领头羊】
{chr(10).join(leader_lines)}
{chr(10).join(news_lines)}
═══════════════════════════════════════
数据来源：腾讯行情（个股：QVeris）
动态权重版本 v8（基于v3.0研究成果）
"""
    return report, state, cfg, date_str

def send_notification(report, date_str):
    """通过OpenClaw工具发送通知（微信优先，降级飞书）"""
    wechat_target = os.environ.get('WEIXIN_TARGET_USER', '')
    feishu_target = os.environ.get('FEISHU_TARGET_USER', '')
    
    if not wechat_target:
        print('[警告] 环境变量 WEIXIN_TARGET_USER 未设置，跳过微信推送')
        return False
    
    try:
        from agent_funcs import message
        msg_result = message(action='send', channel='openclaw-weixin',
            message=report, target=wechat_target)
        msg_id = msg_result.get('result', {}).get('messageId', '发送成功')
        print(f'\n[微信推送成功] messageId: {msg_id}')
        return True
    except Exception as e:
        print(f'\n[微信推送失败，尝试降级飞书] {e}')
        if feishu_target:
            try:
                from agent_funcs import message
                short_msg = f"【汇金日报 {date_str}】\n完整版已生成，查看 diary/ 目录。微信推送失败：{e}"
                message(action='send', channel='feishu', target=feishu_target, message=short_msg)
                print(f'[飞书降级推送成功]')
                return True
            except Exception as feishu_err:
                print(f'[飞书降级也失败] {feishu_err}')
        # 记录告警日志
        skill_root = get_skill_root()
        log_dir = os.path.join(skill_root, 'alert_logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f'{datetime.now().strftime("%Y-%m-%d")}.md')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n[日报推送失败] {datetime.now().strftime('%H:%M')} - 微信错误: {e}\n")
        print(f'[告警日志已记录: {log_path}]')
        return False

if __name__ == '__main__':
    report, state, cfg, date_str = generate_report()
    print(report)
    
    # ── 幂等存档（防重复写入）─────────────────────────────
    today = datetime.now().strftime('%Y-%m-%d')
    diary_dir = get_diary_dir()
    os.makedirs(diary_dir, exist_ok=True)
    diary_path = os.path.join(diary_dir, f'{today}.md')
    marker = f'# DATE: {today}'
    
    if os.path.exists(diary_path):
        with open(diary_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        if marker in existing:
            print(f'\n[日报已存在，跳过存档: {diary_path}]')
        else:
            with open(diary_path, 'w', encoding='utf-8') as f:
                f.write(f"{marker}\n# {today} 日报\n\n{report}")
            print(f'\n[日报存档(替换旧格式): {diary_path}]')
    else:
        with open(diary_path, 'w', encoding='utf-8') as f:
            f.write(f"{marker}\n# {today} 日报\n\n{report}")
        print(f'\n[日报存档: {diary_path}]')
    
    # ── 发送通知 ─────────────────────────────────────────
    send_notification(report, today)