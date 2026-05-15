# -*- coding: utf-8 -*-
"""
conftest.py — pytest全局配置
在所有测试运行前设置dummy环境变量，避免QVeris API Key启动检查阻塞
"""
import os

# 设置测试环境变量（避免market_report_v8.py的RuntimeError检查阻塞）
os.environ.setdefault('QVERIS_API_KEY', 'sk-test-dummy-for-testing')
os.environ.setdefault('WEIXIN_TARGET_USER', 'test@wechat')
os.environ.setdefault('FEISHU_TARGET_USER', 'user:test')