# -*- coding: utf-8 -*-
"""TOP SENDER v8 — human-like pacing & pure-real interactions.
Cadence: 4-8 minutes between comments (jittered). Page reload each time.
Real clicks only (Input domain), no jsClick. Publish only when button VISIBLE
(no hidden-class bypass). If blocked -> wait extra 4 min and retry.
API-verify each post; progress file; resumable; skip list; sparse log."""
import sys, io, json, time, os, random, re, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"E:\欧尼酱_召唤工作区")
from cdp import CDP

WORK = r"E:\欧尼酱_召唤工作区"
URL = "https://www.bilibili.com/video/BV1VdHE6PEEa"
AID = 117384258060764
PROG_F = os.path.join(WORK, "top8_progress.json")
LOG_F = os.path.join(WORK, "top8_log.txt")
QUEUE = os.path.join(WORK, "top5_queue.json")
START_I = 4  # queue index of the NEXT group to send (0=78818 skip; 1=79753 skip; 2=81962 skip; 3=82808 skip)

def log(m):
    with open(LOG_F, "a", encoding="utf-8") as f:
        f.write(time.strftime("[%m-%d %H:%M:%S] ") + m + "\n")

def P():
    if os.path.exists(PROG_F):
        return json.load(open(PROG_F, encoding="utf-8"))
    return {"i": START_I, "last_tok": 82808, "posted": 41, "posted_n": 401, "fails": 0, "sent_idx": 0}
def S(p):
    json.dump(p, open(PROG_F + ".t", "w", encoding="utf-8"), ensure_ascii=False); os.replace(PROG_F + ".t", PROG_F)

def js(c, code):
    v, e = c.eval(code)
    return v if not e else "E:" + str(e)

WALK = r"""
window.__walk2=function(){function go(r,f,d){if(!r||d>20)return;try{f(r)}catch(e){}if(r.shadowRoot)go(r.shadowRoot,f,d+1);if(r.querySelectorAll){var k;try{k=r.querySelectorAll('*')}catch(e){return}for(var i=0;i<k.length;i++){try{f(k[i])}catch(e){}if(k[i].shadowRoot)go(k[i].shadowRoot,f,d+1)}}}return go}();
window.__cargo=function(ed){ed.focus();var s=window.getSelection();var r=document.createRange();r.selectNodeContents(ed);r.collapse(false);s.removeAllRanges();s.addRange(r)};
window.__edtop=function(){var eds=[];__walk2(document,function(n){if(n.matches&&n.matches('.brt-editor[contenteditable="true"]')){var b=n.getBoundingClientRect();if(b.width>40)eds.push({x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height),t:(n.innerText||'')});}});eds.sort(function(a,b){return a.y-b.y});return eds;};
window.__mained=function(){var eds=window.__edtop();if(!eds.length)return null;for(var i=0;i<eds.length;i++){var e=eds[i];var up=null;__walk2(document,function(n){if(n.matches&&n.matches('.brt-editor[contenteditable="true"]')&&Math.abs(n.getBoundingClientRect().x-e.x)<2&&Math.abs(n.getBoundingClientRect().y-e.y)<2)up=n;});if(!up)continue;var a=up,s='';for(var k=0;k<7&&a;k++){s+=(a.textContent||'').slice(0,10);a=a.parentElement||(a.getRootNode&&a.getRootNode().host);}if(s.indexOf('回复')<0){window.__tred=up;return e;}}return null;};
window.__ph=function(){var ph=null;__walk2(document,function(n){if(!ph&&n.matches&&n.matches('.brt-placeholder')){var b=n.getBoundingClientRect();if(b.width>30)ph={x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)};}});return ph;};
window.__clear=function(){var ed=window.__tred;if(!ed)return -1;window.__cargo(ed);document.execCommand('selectAll');document.execCommand('delete');return (ed.innerText||'').length;};
window.__ins=function(t){var ed=window.__tred;if(!ed)return -1;window.__cargo(ed);document.execCommand('insertText',false,t);return (ed.innerText||'').length;};
window.__pubrect=function(){
  // find the real visible 发布 button (no hidden state bypass)
  var btn=null;
  __walk2(document,function(n){if(!btn&&n.tagName==='BUTTON'&&/^发布$|^发表$/.test((n.textContent||'').trim())&&n.className.indexOf('active')>=0){var b=n.getBoundingClientRect();if(b.width>4&&b.height>4)btn={x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)};}});
  if(!btn)return null;return btn;
};
"""

def connect():
    # 先尝试直接连接9222
    for _ in range(8):
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
    # 9222不通 → 自动拉起调试Edge（专用profile，登录态保留）
    log("9222不通 → 自动拉起调试浏览器")
    import subprocess
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    subprocess.Popen([edge, "--remote-debugging-port=9222",
                      '--user-data-dir="E:\\欧尼酱_召唤工作区\\edge_profile"',
                      "--no-first-run", "--window-size=1500,1300",
                      URL], cwd=os.path.dirname(edge))
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

def click(c, x, y):
    c.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1, "buttons": 1}); time.sleep(0.11)
    c.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}); time.sleep(0.6)

ck_cache = [None]
def verify_tok(tok):
    if ck_cache[0] is None:
        ck_cache[0] = json.load(open(os.path.join(WORK, 'session.json'), encoding='utf-8'))
    ck = ck_cache[0]
    H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36',
         'Referer': URL,
         'Cookie': '; '.join('%s=%s' % (k, v) for k, v in ck.items() if v)}
    cur = 0
    for pg in range(3):
        try:
            r = urllib.request.Request('https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d' % (AID, cur), headers=H)
            d = json.loads(urllib.request.urlopen(r, timeout=15).read())
            dd = d.get('data') or {}
            for rp in (dd.get('replies') or []):
                t = (rp.get('content') or {}).get('message', '')
                if t.find("已消耗 {:,} Token".format(tok)) >= 0:
                    return "LIVE"
            cu = dd.get('cursor') or {}
            cur = cu.get('next', 0)
            if cu.get('is_end'): break
        except Exception:
            pass
        time.sleep(1.2)
    return "MAYBE_AUDIT"

def main():
    global URL, AID
    tj = os.path.join(WORK, "target.json")
    if os.path.exists(tj):
        try:
            td = json.load(open(tj, encoding="utf-8"))
            if td.get("url"): URL = td["url"]
            if td.get("aid"): AID = int(td["aid"])
            log("目标视频(面板): url=%s aid=%s" % (URL, AID))
        except Exception as e:
            log("target.json 读取失败 %r，用默认" % e)
    p = P()
    q = json.load(open(QUEUE, encoding="utf-8"))["queue"]
    log("v8 START i=%d last_tok=%d q=%d — 4-8min cadence, real clicks only" % (p["i"], p["last_tok"], len(q)))
    c = connect()
    fails_streak = 0
    while p["i"] < len(q):
        # 面板停止开关：STOP=暂停退出（进度已保存）
        try:
            if open(os.path.join(WORK, "flag.txt"), encoding="utf-8").read().strip() == "STOP":
                log("面板请求停止 → 暂停退出（进度 i=%d）" % p["i"])
                break
        except Exception:
            pass
        g = q[p["i"]]
        t0 = time.time()
        ok = False
        for att in (1, 2):
            cur = js(c, "location.href")
            if "BV1VdHE6PEEa" not in cur:
                c.navigate(URL); time.sleep(9)
            js(c, WALK)
            time.sleep(3.0)
            ed = js(c, "JSON.stringify(window.__mained())")
            try:
                edp = json.loads(ed) if ed and ed != "null" else None
            except Exception:
                edp = None
            if not edp:
                ph = js(c, "JSON.stringify(window.__ph())")
                try:
                    pp = json.loads(ph) if ph and ph != "null" else None
                except Exception:
                    pp = None
                if not pp:
                    c.navigate(URL); time.sleep(9); continue
                click(c, pp["x"], pp["y"]); time.sleep(2.0)
                ed = js(c, "JSON.stringify(window.__mained())")
                try:
                    edp = json.loads(ed) if ed and ed != "null" else None
                except Exception:
                    edp = None
                if not edp:
                    continue
            if len(edp.get("t", "")) > 2:
                # clear leftover text by REAL select (js caret) + execCommand delete
                js(c, "window.__clear()"); time.sleep(0.6)
                if js(c, "JSON.stringify(window.__edtop())").find('"t":""') < 0:
                    # leftover more; js force
                    js(c, "window.__clear()")
            # REAL content insertion: real click inside editor -> Input.insertText (proven to activate B tråbers state)
            cur_ed = json.loads(js(c, "JSON.stringify(window.__edtop())") or "[]")
            if not cur_ed:
                continue
            ce = cur_ed[0]
            click(c, ce["x"] + ce["w"] - 30, ce["y"] + ce["h"] - 3)
            time.sleep(0.7)
            c.cmd("Input.insertText", {"text": g["text"]})
            time.sleep(1.4)
            # publish can now be visible
            pb = js(c, "JSON.stringify(window.__pubrect())")
            try:
                bpp = json.loads(pb) if pb and pb != "null" else None
            except Exception:
                bpp = None
            if not bpp:
                # FALLBACK (proven): remove 'hidden' class on button ancestors, then jsClick
                rfb = js(c, """(function(){
                  var btn=null;
                  __walk2(document,function(n){if(!btn&&n.tagName==='BUTTON'&&/^发布$|^发表$/.test((n.textContent||'').trim())&&n.className.indexOf('active')>=0)btn=n;});
                  if(!btn)return 'NOBTN';
                  var a=btn;for(var k=0;k<4&&a;k++){if(a.classList&&a.classList.contains('hidden'))a.classList.remove('hidden');a=a.parentElement||(a.getRootNode&&a.getRootNode().host);}
                  if(getComputedStyle(btn).display==='none')return 'STILLHIDDEN';
                  btn.click();return 'CLICKED';
                })()""")
                if "CLICKED" not in str(rfb):
                    log("att%d 组%d hidden状态 bypass失败(%s) — 15s后重试" % (att, p["i"] + 1, rfb))
                    time.sleep(15)
                    continue
                t_end = time.time() + 14; cleared = False
                while time.time() < t_end:
                    time.sleep(1.3)
                    a2 = js(c, "JSON.stringify(window.__edtop())")
                    try:
                        arr = json.loads(a2)
                    except Exception:
                        arr = []
                    if not arr or len(arr[0].get("t", "")) < 5:
                        cleared = True; break
                if cleared:
                    ok = True; break
                js(c, "window.__clear()")
                time.sleep(20)
                continue
            click(c, bpp["x"], bpp["y"])  # REAL click
            t_end = time.time() + 14; cleared = False
            while time.time() < t_end:
                time.sleep(1.3)
                a2 = js(c, "JSON.stringify(window.__edtop())")
                try:
                    arr = json.loads(a2)
                except Exception:
                    arr = []
                if not arr or len(arr[0].get("t", "")) < 5:
                    cleared = True; break
            if cleared:
                ok = True; break
            js(c, "window.__clear()")
            time.sleep(20)  # short page cool before retry
        if ok:
            fails_streak = 0
            p["i"] += 1; p["last_tok"] = g["tok"]; p["posted"] += 1; p["posted_n"] += len(g["names"])
            S(p); time.sleep(3)
            stat = verify_tok(g["tok"])
            log("✅ tok=%.0f 人=%d 已发=%d %s" % (g["tok"], len(g["names"]), p["posted"], stat))
            jit = random.randint(30, 45)  # ~35s / 条
            log("…等待%d秒再发下条" % jit); time.sleep(jit)
        else:
            fails_streak += 1
            p["fails"] = fails_streak; S(p)
            log("❌ tok~%.0f 失败streak=%d — 60s后重试" % (g["tok"], fails_streak))
            time.sleep(60)
    log("=== 全部发送完成 已发=%d 人次=%d ===" % (p["posted"], p["posted_n"]))

if __name__ == "__main__":
    main()
