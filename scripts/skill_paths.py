# -*- coding: utf-8 -*-
"""
路径适配器：将Windows绝对路径 → Linux/Mac相对路径
自动检测OS，智能选择数据源配置

用法：直接 import 本文件后，所有路径变量会被正确设置
"""
import sys, os, platform

# 检测当前OS
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX   = platform.system() == 'Linux' or 'darwin' in platform.system().lower()

def get_skill_root():
    """获取skill包根目录（兼容Windows和Linux）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_scripts_dir():
    """获取脚本目录"""
    return os.path.join(get_skill_root(), 'scripts')

def get_data_dir():
    """获取数据目录"""
    base = get_skill_root()
    if IS_WINDOWS:
        # Windows：优先通达信本地数据
        tdx_path = r'D:\new_tdx\vipdoc'
        if os.path.exists(tdx_path):
            return tdx_path
        return os.path.join(base, 'data')
    else:
        # Linux/Mac：使用workspace数据目录
        return os.path.join(base, 'data')

def get_backup_dir():
    """获取备份目录"""
    base = get_skill_root()
    if IS_WINDOWS:
        return os.path.join(base, 'backup')
    else:
        return os.path.join(os.path.expanduser('~'), 'stock-analysis-backup')

def get_diary_dir():
    """获取日记存档目录"""
    base = get_skill_root()
    diary = os.path.join(base, 'diary')
    os.makedirs(diary, exist_ok=True)
    return diary

def get_alert_dir():
    """获取预警日志目录"""
    base = get_skill_root()
    alert = os.path.join(base, 'alert_logs')
    os.makedirs(alert, exist_ok=True)
    return alert

def get_knowledge_dir():
    """获取知识库目录（回测数据）"""
    base = get_skill_root()
    kb = os.path.join(base, 'knowledge_backtest')
    os.makedirs(kb, exist_ok=True)
    return kb

# ── 导出配置字典 ─────────────────────────────────────
SKILL_CONFIG = {
    'skill_root':    get_skill_root(),
    'scripts_dir':  get_scripts_dir(),
    'data_dir':     get_data_dir(),
    'backup_dir':   get_backup_dir(),
    'diary_dir':    get_diary_dir(),
    'alert_dir':    get_alert_dir(),
    'knowledge_dir': get_knowledge_dir(),
    'is_windows':   IS_WINDOWS,
    'is_linux':     IS_LINUX,
    'platform':     platform.system(),
    # 数据源优先级
    'data_source_priority': [
        'sina',      # 新浪财经（主力）
        'tencent',   # 腾讯行情（备用）
        'qveris',    # QVeris API（需Key）
        'tdx',       # 通达信本地（仅Windows）
    ],
    # 存档路径
    'archive_paths': {
        'daily_report': get_diary_dir(),
        'alert_log':    get_alert_dir(),
        'backtest_data': get_knowledge_dir(),
    },
}

if __name__ == '__main__':
    # 自测时打印配置
    print('=== Skill路径配置 ===')
    for k, v in SKILL_CONFIG.items():
        if k not in ('data_source_priority', 'archive_paths'):
            print(f'{k}: {v}')
    print(f'platform: {SKILL_CONFIG["platform"]}')
    print(f'is_windows: {IS_WINDOWS}')
    print(f'is_linux: {IS_LINUX}')
    print('\n=== 数据源优先级 ===')
    for src in SKILL_CONFIG['data_source_priority']:
        print(f'  - {src}')
