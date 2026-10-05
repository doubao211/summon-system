# -*- coding: utf-8 -*-
"""检测当前edge_profile里登录的是谁 + 看是不是"别的账号"。
如果是别人的账号：提示用户退出（页面右上角头像→退出登录），然后重新扫码。"""
import io, sys, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"E:\欧尼酱_召唤工作区")
from cdp import CDP

tg = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
ws = next((t["webSocketDebuggerUrl"] for t in tg if t.get("type") == "page" and "bilibili.com" in (t.get("url") or "")), None)
c = CDP(ws)
r = c.cmd("Runtime.evaluate", {"expression": "document.cookie", "returnByValue": True})
doc = (r.get("result") or {}).get("value") or ""
cookies = {}
for kv in doc.split(";"):
    if "=" in kv:
        k, v = kv.strip().split("=", 1)
        cookies[k] = v
print("当前浏览器里的登录cookie数:", len(cookies))
if cookies.get("SESSDATA"):
    H = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
         "Cookie": "; ".join("%s=%s" % (k, v) for k, v in cookies.items() if v)}
    d = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav", headers=H), timeout=15).read())
    print("当前登录账号:", (d.get("data") or {}).get("uname"), "| mid =", (d.get("data") or {}).get("mid"))
    print("登录态:", "有效" if d.get("data", {}).get("isLogin") else "无效")
else:
    print("当前浏览器没有登录态（干净状态，可以直接扫码）")
