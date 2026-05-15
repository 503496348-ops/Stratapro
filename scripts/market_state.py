# -*- coding: utf-8 -*-
"""
统一市场状态识别模块
===================
所有市场状态判断的单一数据源，避免多个脚本判断结论矛盾。
数据源：新浪财经 ETF K线数据

返回: 'bull'(牛市)|'bear'(熊市)|'mixed'(震荡市)
"""
import urllib.request
import json

# 新浪ETF行情接口（大盘指标用510300华泰柏瑞沪深300ETF）
ETFS = [
    ('sh510300', '沪深300'),
    ('sh510500', '中证500'),
    ('sh588000', '科创50'),
]

def detect_market_state():
    """返回: 'bull'(牛市)|'bear'(熊市)|'mixed'(震荡市)"""
    closes = {}
    ma20_vals = {}
    
    for code, name in ETFS:
        url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={code}&scale=240&ma=no&datalen=25'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                klines = json.load(resp)
                if isinstance(klines, list) and len(klines) >= 20:
                    close_prices = [float(k['close']) for k in klines]
                    current = close_prices[-1]
                    ma20 = sum(close_prices[-20:]) / 20
                    slope = (close_prices[-1] - close_prices[-5]) / 5
                    closes[code] = {'current': current, 'ma20': ma20, 'slope': slope}
        except:
            pass
    
    if len(closes) == 0:
        return 'mixed'  # 无数据默认震荡
    
    # 多数原则
    bull_count = sum(1 for c in closes.values() if c['current'] > c['ma20'] and c['slope'] > 0)
    bear_count = sum(1 for c in closes.values() if c['current'] < c['ma20'] and c['slope'] < 0)
    
    if bull_count >= 2:
        return 'bull'
    elif bear_count >= 2:
        return 'bear'
    else:
        return 'mixed'


def get_market_state_info():
    """返回状态信息字典（含emoji和label）"""
    state = detect_market_state()
    info_map = {
        'bull': {'emoji': '🐂', 'label': '上涨趋势', 'label_cn': '牛市'},
        'bear': {'emoji': '🐻', 'label': '下跌趋势', 'label_cn': '熊市'},
        'mixed': {'emoji': '⚖️', 'label': '震荡整理', 'label_cn': '震荡市'},
    }
    return info_map.get(state, info_map['mixed'])


if __name__ == '__main__':
    state = detect_market_state()
    info = get_market_state_info()
    print(f"市场状态: {info['emoji']}{info['label_cn']}({state})")
