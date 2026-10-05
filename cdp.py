# -*- coding: utf-8 -*-
"""CDP (Chrome DevTools Protocol) driver for Edge remote debugging."""
import json, base64, itertools, urllib.request
import websocket

def list_targets():
    with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5) as r:
        return json.loads(r.read().decode())

def page_ws_url(match=None):
    for t in list_targets():
        if t.get("type") == "page" and (match is None or match in (t.get("url") or "")):
            return t["webSocketDebuggerUrl"]
    return None

class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
        self.ids = itertools.count(1)

    def cmd(self, method, params=None):
        i = next(self.ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                return msg.get("result", {})

    def eval(self, js):
        """执行JS并返回 (值, 异常信息)"""
        r = self.cmd("Runtime.evaluate", {"expression": js, "returnByValue": True})
        val = r.get("result", {}).get("value")
        err = r.get("exceptionDetails")
        return val, (err.get("text") if err else None)

    def screenshot(self, path):
        r = self.cmd("Page.captureScreenshot", {"format": "jpeg", "quality": 72})
        data = base64.b64decode(r["data"])
        with open(path, "wb") as f:
            f.write(data)
        return path

    def navigate(self, url):
        return self.cmd("Page.navigate", {"url": url})
