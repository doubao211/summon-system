# -*- coding: utf-8 -*-
"""二维码登录 v4：412问题——改用B站浏览器页面完成登录（扫码后浏览器自动种cookie），
然后用CDP把cookie读出来存session.json"""
import io, sys, json, time, os, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = r"E:\欧尼酱_召唤工作区"

# 1) 打开B站登录页（用户的调试Edge，之前已停了所有，重新拉起）
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(edge):
    edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
os.system('start "" "%s" --remote-debugging-port=9222 --user-data-dir="%s" --no-first-run --window-size=1300,1000 "https://www.bilibili.com/"' % (edge, os.path.join(WORK, "edge_profile")))
print("浏览器已打开B站首页。", flush=True)
print("请在浏览器右上角点【登录】→ 扫码登录（用新账号）→ 确认登录完成。", flush=True)
print("我每3秒检查一次登录态，检测到新登录就自动提取cookie。", flush=True)

time.sleep(8)
sys.path.insert(0, WORK)
from cdp import CDP

def get_ws():
    tg = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
    return next((t["webSocketDebuggerUrl"] for t in tg if t.get("type") == "page" and "bilibili.com" in (t.get("url") or "")), None)

t0 = time.time()
while time.time() - t0 < 600:
    try:
        ws = get_ws()
        if not ws:
            time.sleep(3); continue
        c = CDP(ws)
        r = c.cmd("Runtime.evaluate", {"expression": "document.cookie", "returnByValue": True})
        doc_cookie = (r.get("result") or {}).get("value") or ""
        cookies = {}
        for kv in doc_cookie.split(";"):
            if "=" in kv:
                k, v = kv.strip().split("=", 1)
                cookies[k] = v
        if cookies.get("SESSDATA") and cookies.get("bili_jct") and cookies.get("DedeUserID"):
            json.dump(cookies, open(os.path.join(WORK, "session.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("\n=== 登录检测成功！已保存 session.json ===")
            print("  DedeUserID =", cookies.get("DedeUserID"))
            print("  SESSDATA = 有")
            print("  bili_jct = 有")
            # 验证账号名
            try:
                H2 = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
                      "Cookie": "; ".join("%s=%s" % (k, v) for k, v in cookies.items() if v)}
                d = json.loads(urllib.request.urlopen(urllib.request.Request(
                    "https://api.bilibili.com/x/web-interface/nav", headers=H2), timeout=15).read())
                print("  账号昵称 =", (d.get("data") or {}).get("uname", "?"))
                print("  mid =", (d.get("data") or {}).get("mid", "?"))
            except Exception:
                pass
            break
        print("等待登录…（检测到 %d 个cookie，还缺SESSDATA/bili_jct/DedeUserID）" % len(cookies), flush=True)
    except Exception as e:
        print("err %r" % e, flush=True)
    time.sleep(3)
