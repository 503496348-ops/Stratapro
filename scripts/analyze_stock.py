# -*- coding: utf-8 -*-
import sys, requests, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def sina_price(code):
    url = 'https://hq.sinajs.cn/list={}'.format(code)
    try:
        r = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}, timeout=10)
        r.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', r.text)
        if m:
            p = m.group(1).split(',')
            price = float(p[3])
            prev = float(p[2])
            return p[0], price, prev, (price - prev) / prev * 100
    except:
        pass
    return None, None, None, None

def get_kline(code, count=60):
    url = 'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={}&scale=240&datalen={}&ma=no'.format(code, count)
    try:
        r = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}, timeout=10)
        return r.json()
    except:
        return []

def calc_up_count(closes, period):
    count = 0
    for i in range(1, period + 1):
        if i < len(closes):
            if closes[-i] > closes[-i - 1]:
                count += 1
    return count

def analyze(code):
    n, price, prev, pct = sina_price(code)
    if n is None:
        print('无法获取数据，请检查代码是否正确')
        return

    kdata = get_kline(code, 60)
    closes = [float(d.get('close', 0)) for d in kdata if d.get('close')]
    if len(closes) < 10:
        print('K线数据不足，无法分析')
        return

    ret5 = 0.0
    if len(closes) >= 6:
        ret5 = (closes[-1] - closes[-6]) / closes[-6] * 100

    ret20 = 0.0
    if len(closes) >= 21:
        ret20 = (closes[-1] - closes[-21]) / closes[-21] * 100
    elif len(closes) >= 11:
        ret20 = (closes[-1] - closes[-11]) / closes[-11] * 100

    ret60_val = 0.0
    if len(closes) >= 61:
        ret60_val = (closes[-1] - closes[-61]) / closes[-61] * 100
    elif len(closes) >= 31:
        ret60_val = (closes[-1] - closes[-31]) / closes[-31] * 100

    up5 = calc_up_count(closes, 5)
    up20 = calc_up_count(closes, 20)

    ma20 = 0.0
    if len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20.0
    else:
        ma20 = sum(closes) / float(len(closes))

    cur = closes[-1]
    above = cur > ma20
    slope = False
    if len(closes) >= 20:
        recent = sum(closes[-5:]) / 5.0
        older = sum(closes[-20:-5]) / 15.0
        slope = recent > older

    ts = ret20 * 0.4 + ret5 * 0.3 + (float(up5) / 5.0) * 20.0 * 0.3
    bs = ret60_val * 0.6 + ret20 * 0.4
    pf = max(0.0, min(100.0, 50.0 - cur / 2.0))
    comp = ts * 0.5 + bs * 0.3 + pf * 0.2

    if above and slope:
        state, w = '🐂 上涨趋势', (0.60, 0.25, 0.15)
    elif not above and not slope:
        state, w = '🐻 下跌趋势', (0.25, 0.50, 0.25)
    else:
        state, w = '⚖️ 震荡整理', (0.40, 0.35, 0.25)

    ds = ts * w[0] + bs * w[1] + pf * w[2]
    trend = '上涨趋势' if above and slope else '下跌趋势' if not above and not slope else '震荡整理'

    print('=' * 50)
    print(code.upper() + ' ' + n + ' 实时行情')
    print('=' * 50)
    print('现价: {:.2f}元  {:+.2f}%'.format(price, pct))
    print('')
    print('=== 技术面分析 ===')
    print('5日涨跌: {:+.1f}%  持续{:d}/5'.format(ret5, up5))
    print('20日涨跌: {:+.1f}%  持续{:d}/20'.format(ret20, up20))
    print('60日涨跌: {:+.1f}%'.format(ret60_val))
    print('20日均线: {:.2f}元  {}均线'.format(ma20, '高于' if above else '低于'))
    print('均线方向: {}'.format('向上' if slope else '向下'))
    print('')
    print('=== 三维评分 ===')
    print('技术面: {:.1f}  基本面: {:.1f}  产业渗透率: {:.1f}'.format(ts, bs, pf))
    print('综合评分(固定50/30/20): {:.1f}'.format(comp))
    print('')
    print('=== 市场状态 === ' + state)
    print('动态加权综合分: {:.1f}'.format(ds))
    print('')
    print('=== 综合结论 ===')
    print('现价{:.2f}元，{}'.format(cur, trend))
    if ret20 > 10:
        print('✅ 20日强势，上涨动能充足')
    elif ret20 > 3:
        print('🟢 20日偏强，趋势向好')
    elif ret20 < -5:
        print('🔴 20日走弱，注意风险')
    else:
        print('🟡 方向待观察')
    print('')
    print('⚠️ 本分析仅供参考，不构成投资建议')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python analyze_stock.py <代码>')
        print('例: python analyze_stock.py sz002384')
        print('    python analyze_stock.py sh600105')
        sys.exit(1)
    analyze(sys.argv[1])
