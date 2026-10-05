# -*- coding: utf-8 -*-
"""循环监测器（带GUI界面）：
- 每5~6分钟体检一次评论区新评论
- 检测111/异常评论（明确表达被打扰）→ 自动发布道歉语+@该用户（绝不重复）
- 与召唤脚本同样风格的置顶控制台：开始/停止/实时数据
  · 已道歉人数 / 本轮扫描次数 / 新评论数 / 最新发现
  · 监测日志滚动显示（最近N条事件）
- flag文件: apology_flag.txt (RUN/STOP)"""
import io, sys, os, json, time, re, random, threading, queue
import tkinter as tk
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"E:\欧尼酱_召唤工作区")
from cdp import CDP

WORK = r"E:\欧尼酱_召唤工作区"
URL = "https://www.bilibili.com/video/BV1VdHE6PEEa"
AID = 117384258060764
SELF_MID = 3706929960454980
FLAG = os.path.join(WORK, "apology_flag.txt")
STATE_F = os.path.join(WORK, "apology_state.json")
QFILE = os.path.join(WORK, "apologies.json")
LOG_F = os.path.join(WORK, "apology_log.txt")

def log(m):
    line = time.strftime("[%H:%M:%S] ") + str(m)
    with open(LOG_F, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line

def P():
    if os.path.exists(STATE_F):
        d = json.load(open(STATE_F, encoding="utf-8"))
        for k, v in (("done_rpids", []), ("done_names", []), ("count", 0), ("fails", {})):
            d.setdefault(k, v)
        return d
    return {"done_rpids": [], "done_names": [], "count": 0, "fails": {}}
def S(p):
    json.dump(p, open(STATE_F + ".t", "w", encoding="utf-8"), ensure_ascii=False); os.replace(STATE_F + ".t", STATE_F)

ck_cache = [None]
def hdrs():
    if ck_cache[0] is None:
        ck_cache[0] = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
    ck = ck_cache[0]
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
            "Referer": URL,
            "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items() if v)}

def api_get(url, retries=3):
    for a in range(retries):
        try:
            r = urllib.request.Request(url, headers=hdrs())
            with urllib.request.urlopen(r, timeout=15) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            if d.get("code", -1) in (-412, -352):
                time.sleep(60); continue
            return d
        except Exception:
            time.sleep(5 + a * 10)
    return None

def is_optout(msg):
    """新判定原理（用户定稿）：只要评论内容里含"1"这个数字（无论前面后面加了什么内容），
    一律判定为不想订阅者 → 拉黑名单+道歉。"""
    m = msg.strip()
    if not m:
        return False
    if "1" in m:
        return True
    # 兜底：明确表达被打扰的也纳入
    if ("别@" in m or "不要@" in m or "别艾特" in m or "别at" in m) and len(m) < 40:
        return True
    if ("打扰" in m and ("别" in m or "不要" in m or "取消" in m or "退" in m) and "@" not in m):
        return True
    return False

def scan_111():
    out = []
    roots_meta = []
    cur = 0
    seen_rpids = set()
    for pg in range(5):
        d = api_get("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (AID, cur))
        if not d or d.get("code") != 0:
            break
        dd = d.get("data") or {}
        reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
        if not reps:
            break
        for r_ in reps:
            root_rpid = r_.get("rpid")
            def chk(item, root):
                mid = str((item.get("member") or {}).get("mid") or "")
                uname = (item.get("member") or {}).get("uname", "")
                msg = ((item.get("content") or {}).get("message") or "").strip()
                if mid and mid != str(SELF_MID) and is_optout(msg) and item.get("rpid") not in seen_rpids:
                    seen_rpids.add(item.get("rpid"))
                    out.append({"rpid": item.get("rpid"), "mid": mid, "uname": uname, "msg": msg[:50], "root": root})
            chk(r_, root_rpid)
            for sub in (r_.get("replies") or []):
                chk(sub, root_rpid)
            rc = r_.get("rcount") or 0
            if rc > len(r_.get("replies") or []):
                roots_meta.append((root_rpid, rc))
        cu = dd.get("cursor") or {}
        cur = cu.get("next", 0)
        if cu.get("is_end"):
            break
        time.sleep(0.6)
    for root_rpid, rc in roots_meta[:15]:
        for pn in range(1, min(4, rc // 20 + 2)):
            d2 = api_get("https://api.bilibili.com/x/v2/reply/reply?type=1&oid=%d&root=%d&pn=%d&ps=20" % (AID, root_rpid, pn))
            if not d2 or d2.get("code") != 0:
                break
            reps2 = (d2.get("data") or {}).get("replies") or []
            if not reps2:
                break
            for sub in reps2:
                mid = str((sub.get("member") or {}).get("mid") or "")
                uname = (sub.get("member") or {}).get("uname", "")
                msg = ((sub.get("content") or {}).get("message") or "").strip()
                if mid and mid != str(SELF_MID) and is_optout(msg) and sub.get("rpid") not in seen_rpids:
                    seen_rpids.add(sub.get("rpid"))
                    out.append({"rpid": sub.get("rpid"), "mid": mid, "uname": uname, "msg": msg[:50], "root": root_rpid})
            time.sleep(0.5)
    return out

def already_apologized_set():
    done = set()
    try:
        cur = 0
        for pg in range(6):
            d = api_get("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (AID, cur))
            if not d or d.get("code") != 0:
                break
            dd = d.get("data") or {}
            reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
            if not reps:
                break
            for r_ in reps:
                for sub in ((r_.get("replies") or []) + [r_]):
                    mid = str((sub.get("member") or {}).get("mid") or "")
                    msg = ((sub.get("content") or {}).get("message") or "")
                    if mid == str(SELF_MID) and re.search(r"(已经收到|收到您的111|您的111|退订|永久移除|免打扰|深表歉意|打扰了，实在抱歉|对不起，打扰您了|十分抱歉！您的111)", msg):
                        m2 = re.match(r"^@(.+?)\s", msg.strip())
                        if m2:
                            done.add(m2.group(1))
            cu = dd.get("cursor") or {}
            cur = cu.get("next", 0)
            if cu.get("is_end"):
                break
            time.sleep(0.5)
    except Exception:
        pass
    return done

# ---------- CDP helpers ----------
WALK = r"""
window.__walk2=function(){function go(r,f,d){if(!r||d>20)return;try{f(r)}catch(e){}if(r.shadowRoot)go(r.shadowRoot,f,d+1);if(r.querySelectorAll){var k;try{k=r.querySelectorAll('*')}catch(e){return}for(var i=0;i<k.length;i++){try{f(k[i])}catch(e){}if(k[i].shadowRoot)go(k[i].shadowRoot,f,d+1)}}}return go}();
window.__eds=function(){var eds=[];__walk2(document,function(n){if(n.matches&&n.matches('.brt-editor[contenteditable="true"]')){var b=n.getBoundingClientRect();if(b.width>40)eds.push({x:b.x,y:b.y,w:b.width,h:b.height,t:(n.innerText||'')});}});eds.sort(function(a,b){return a.y-b.y});return eds;};
window.__expandall=function(){var clicked=0;__walk2(document,function(n){if(n.childElementCount===0){var t=(n.textContent||'').trim();if(clicked<30&&/^(共\s*\d+\s*条回复|展开更多回复|查看更多回复|更多回复|展开\d+条回复)/.test(t)){var b=n.getBoundingClientRect();if(b.width>0){try{(n.closest('button,[class*=btn],[class*=expand],[class*=more],[class*=item]')||n).click();clicked++;}catch(e){}}}}});return clicked;};
window.__replybtn=function(uname,msg){var m=(msg||'111').slice(0,20);var leaves=[];__walk2(document,function(n){if(n.childElementCount===0){var t=(n.textContent||'').trim();if(t&&t.length<=40&&(t===m||t.indexOf(m)===0||m.indexOf(t)===0||(t==='111'&&m.indexOf('111')>=0)))leaves.push(n);}});
 for(var i=0;i<leaves.length;i++){var item=leaves[i];
  for(var lv=0;lv<20;lv++){var up=item.parentElement||(item.getRootNode&&item.getRootNode().host);if(!up)break;item=up;var full='';try{full=(item.textContent||'');}catch(e){break;}
   if(full.indexOf(uname)<0){if(full.length>9000)break;else continue;}
   var btn=null;__walk2(item,function(n2){if(!btn&&n2.childElementCount===0&&(n2.textContent||'').trim()==='回复'){var b=n2.getBoundingClientRect();if(b.width>0)btn={x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)};}});
   if(btn)return btn;
   if(full.length>9000)break;}}
 return null;};
window.__pub_hidden=function(){var btn=null;__walk2(document,function(n){if(!btn&&n.tagName==='BUTTON'&&/^发布$|^发表$/.test((n.textContent||'').trim())&&n.className.indexOf('active')>=0)btn=n;});if(!btn)return 'NOBTN';var a=btn;for(var k=0;k<4&&a;k++){if(a.classList&&a.classList.contains('hidden'))a.classList.remove('hidden');a=a.parentElement||(a.getRootNode&&a.getRootNode().host);}if(getComputedStyle(btn).display==='none')return 'HIDDEN';btn.click();return 'CLICKED';};
window.__pubrect=function(){var btn=null;__walk2(document,function(n){if(!btn&&n.tagName==='BUTTON'&&/^发布$|^发表$/.test((n.textContent||'').trim())&&n.className.indexOf('active')>=0){var b=n.getBoundingClientRect();if(b.width>4)btn={x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)};}});return btn;};
window.__replyed=function(){var eds=[];__walk2(document,function(n){if(n.matches&&n.matches('.brt-editor[contenteditable="true"]')){var b=n.getBoundingClientRect();if(b.width>40)eds.push({el:n,b:b});}});
 for(var i=0;i<eds.length;i++){var a=eds[i].el,s='';for(var k=0;k<7&&a;k++){s+=(a.textContent||'').slice(0,26);a=a.parentElement||(a.getRootNode&&a.getRootNode().host);}
  if(s.indexOf('回复')>=0){window.__tred=eds[i].el;return {x:Math.round(eds[i].b.x),y:Math.round(eds[i].b.y),w:Math.round(eds[i].b.width),h:Math.round(eds[i].b.height)};}}
 return null;};
"""

def connect():
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=4) as r:
                tg = json.loads(r.read().decode())
            ws = next((t["webSocketDebuggerUrl"] for t in tg if t.get("type") == "page" and "bilibili.com" in t.get("url", "")), None)
            if ws:
                c = CDP(ws); c.cmd("Page.enable"); c.cmd("Runtime.enable")
                return c
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("no browser")

def js(c, code):
    v, e = c.eval(code)
    return v if not e else "E:" + str(e)

def click(c, x, y):
    c.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1, "buttons": 1}); time.sleep(0.1)
    c.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}); time.sleep(0.6)

def apologize(c, uname, msg, text):
    cur = js(c, "location.href")
    if "BV1VdHE6PEEa" not in cur:
        c.navigate(URL); time.sleep(9)
    js(c, WALK)
    for si in range(30):
        at_bottom = js(c, "(function(){return (window.innerHeight+window.scrollY)>=(document.body.scrollHeight-40);})()")
        if si > 0 and at_bottom:
            break
        c.cmd("Input.synthesizeScrollGesture", {"x": 700, "y": 400, "xDistance": 0, "yDistance": 700, "speed": 700})
        time.sleep(0.9)
    for _ in range(3):
        n = js(c, "window.__expandall()")
        time.sleep(1.6)
        if n == 0:
            break
    r = js(c, "JSON.stringify(window.__replybtn(%s,%s))" % (json.dumps(uname, ensure_ascii=False), json.dumps(msg, ensure_ascii=False)))
    try:
        btn = json.loads(r) if r and r != "null" else None
    except Exception:
        btn = None
    if not btn:
        return False, "找不到他的111楼层"
    r2 = js(c, "(function(){var b=null;__walk2(document,function(n){if(!b&&n.childElementCount===0&&(n.textContent||'').trim()==='回复'){var rc=n.getBoundingClientRect();if(Math.abs(rc.x+rc.width/2-%d)<4&&Math.abs(rc.y+rc.height/2-%d)<4)b=n;}});if(b){(b.closest('button,[class*=btn],[class*=action]')||b).click();return 'OPENED';}return 'NOBTN';})()" % (btn["x"], btn["y"]))
    if "OPENED" not in str(r2):
        return False, "回复按钮点不开"
    time.sleep(2.0)
    ed = js(c, "JSON.stringify(window.__replyed())")
    try:
        e = json.loads(ed) if ed and ed != "null" else None
    except Exception:
        e = None
    if not e:
        return False, "楼中楼编辑器未出现"
    click(c, e["x"] + e["w"] - 20, e["y"] + e["h"] - 4)
    time.sleep(0.5)
    c.cmd("Input.insertText", {"text": text})
    time.sleep(1.2)
    pb = js(c, "JSON.stringify(window.__pubrect())")
    try:
        bp = json.loads(pb) if pb and pb != "null" else None
    except Exception:
        bp = None
    if bp:
        click(c, bp["x"], bp["y"])
    else:
        r3 = js(c, "window.__pub_hidden()")
        if "CLICKED" not in str(r3):
            return False, "发布按钮不可用"
    t_end = time.time() + 12
    while time.time() < t_end:
        time.sleep(1.2)
        eds = js(c, "JSON.stringify(window.__eds())")
        try:
            arr = json.loads(eds)
        except Exception:
            arr = []
        if not arr or len(arr[0].get("t", "")) < 8:
            return True, "OK"
    return False, "编辑器未清空"

# ============ 监测线程 ============
class Monitor(threading.Thread):
    def __init__(self, ui_q):
        super().__init__(daemon=True)
        self.ui_q = ui_q
        self.c = None
        self.stop_flag = False

    def ui(self, m):
        self.ui_q.put(m)

    def run(self):
        apols = json.load(open(QFILE, encoding="utf-8"))["apologies"]
        self.ui("监测线程启动：5~6分钟/轮")
        while not self.stop_flag:
            try:
                if open(FLAG, encoding="utf-8").read().strip() != "RUN":
                    time.sleep(5)
                    continue
                st = P()
                found = scan_111()
                self.ui("体检完成：发现111/异常 %d 人" % len(found))
                hard_done = already_apologized_set()
                if hard_done:
                    st["done_names"] = list(set(st["done_names"]) | hard_done)
                    S(st)
                new = [f for f in found
                       if f["rpid"] not in st["done_rpids"]
                       and f["uname"] not in st["done_names"]
                       and f["uname"] not in hard_done
                       and st["fails"].get(str(f["rpid"]), 0) < 3]
                if new:
                    self.ui("待道歉：%d 人" % len(new))
                    if self.c is None:
                        self.c = connect()
                    for f in new:
                        self.ui("→ 处理 @%s | 他发布的内容: %s" % (f["uname"], f["msg"]))
                        text = apols[st["count"] % len(apols)].replace("{name}", f["uname"])
                        try:
                            ok, why = apologize(self.c, f["uname"], f["msg"], text)
                        except Exception as ex:
                            ok, why = False, "异常 %r" % ex
                        if ok:
                            st["done_rpids"].append(f["rpid"])
                            st["done_names"].append(f["uname"])
                            st["count"] += 1
                            S(st)
                            self.ui("✅ 已艾特并道歉 @%s（版本%d）| 其发布内容: %s" % (f["uname"], (st["count"] - 1) % len(apols) + 1, f["msg"]))
                        else:
                            st["fails"][str(f["rpid"])] = st["fails"].get(str(f["rpid"]), 0) + 1
                            S(st)
                            self.ui("❌ @%s 失败(第%d次): %s | 其发布内容: %s" % (f["uname"], st["fails"][str(f["rpid"])], why, f["msg"]))
                        # 道歉间隔：每人之间隔60秒（用户要求每分钟一人）
                        time.sleep(60)
                    # 退订剔除
                    stq = json.load(open(os.path.join(WORK, "sent_state.json"), encoding="utf-8"))
                    drop = set(st["done_names"])
                    b = len(stq["remaining"])
                    stq["remaining"] = [n for n in stq["remaining"] if n not in drop]
                    if len(stq["remaining"]) != b:
                        json.dump(stq, open(os.path.join(WORK, "sent_state.json"), "w", encoding="utf-8"), ensure_ascii=False)
                        self.ui("待发名单剔除%d人" % (b - len(stq["remaining"])))
                wait = random.randint(300, 360)  # 5~6分钟
                self.ui("休眠%d秒后下一轮…" % wait)
                for _ in range(wait):
                    if self.stop_flag or open(FLAG, encoding="utf-8").read().strip() != "RUN":
                        break
                    time.sleep(1)
            except Exception as e:
                self.ui("监测异常: %r，60s后重试" % e)
                time.sleep(60)

# ============ GUI ============
def main_gui():
    if not os.path.exists(FLAG):
        open(FLAG, "w", encoding="utf-8").write("RUN")
    root = tk.Tk()
    root.title("评论监测·道歉控制台")
    root.geometry("560x430")
    root.attributes("-topmost", True)
    q = queue.Queue()

    stat_vars = {
        "state": tk.StringVar(value="监测中"),
        "done": tk.StringVar(value="0"),
        "scans": tk.StringVar(value="0"),
        "found": tk.StringVar(value="0"),
    }
    scan_count = [0]

    def pump():
        try:
            while True:
                m = q.get_nowait()
                if m.startswith("体检完成"):
                    scan_count[0] += 1
                    stat_vars["scans"].set(str(scan_count[0]))
                    try:
                        stat_vars["done"].set(str(len(json.load(open(STATE_F, encoding="utf-8"))["done_names"])))
                    except Exception:
                        pass
                elif m.startswith("✅"):
                    try:
                        stat_vars["done"].set(str(len(json.load(open(STATE_F, encoding="utf-8"))["done_names"])))
                    except Exception:
                        pass
                txt.insert("end", m + "\n")
                txt.see("end")
                with open(LOG_F, "a", encoding="utf-8") as f:
                    f.write(time.strftime("[%H:%M:%S] ") + m + "\n")
        except queue.Empty:
            pass
        root.after(700, pump)

    f0 = tk.Frame(root); f0.pack(pady=8)
    tk.Button(f0, text="▶ 开始监测", font=("微软雅黑", 12, "bold"), width=12, bg="#2ecc71", fg="white",
              command=lambda: (open(FLAG, "w", encoding="utf-8").write("RUN"), stat_vars["state"].set("监测中"))).pack(side="left", padx=8)
    tk.Button(f0, text="■ 停止监测", font=("微软雅黑", 12, "bold"), width=12, bg="#e74c3c", fg="white",
              command=lambda: (open(FLAG, "w", encoding="utf-8").write("STOP"), stat_vars["state"].set("已停止"))).pack(side="left", padx=8)

    f1 = tk.Frame(root); f1.pack(pady=4)
    rows = [("监测状态", stat_vars["state"]), ("已道歉人数", stat_vars["done"]),
            ("体检轮数", stat_vars["scans"]), ("发现111/异常", stat_vars["found"])]
    for i, (k, v) in enumerate(rows):
        tk.Label(f1, text=k + "：", font=("微软雅黑", 11), width=8, anchor="e").grid(row=i, column=0, sticky="e", pady=2)
        tk.Label(f1, textvariable=v, font=("微软雅黑", 11, "bold"), fg="#0984e3", width=26, anchor="w").grid(row=i, column=1, sticky="w", pady=2)

    tk.Label(root, text="监测日志（每5~6分钟自动体检一次评论区）：", font=("微软雅黑", 9), fg="#636e72", anchor="w").pack(fill="x", padx=12)
    txt = tk.Text(root, font=("Consolas", 9), height=9, bg="#1e1e1e", fg="#d4d4d4")
    txt.pack(fill="both", expand=True, padx=12, pady=(2, 12))

    mon = Monitor(q)
    mon.start()
    pump()
    root.mainloop()

if __name__ == "__main__":
    main_gui()
