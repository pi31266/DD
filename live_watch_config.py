# -*- coding: utf-8 -*-
"""
live_watch_config.py - 抖音直播监听配置文件
"""

# 🎯 抖音相关关键词（用于过滤感兴趣数据字段）
ALL_SENSITIVE_KEYS = [
    "nickname", "user_id", "gift", "diamond_count",
    "user", "room", "message", "chat", "danmu", "webcast", "anchor", "audience"
]

# 🎯 请求URL包含这些关键词才会被记录（降低无效数据）
TRUE_MATCH_KEYWORDS = [
    "webcast", "live", "room", "gift", "msg", "chat", "danmu", "bullet", "im"
]

# 🛡️ 屏蔽无关域名（节省性能）
EXCLUDED_DOMAINS = [
    "googleapis.com", "baidu.com", "gstatic.com", "qq.com",
    "geetest.com", "chromewebstore", "update.googleapis.com",
    "googletagmanager.com", "tampermonkey.net", "byted.org",
    "pstatp.com", "douyincdn.com"
]

# 🧠 浏览器模拟UA（按需随机）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 Version/16.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.77 Mobile Safari/537.36"
]

# 📁 日志保存目录
SAVE_DIR = "mitm_logs"
WS_SAVE_DIR = "mitm_logs/ws_logs"
COOKIE_FILE = "douyin_cookies.json"

# ⏱️ 抓包设置
SCAN_INTERVAL = 5                # 抓包扫描间隔秒
MONITOR_TIME = 60                # 默认浏览器保持运行时间（可手动退出）
MAX_CONCURRENT_BROWSERS = 1      # 只开一个浏览器，避免冲突

# 🔐 限制存储
SAVE_ONLY_IF_MATCH = False        # 只保存符合条件的数据
SAVE_POST_ONLY = False           # 只记录 POST 请求
ENABLE_LOG_LIMIT = True          # 限制单域名保存量
MAX_LOGS_PER_DOMAIN = 100        # 每域名最多保存的封包文件数量

# 🧩 代理端口范围
PORT_RANGE = (8080, 8200)

# 🙈 忽略谷歌服务干扰
SKIP_UNKNOWN_GOOGLE_REQUESTS = True
