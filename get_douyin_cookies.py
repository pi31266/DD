from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json

COOKIE_FILE = "douyin_cookies.json"

def get_douyin_cookies():
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    driver.get("https://www.douyin.com/")

    print("请在打开的浏览器中手动登录抖音（扫码或输入手机号），然后按任意键继续...")
    input()

    cookies = driver.get_cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookie_dict, f, ensure_ascii=False, indent=2)

    print(f"[保存成功] Cookie 已保存到 {COOKIE_FILE}")
    driver.quit()

if __name__ == "__main__":
    get_douyin_cookies()
