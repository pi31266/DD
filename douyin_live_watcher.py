# -*- coding: utf-8 -*-

import os
import time
import threading
import json
import hashlib
from datetime import datetime
from urllib.parse import urlparse
import random
import signal
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import proxy_server

COOKIE_FILE = "douyin_cookies.json"

ALL_SENSITIVE_KEYS = ["nickname", "gift", "diamond", "msg", "chat"]
TRUE_MATCH_KEYWORDS = ["webcast", "room", "watch", "im", "live", "gift", "msg", "danmu", "chat"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.77 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 Version/16.3 Mobile/15E148 Safari/604.1"
]

SAVE_DIR = "mitm_logs"
FLOW_FILE = os.path.join(SAVE_DIR, "flows.json")
SCAN_INTERVAL = 5

stop_flag = threading.Event()
signal.signal(signal.SIGINT, lambda s, f: stop_flag.set())

packet_buffer = []
watchers = {}

def get_douyin_cookies():
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    driver.get("https://www.douyin.com/")

    print("\n请在打开的浏览器中手动登录抖音（扫码或输入手机号），然后按任意键继续...")
    input()

    cookies = driver.get_cookies()
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    print(f"[保存成功] Cookie 已保存到 {COOKIE_FILE}")
    driver.quit()

def create_stealth_driver(proxy_port):
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument(f"--proxy-server=http://127.0.0.1:{proxy_port}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    ua = random.choice(USER_AGENTS)
    options.add_argument(f"user-agent={ua}")

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.douyin.com")
    time.sleep(3)

    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            for cookie in cookies:
                try:
                    if 'domain' not in cookie:
                        cookie['domain'] = ".douyin.com"
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"[Cookie 注入失败] {cookie.get('name')} ({e})")

    driver.get("https://www.douyin.com/")
    time.sleep(2)

    return driver

def monitor_packets(session_tag):
    seen = set()
    last_size = 0
    while not stop_flag.is_set():
        try:
            if not os.path.exists(FLOW_FILE):
                time.sleep(SCAN_INTERVAL)
                continue

            with open(FLOW_FILE, "r", encoding="utf-8") as f:
                f.seek(last_size)
                lines = f.readlines()
                last_size = f.tell()

            for line in lines:
                try:
                    try:
                        flow = json.loads(line)
                        if not isinstance(flow, dict) or "request" not in flow or "response" not in flow:
                            continue
                    except Exception as e:
                        print(f"[Flow解析失败] {e} 内容: {line}")
                        continue

                    url = flow["request"].get("url", "")
                    method = flow["request"].get("method", "")
                    req_body = flow["request"].get("content", "")
                    resp_body = flow["response"].get("content", "")

                    fp = hashlib.md5((method + url).encode()).hexdigest()
                    if fp in seen:
                        continue
                    seen.add(fp)

                    nickname = None
                    gift_score = 0

                    try:
                        data = json.loads(resp_body)

                        def extract(obj):
                            name, score = None, 0
                            if isinstance(obj, dict):
                                if 'nickname' in obj:
                                    name = obj['nickname']
                                if 'gift' in obj and isinstance(obj['gift'], dict):
                                    score = obj['gift'].get('diamond_count', 0)
                                for v in obj.values():
                                    sub_name, sub_score = extract(v)
                                    name = name or sub_name
                                    score = score or sub_score
                            elif isinstance(obj, list):
                                for item in obj:
                                    sub_name, sub_score = extract(item)
                                    name = name or sub_name
                                    score = score or sub_score
                            return name, score

                        nickname, gift_score = extract(data)
                    except:
                        pass

                    if nickname:
                        if nickname not in watchers:
                            watchers[nickname] = 0
                            print(f"\n[观众] {nickname}")
                        if gift_score:
                            watchers[nickname] += gift_score
                            print(f"[礼物] {nickname} +{gift_score}")

                    if method == "POST" and req_body.strip():
                        if any(k in url for k in TRUE_MATCH_KEYWORDS):
                            packet_buffer.append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "method": method,
                                "url": url,
                                "request_body": req_body,
                                "response_body": resp_body,
                                "nickname": nickname,
                                "gift_score": gift_score
                            })
                except Exception as ex:
                    print(f"[解析错误] {ex}")
        except Exception as e:
            print(f"[监听错误] {e}")
        time.sleep(SCAN_INTERVAL)

def save_packet_report(session_tag):
    if not packet_buffer:
        print("[报告] 无封包记录")
    else:
        with open(f"packet_report_{session_tag}.json", "w", encoding="utf-8") as f:
            json.dump(packet_buffer, f, ensure_ascii=False, indent=2)
        print(f"[保存] 共 {len(packet_buffer)} 条封包记录")

    with open(f"watchers_{session_tag}.json", "w", encoding="utf-8") as f:
        json.dump(watchers, f, ensure_ascii=False, indent=2)
    print(f"[保存] 共 {len(watchers)} 位观众昵称（含礼物积分）")

def start_monitor(url, proxy_port):
    try:
        parsed = urlparse(url)
        session_tag = f"{parsed.hostname}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[启动监听] {url}")
        print(f"[记录标识] {session_tag}")

        driver = create_stealth_driver(proxy_port)
        driver.get(url)
        threading.Thread(target=monitor_packets, args=(session_tag,), daemon=True).start()
        while not stop_flag.is_set():
            time.sleep(5)
    except Exception as e:
        print(f"[监听错误] {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
        save_packet_report(session_tag)

def main():
    proxy_port = proxy_server.start_proxy_in_thread()
    print("\n欢迎使用抖音直播监听器")
    while True:
        url = input("请输入直播间链接（输入 exit 退出）: ").strip()
        if url.lower() == "exit":
            break
        if url:
            start_monitor(url, proxy_port)

if __name__ == "__main__":
    main()
