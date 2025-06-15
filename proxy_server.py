import os
import json
import asyncio
import logging
import threading
import queue
import gzip
from io import BytesIO
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict

from mitmproxy import options, http, websocket
from mitmproxy.tools.dump import DumpMaster

import live_watch_config as cfg

# 载入登录后的 Cookie（记得先用 cookie_getter.py 抓好）
with open("douyin_cookies.json", "r", encoding="utf-8") as f:
    LOGIN_COOKIES = json.load(f)

os.makedirs(cfg.SAVE_DIR, exist_ok=True)

class ProxyAddon:
    def __init__(self):
        self.domain_counter = defaultdict(int)
        self.domain_seen = 0
        self.domain_dump_interval = 100

    def _get_domain_from_url(self, url):
        return urlparse(url).netloc.replace(":", "_")

    def _get_base_domain(self, url):
        try:
            netloc = urlparse(url).netloc
            if not netloc or "." not in netloc:
                return "unknown"
            parts = netloc.split(".")
            return ".".join(parts[-2:])
        except:
            return "unknown"

    def _record_pollution(self, url):
        base = self._get_base_domain(url)
        self.domain_counter[base] += 1
        self.domain_seen += 1
        if self.domain_seen >= self.domain_dump_interval:
            self.domain_seen = 0
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            dump_path = os.path.join(cfg.SAVE_DIR, f"pollution_report_{timestamp}.json")
            with open(dump_path, "w", encoding="utf-8") as f:
                sorted_result = dict(sorted(self.domain_counter.items(), key=lambda x: -x[1]))
                json.dump(sorted_result, f, ensure_ascii=False, indent=2)

    def response(self, flow: http.HTTPFlow):
        try:
            self._save_douyin_data(flow)
        except Exception as e:
            print(f"[Douyin Response Save Error] {e}")

    def websocket_message(self, flow):
        try:
            if not hasattr(flow, "messages") or not flow.messages:
                return
            domain = self._get_domain_from_url(flow.request.url)
            folder = os.path.join(cfg.WS_SAVE_DIR, domain)
            os.makedirs(folder, exist_ok=True)

            for msg in flow.messages:
                direction = "SEND" if msg.from_client else "RECV"
                try:
                    payload = msg.content.decode("utf-8", errors="ignore")
                except Exception:
                    payload = "[Decode Error]"
                timestamp = datetime.now().strftime('%H%M%S_%f')
                save_path = os.path.join(folder, f"{timestamp}.txt")
                with open(save_path, "a", encoding="utf-8") as f:
                    f.write(f"[{direction}] {payload}\n")
        except Exception as e:
            print(f"[WebSocket Save Error] {e}")

    def _save_douyin_data(self, flow):
        try:
            if not flow.response:
                return
            if any(domain in flow.request.url for domain in cfg.EXCLUDED_DOMAINS):
                return

            self._record_pollution(flow.request.url)
            raw_body = flow.response.raw_content or b""
            encoding = flow.response.headers.get("Content-Encoding", "").lower()

            if encoding == "gzip":
                try:
                    buf = BytesIO(raw_body)
                    with gzip.GzipFile(fileobj=buf) as f:
                        decoded_body = f.read().decode("utf-8", errors="ignore")
                except:
                    decoded_body = "[Decompression Failed or Non-Text]"
            else:
                decoded_body = raw_body.decode("utf-8", errors="ignore")

            if not decoded_body.strip():
                return

            if cfg.SAVE_POST_ONLY and flow.request.method.upper() != "POST":
                return

            is_match = any(k.lower() in decoded_body.lower() for k in cfg.ALL_SENSITIVE_KEYS)
            if cfg.SAVE_ONLY_IF_MATCH and not is_match:
                return

            if not any(keyword in flow.request.url for keyword in cfg.TRUE_MATCH_KEYWORDS):
                return

            domain = self._get_domain_from_url(flow.request.url)
            log_dir = os.path.join(cfg.SAVE_DIR, domain, "douyin")
            os.makedirs(log_dir, exist_ok=True)
            save_path = os.path.join(log_dir, f"{datetime.now().strftime('%H%M%S_%f')}.json")

            injected_headers = dict(flow.request.headers)
            injected_headers["cookie"] = "; ".join([f"{k}={v}" for k, v in LOGIN_COOKIES.items()])

            data = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "url": flow.request.url,
                "method": flow.request.method,
                "request_headers": injected_headers,
                "request_body": flow.request.text,
                "response_status": flow.response.status_code,
                "response_headers": dict(flow.response.headers),
                "response_body": decoded_body,
            }

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"[Douyin Data Save Error] {e}")

async def run_mitmproxy(listen_port=8080):
    opts = options.Options(
        listen_host="127.0.0.1",
        listen_port=listen_port,
        http2=True,
        websocket=True,
        ssl_insecure=True
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(ProxyAddon())

    try:
        await master.run()
    except Exception as e:
        print(f"[Mitmproxy Shutdown Error] {e}")

def start_proxy_in_thread():
    port_queue = queue.Queue()

    def find_free_port(start, end):
        import socket
        for port in range(start, end):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except:
                    continue
        raise Exception("No free port available!")

    def thread_target():
        try:
            port = find_free_port(cfg.PORT_RANGE[0], cfg.PORT_RANGE[1])
            port_queue.put(port)
            logging.getLogger("mitmproxy").setLevel(logging.CRITICAL)
            print(f"[Douyin Proxy Monitor] Listening on port: {port}")
            asyncio.run(run_mitmproxy(listen_port=port))
        except Exception as e:
            print(f"[Proxy Thread Error] {e}")

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()

    try:
        return port_queue.get(timeout=3)
    except queue.Empty:
        raise RuntimeError("Proxy thread failed to start: no port returned")
