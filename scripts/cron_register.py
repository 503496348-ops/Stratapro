# -*- coding: utf-8 -*-
"""
Cron任务注册脚本
================
输出标准crontab格式配置，供用户手动添加到系统crontab。

使用方式：
  python3 cron_register.py

或者查看本文件底部的 crontab_config 变量，手动添加到crontab。
"""
import os
from datetime import datetime

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_ROOT, 'scripts')
LOGS_DIR = os.path.join(SKILL_ROOT, 'logs')

# 确保logs目录存在
os.makedirs(LOGS_DIR, exist_ok=True)

# ── 标准权重配置（用于参考，不参与cron执行） ─────────────────
# 详见 config/weights.json

# ── Crontab 配置模板 ───────────────────────────────────────
crontab_config = f"""
# ============================================================
# 汇金选股 Skill 定时任务配置
# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
# Skill根目录: {SKILL_ROOT}
# ============================================================

# ── 日报定时任务（周一至周五16:00 CST）──────────────────────
# 16:00是A股收盘后30分钟，数据最完整
0 16 * * 1-5 {os.path.join(SCRIPTS_DIR, 'market_report_v8.py')} >> {os.path.join(LOGS_DIR, 'daily_report.log')} 2>&1

# ── 盘中预警定时任务（周一至周五9:30-14:57，每30分钟）──────
# 9:30开盘首检，14:57收盘前最后检查，每30分钟检查一次
30,0 9-14 * * 1-5 {os.path.join(SCRIPTS_DIR, 'v3_alert_module.py')} >> {os.path.join(LOGS_DIR, 'alert.log')} 2>&1

# 说明：
#   - 日报：每天16:00生成并推送，包含完整的赛道排名和情绪分析
#   - 盘中预警：交易时段每30分钟扫描一次，检测持仓警戒、价格异动、量能异常
#   - 日志文件：查看日报问题先看 {os.path.join(LOGS_DIR, 'daily_report.log')}
#   - 盘中预警问题先看 {os.path.join(LOGS_DIR, 'alert.log')}
#
# 添加到系统crontab：
#   crontab -e
#   # 然后粘贴上面的内容
#
# 查看当前crontab：
#   crontab -l
#
# 删除所有汇金相关crontab：
#   crontab -l | grep -v 'stock-analysis' | crontab -
# ============================================================
"""

def print_crontab():
    """打印crontab配置"""
    print(crontab_config)

def get_crontab_lines():
    """返回需要添加的crontab行列表"""
    lines = [
        "# 汇金选股 Skill - 日报（周一至周五16:00）",
        f"0 16 * * 1-5 {os.path.join(SCRIPTS_DIR, 'market_report_v8.py')} >> {os.path.join(LOGS_DIR, 'daily_report.log')} 2>&1",
        "# 汇金选股 Skill - 盘中预警（周一至周五9:30-14:57，每30分钟）",
        f"30,0 9-14 * * 1-5 {os.path.join(SCRIPTS_DIR, 'v3_alert_module.py')} >> {os.path.join(LOGS_DIR, 'alert.log')} 2>&1",
    ]
    return lines

def add_to_crontab():
    """尝试自动添加到当前用户crontab（需要权限）"""
    import subprocess
    lines = get_crontab_lines()
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except:
        existing = ""
    
    new_crontab = existing.rstrip() + "\n" + "\n".join(lines) + "\n"
    
    try:
        proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(input=new_crontab.encode())
        if proc.returncode == 0:
            print("✅ Crontab配置已添加")
            return True
        else:
            print(f"⚠️ 自动添加失败，请手动运行 crontab -e 添加：\n")
            print("\n".join(lines))
            return False
    except Exception as e:
        print(f"⚠️ 错误: {e}")
        print("\n请手动运行以下命令添加crontab：")
        print("\n".join(lines))
        return False


if __name__ == '__main__':
    print("=== 汇金选股 Skill Crontab 配置 ===")
    print(crontab_config)
    print("\n--- 快速添加 ---")
    print("如果想让本脚本尝试自动添加crontab，请运行：")
    print("  python3 cron_register.py --add")
