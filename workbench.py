# -*- coding: utf-8 -*-
"""召唤&艾特 工作台 v3（多仓库版）：
- 仓库栏：可"＋新建仓库"（每个仓库=独立标签集+独立名单队列+独立目标视频），切换仓库自动换数据
- 顶部：当前仓库的探测标签页（多标签可增删）
- 左：召唤工具箱（自定义话语/黄色艾特区 + 人名仓库：未艾特|已艾特双栏）
- 右：艾特工具箱（视频链接可自定义+绑定 / 发送参数（间隔/每条人数）/ 启停控制 / 日志）
- 中间竖线分隔，左右grid等权50/50
- 界面自适应：长文本标签自动折行、输入框随窗口伸缩、控件两行布局——任意窗口缩放文字不消失
- 登录态：左上角账号模块（首次启动引导扫码登录B站网页版二维码，支持多账号添加/切换/退出）——
  评论一律使用「当前登录账号」自己的凭据，不依赖作者凭据
- 系统监控：右上角单一区域实时显示 CPU占用、真实运存占用、GPU占用（硬件实测读数，每2秒刷新）
- 目标页面一键打开：🌐按钮/绑定成功后在艾特机器人专用的调试浏览器里自动弹出目标视频页"""
import io, sys, os, json, time, re, random, hashlib, urllib.parse, urllib.request
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading, queue as thq

# pythonw（无控制台）下 sys.stdout 为 None，必须跳过包装，否则GUI无法启动
if sys.stdout and getattr(sys.stdout, "buffer", None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
# 可移植：工作目录=程序所在目录（本机即召唤工作区；别人克隆仓库后就是仓库文件夹）
WORK = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SELF_MID = 3706929960454980
TEMPLATE_F = os.path.join(WORK, "custom_template.txt")
REPOS_F = os.path.join(WORK, "repos.json")
AT_MARK = "【艾特区】"
DEFAULT_TPL = "⚡大型召唤魔法发动中⚡ 已消耗 {token} Token 【艾特区】 如果你被打扰了，那么很抱歉，请在本条评论下方回复111，以后将不会再打扰您。 ⚠️这是一段自动运行的脚本。它从B站公开的评论区里收集了同好观众名单，自动逐条发布召唤评论（每条艾特10人、间隔可调）。当脚本检测到有人回复\u201c111\u201d，会立刻把这位用户写入永久黑名单。全程无人工参与——打扰到您，是脚本设置者的责任，再次抱歉。"
DEFAULT_VIDEO = "https://www.bilibili.com/video/BV1VdHE6PEEa"
DEFAULT_AID = 117384258060764

if not os.path.exists(TEMPLATE_F):
    open(TEMPLATE_F, "w", encoding="utf-8").write(DEFAULT_TPL)

# ---------- 仓库存储 ----------
def load_repos():
    if os.path.exists(REPOS_F):
        return json.load(open(REPOS_F, encoding="utf-8"))
    # 迁移：旧tags_config.json成为主仓库
    tags = []
    try:
        tags = json.load(open(os.path.join(WORK, "tags_config.json"), encoding="utf-8"))["tags"]
    except Exception:
        tags = [{"name": "别当欧尼酱了", "maxv": 30, "rng": "近90天"}]
    repos = {"repos": [{"id": 1, "name": "主仓库", "video": DEFAULT_VIDEO, "aid": DEFAULT_AID, "tags": tags}], "active": 1}
    json.dump(repos, open(REPOS_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return repos

def repo_queue_f(rid):
    return os.path.join(WORK, "repo%d_queue.json" % rid)
def repo_prog_f(rid):
    return os.path.join(WORK, "repo%d_progress.json" % rid)
BLANK_QUEUE = {"queue": []}
BLANK_PROG = {"i": 0, "last_tok": 0, "posted": 0, "posted_n": 0, "fails": 0}

sess = {}
try:
    sess = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
except Exception:
    sess = {}   # 新用户首启无session.json：不崩，走扫码登录引导
S = None
try:
    import requests
    S = requests.Session()
    S.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com",
                      "Accept": "application/json", "Accept-Language": "zh-CN,zh;q=0.9"})
    for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
        if sess.get(k):
            S.cookies.set(k, sess[k])
except Exception:
    S = None

MIXIN = ""
def refresh_wbi():
    """按当前登录态刷新wbi签名密钥（登录/切换账号后可重算）"""
    try:
        if S:
            r = S.get("https://api.bilibili.com/x/web-interface/nav", timeout=15).json()
            ik = r["data"]["wbi_img"]["img_url"].rsplit("/", 1)[1].split(".")[0]
            sk = r["data"]["wbi_img"]["sub_url"].rsplit("/", 1)[1].split(".")[0]
            MIX = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,37,12,13,25,40,34,55,48,17,54,51,36,0,39,6,30,44,52,1,57,56,26,41,11,22,4,24,20,21,7,38,16,59]
            return "".join((ik + sk)[i] for i in MIX)[:32]
    except Exception:
        pass
    return ""
MIXIN = refresh_wbi()

# ---------- 登录态：多账号存储（扫码登录/切换/退出，凭据只存本机） ----------
try:
    import qrcode
except Exception:
    qrcode = None
ACCOUNTS_F = os.path.join(WORK, "accounts.json")

def load_accounts():
    try:
        d = json.load(open(ACCOUNTS_F, encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("accounts"), list):
            return d
    except Exception:
        pass
    return {"active": None, "accounts": []}

def save_accounts(doc):
    json.dump(doc, open(ACCOUNTS_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def account_creds(acc):
    """取账号凭据：优先返回存档过的全套cookie（含风控辅助），老账号只有4核心也能用"""
    keys = ("SESSDATA", "bili_jct", "DedeUserID", "buvid3", "ac_time_value", "DedeUserID__ckMd5", "sid")
    out = {k: acc.get(k) or "" for k in keys if acc.get(k)}
    if not out.get("SESSDATA"):
        return {"SESSDATA": acc.get("SESSDATA") or "", "bili_jct": acc.get("bili_jct") or "",
                "DedeUserID": acc.get("DedeUserID") or "", "buvid3": acc.get("buvid3") or ""}
    return out

def apply_session(creds):
    """登录/切换的统一落点：更新全局sess与requests cookies，并写session.json（发送引擎读的标准槽位）"""
    global MIXIN
    sess.clear()
    sess.update(creds)
    json.dump(creds, open(os.path.join(WORK, "session.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if S:
        try:
            S.cookies.clear()
            for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
                if creds.get(k):
                    S.cookies.set(k, creds[k])
        except Exception:
            pass
    MIXIN = refresh_wbi()

def fetch_nav_info(creds=None):
    """调nav接口取当前登录者 (mid, uname)；creds=None时用全局会话S"""
    try:
        if creds:
            import requests
            t = requests.Session()
            t.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
            for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
                if creds.get(k):
                    t.cookies.set(k, creds[k])
            j = t.get("https://api.bilibili.com/x/web-interface/nav", timeout=15).json()
        else:
            if not S:
                return None, None
            j = S.get("https://api.bilibili.com/x/web-interface/nav", timeout=15).json()
        d = j.get("data") or {}
        if d.get("isLogin"):
            return str(d.get("mid")), d.get("uname") or "?"
    except Exception:
        pass
    return None, None

def server_logout(creds):
    """尽力让B站服务端登录态失效（失败不影响本地移除）"""
    try:
        import requests
        t = requests.Session()
        t.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
            if creds.get(k):
                t.cookies.set(k, creds[k])
        t.get("https://passport.bilibili.com/x/passport-login/web/login/exit",
              params={"csrf": creds.get("bili_jct", "")}, timeout=15)
    except Exception:
        pass

# ---------- UP主删评卫士（召唤评论发布后延时删除，压缩风控曝光窗口） ----------
def deleter_del_comment(creds, oid, rpid):
    """以UP主身份删除其视频下指定评论（UP主对自己视频的评论有删除权限）"""
    try:
        import requests
        t = requests.Session()
        t.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
            if creds.get(k):
                t.cookies.set(k, creds[k])
        r = t.post("https://api.bilibili.com/x/v2/reply/del",
                   data={"oid": int(oid), "type": 1, "rpid": int(rpid), "csrf": creds.get("bili_jct", "")},
                   timeout=15).json()
        return r.get("code") == 0, r.get("code"), r.get("message") or ""
    except Exception as e:
        return False, -1, repr(e)

def deleter_scan_comments(creds, oid, pages=1):
    """以UP主身份拉取视频最新评论（时间序优先，失败回退热度序），返回评论列表"""
    try:
        import requests
        t = requests.Session()
        t.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
            if creds.get(k):
                t.cookies.set(k, creds[k])
        cur = 0
        out = []
        for pg in range(pages):
            j = {}
            for mode in (2, 3):
                j = t.get("https://api.bilibili.com/x/v2/reply/main",
                          params={"type": 1, "oid": int(oid), "mode": mode, "next": cur}, timeout=15).json()
                if j.get("code") == 0:
                    break
            d = j.get("data") or {}
            reps = (d.get("replies") or []) + (d.get("top_replies") or [])
            if not reps:
                break
            out.extend(reps)
            cu = d.get("cursor") or {}
            cur = cu.get("next", 0)
            if cu.get("is_end"):
                break
        return out
    except Exception:
        return []

def try_migrate_session(doc):
    """旧版只有session.json没有账号库时：把现有登录导入为账号1（顺便取uname/mid）"""
    if doc["accounts"] or not sess.get("SESSDATA"):
        return doc
    mid, uname = fetch_nav_info()
    if mid:
        acc = account_creds(dict(sess))
        acc.update({"mid": mid, "uname": uname, "saved_at": int(time.time())})
        doc["accounts"].append(acc)
        doc["active"] = mid
        save_accounts(doc)
    return doc

ACCOUNTS = try_migrate_session(load_accounts())

def active_uname(doc=None):
    doc = doc if doc is not None else ACCOUNTS
    for a in doc["accounts"]:
        if str(a.get("mid")) == str(doc.get("active")):
            return a.get("uname") or "?"
    return None

def wbi_sign(params):
    p = {k: "".join(ch for ch in str(v) if ch not in set("!'()*")) for k, v in params.items()}
    p["wts"] = int(time.time())
    p = dict(sorted(p.items()))
    p["w_rid"] = hashlib.md5((urllib.parse.urlencode(p) + MIXIN).encode()).hexdigest()
    return p

def api_get(url, params=None, retries=3):
    for a in range(retries):
        try:
            j = S.get(url, params=params, timeout=20).json()
            if j.get("code", -1) in (-412, -352):
                time.sleep(60); continue
            return j
        except Exception:
            time.sleep(4 + a * 6)
    return None

def fetch_aid(bvid):
    try:
        j = api_get("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})
        if j and j.get("code") == 0:
            return j["data"]["aid"], j["data"]["title"]
    except Exception:
        pass
    return None, None

def crawl_video_users(aid, pages_max=6):
    out = {}
    cur = 0
    for pg in range(pages_max):
        j = api_get("https://api.bilibili.com/x/v2/reply/main", {"type": 1, "oid": aid, "mode": 3, "next": cur})
        if not j or j.get("code") != 0:
            break
        d = j.get("data") or {}
        reps = (d.get("replies") or []) + (d.get("top_replies") or [])
        if not reps:
            break
        for r in reps:
            m = r.get("member") or {}
            mid = str(m.get("mid") or "")
            if mid:
                out[mid] = {"uname": m.get("uname", ""), "ctime": r.get("ctime", 0)}
            for sub in (r.get("replies") or []):
                m2 = sub.get("member") or {}
                mid2 = str(m2.get("mid") or "")
                if mid2 and mid2 not in out:
                    out[mid2] = {"uname": m2.get("uname", ""), "ctime": sub.get("ctime", 0)}
        cu = d.get("cursor") or {}
        cur = cu.get("next", 0)
        if cu.get("is_end"):
            break
        time.sleep(0.6)
    return out

def render_template(tpl, tok, names):
    ats = " ".join("@" + n for n in names)
    t = tpl.replace(AT_MARK, ats).replace("{token}", "{:,}".format(tok))
    if AT_MARK not in tpl and ats not in t:
        t = t.rstrip() + " " + ats
    return t

# ---------- 目标页面：在艾特机器人专用调试浏览器中打开 ----------
def open_engine_page(url):
    """在发送引擎同款调试浏览器（9222端口+专用profile）里打开页面：
    - 浏览器已在运行且有B站页 → 该页直接导航到目标并置前（机器人运行中URL一致时只置前、不打扰发送）
    - 其余情况 → 按引擎同款命令拉起调试浏览器并打开该页"""
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=4) as r:
            tg = json.loads(r.read().decode())
        cand = [t for t in tg if t.get("type") == "page" and "bilibili.com" in (t.get("url") or "")]
        tab = next((t for t in cand if "/video/" in (t.get("url") or "")), None) or (cand[0] if cand else None)
        if tab is not None:
            try:
                from cdp import CDP
                c = CDP(tab["webSocketDebuggerUrl"])
                if not (m and m.group(1) in (tab.get("url") or "")):
                    c.navigate(url)   # 页面与目标不一致才导航（机器人正在用同页时不打断）
                c.cmd("Page.bringToFront")
                threading.Thread(target=lambda: _foreground_engine_browser(4.0), daemon=True).start()
                return True
            except Exception:
                pass
    except Exception:
        pass
    try:
        import subprocess
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge):
            edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge):
            return False
        # 注意：user-data-dir参数绝不能内嵌引号（Popen会把\"传给Chromium→路径解析失败
        # →回退默认配置目录→页面被转发到普通Edge，调试端口永远起不来）
        subprocess.Popen([edge, "--remote-debugging-port=9222",
                          "--user-data-dir=" + os.path.join(WORK, "edge_profile"),
                          "--no-first-run", "--window-size=1500,1300", url],
                         cwd=os.path.dirname(edge))
        threading.Thread(target=lambda: _foreground_engine_browser(12.0), daemon=True).start()
        return True
    except Exception:
        return False

def _foreground_engine_browser(wait_win=8.0):
    """把调试浏览器主窗口拉到最前（恢复最小化+SetForegroundWindow），
    冷启动时轮询等待窗口出现。工作台已取消置顶，页面才能真正"弹"到眼前。"""
    try:
        import subprocess, ctypes, ctypes.wintypes
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object {$_.CommandLine -match 'edge_profile'}).ProcessId"],
            timeout=40, creationflags=_NOWIN).decode().split()
        pids = {int(p) for p in out if p.strip().isdigit()}
        if not pids:
            return
        user32 = ctypes.windll.user32
        deadline = time.time() + wait_win
        while time.time() < deadline:
            res = []
            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            def cb(h, l):
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value in pids and user32.IsWindowVisible(h):
                    cls = ctypes.create_unicode_buffer(64)
                    user32.GetClassNameW(h, cls, 64)
                    if cls.value == "Chrome_WidgetWin_1":
                        res.append(h)
                return True
            user32.EnumWindows(cb, 0)
            if res:
                h = res[0]
                if user32.IsIconic(h):
                    user32.ShowWindow(h, 9)     # SW_RESTORE：最小化时恢复
                user32.SetForegroundWindow(h)
                return
            time.sleep(1.0)
    except Exception:
        pass

# ---------- 系统占用监控（右上角单一区域：CPU/运存/GPU） ----------
def gpu_sample():
    """读nvidia-smi：返回(util%, mem_used_mb)，失败返回None"""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            timeout=8, stderr=subprocess.DEVNULL, creationflags=_NOWIN).decode().strip()
        u, m = [x.strip() for x in out.split(",")]
        return int(u), int(m)
    except Exception:
        return None

def ram_usage():
    """真实运存：返回(占用%, 总字节, 可用字节)；纯ctypes直读系统，无第三方依赖"""
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX(); st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.dwMemoryLoad, st.ullTotalPhys, st.ullAvailPhys
    except Exception:
        return None

_sys_prev = [None]
def cpu_usage():
    """全机CPU占用%（GetSystemTimes差值法，纯ctypes）；首次调用返回None"""
    try:
        import ctypes
        class FILETIME(ctypes.Structure):
            _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        def val(ft):
            return (ft.hi << 32) | ft.lo
        i, k, u = val(idle), val(kernel), val(user)
        prev = _sys_prev[0]
        _sys_prev[0] = (i, k, u)
        if prev is None:
            return None
        di, dk, du = i - prev[0], k - prev[1], u - prev[2]
        tot = dk + du
        if tot <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (1.0 - di / tot)))
    except Exception:
        return None

# ---------- 窗口尺寸记忆（启动恢复上次大小，不再强制最大化） ----------
UI_F = os.path.join(WORK, "workbench_ui.json")

def load_ui_size():
    try:
        d = json.load(open(UI_F, encoding="utf-8"))
        w, h = int(d["w"]), int(d["h"])
        if 920 <= w <= 3200 and 640 <= h <= 2000:
            return w, h
    except Exception:
        pass
    return 1280, 760

def save_ui_size(w, h):
    try:
        json.dump({"w": int(w), "h": int(h)}, open(UI_F, "w", encoding="utf-8"))
    except Exception:
        pass

# 子进程统一加"不创建窗口"标志：从pythonw（无控制台）启动的程序调任何控制台子进程，
# Windows都会分配新控制台黑窗，跑完即关——正是"后台不断闪黑窗"的来源
_NOWIN = 0x08000000   # subprocess.CREATE_NO_WINDOW

class Workbench:
    def __init__(self, root):
        self.root = root
        root.title("召唤&艾特 工作台")
        # 界面自适应：长文本标签随宽度自动折行、控件随窗口伸缩；启动恢复上次窗口尺寸（居中显示）
        root.minsize(940, 760)
        w, h = load_ui_size()
        try:
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry("%dx%d+%d+%d" % (w, h, max(10, (sw - w) // 2), max(10, (sh - h) // 4)))
        except Exception:
            pass
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.attributes("-topmost", True)
        self.q = thq.Queue()
        self.repos_doc = load_repos()
        if not any(r["id"] == self.repos_doc.get("active") for r in self.repos_doc["repos"]):
            self.repos_doc["active"] = self.repos_doc["repos"][0]["id"]
        self.active_id = self.repos_doc["active"]

        # ===== 仓库栏（最左=登录态模块） =====
        repobar = ttk.Frame(root); repobar.pack(fill="x", padx=8, pady=(8, 2))
        self.login_var = tk.StringVar(value="")
        ttk.Button(repobar, textvariable=self.login_var, command=self.open_account_mgr).pack(side="left", padx=(0, 10))
        self.refresh_login_btn()
        ttk.Label(repobar, text="📦 仓库：", font=("微软雅黑", 11, "bold")).pack(side="left")
        self.repo_box = ttk.Combobox(repobar, state="readonly", width=16)
        self.repo_box.pack(side="left", padx=4)
        self.repo_box.bind("<<ComboboxSelected>>", self.on_repo_switch)
        ttk.Button(repobar, text="＋ 新建仓库", command=self.new_repo).pack(side="left", padx=8)
        ttk.Button(repobar, text="🗑️ 删除仓库", command=self.del_repo).pack(side="left", padx=4)
        self.sys_var = tk.StringVar(value="🖥️ CPU --｜运存 --｜GPU --")
        # 固定宽度+右对齐：数字刷新时标签占宽恒定，顶栏布局纹丝不动（界面绝不"自己动"）
        self.sys_label = tk.Label(repobar, textvariable=self.sys_var, font=("微软雅黑", 9, "bold"), fg="#2d3436",
                                  width=60, anchor="e")
        self.sys_label.pack(side="right", padx=6)
        self.repo_info = tk.StringVar(value="")
        self.repo_info_lbl = self.wrap_label(repobar, textvariable=self.repo_info, font=("微软雅黑", 9), foreground="#0984e3", anchor="w")
        self.repo_info_lbl.pack(side="left", fill="x", expand=True, padx=10)

        # ===== 顶部：标签页（当前仓库的） =====
        tagbar = ttk.Frame(root); tagbar.pack(fill="x", padx=8, pady=(2, 0))
        ttk.Label(tagbar, text="🏷️ 标签页：", font=("微软雅黑", 10, "bold")).pack(side="left")
        self.tab_note = ttk.Notebook(root)
        self.tab_note.pack(fill="x", padx=8, pady=(2, 4))
        self.tab_logs = {}
        self.tab_vars = {}
        self.tab_note.bind("<<NotebookTabChanged>>", self._on_tab_change)
        ttk.Button(tagbar, text="🗑️ 删除当前标签", command=self.del_tag).pack(side="right", padx=4)
        self.rebuild_tag_tabs()

        # ===== 主体：左右50/50 + 中间竖线 =====
        main = ttk.Frame(root); main.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.LabelFrame(main, text=" ◀ 召唤工具箱 ")
        sep = tk.Frame(main, bg="#333", width=3)
        right = ttk.LabelFrame(main, text=" 艾特工具箱 ▶ ")
        main.grid_columnconfigure(0, weight=1, uniform="half")
        main.grid_columnconfigure(2, weight=1, uniform="half")
        main.grid_rowconfigure(0, weight=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        sep.grid(row=0, column=1, sticky="ns", pady=6)
        right.grid(row=0, column=2, sticky="nsew", padx=(3, 0))

        self.build_left(left)
        self.build_right(right)
        self.refresh_repo_box()
        self.pump()
        # 新用户首启引导：无任何登录凭据时自动弹扫码登录
        self.root.after(800, self._maybe_first_run)
        # 系统占用监控线程：每2秒刷新右上角 CPU/运存/GPU 显示
        threading.Thread(target=self._sys_monitor, daemon=True).start()
        # 登录态健康检查：服务端验证凭据有效性，失效立刻在按钮上显示警告
        threading.Thread(target=self._login_health, daemon=True).start()

    # ---------- 自适应：长文本标签注册自动换行（宽度不够时折行显示，永不消失） ----------
    def _on_close(self):
        # 关闭时记住窗口尺寸（最大化状态下关闭则保留上次normal尺寸），下次启动按此大小打开
        try:
            if self.root.state() != "zoomed":
                save_ui_size(self.root.winfo_width(), self.root.winfo_height())
        except Exception:
            pass
        self.root.destroy()

    def wrap_label(self, parent, pad=10, **kw):
        lb = ttk.Label(parent, **kw)
        def on_cfg(e=None):
            try:
                w = lb.winfo_width()
            except Exception:
                return
            if w > 60:
                try:
                    lb.configure(wraplength=max(60, w - pad))
                except Exception:
                    pass
        lb.bind("<Configure>", on_cfg, add="+")
        return lb

    # ---------- 仓库 ----------
    def active_repo(self):
        return next(r for r in self.repos_doc["repos"] if r["id"] == self.active_id)

    def save_repos(self):
        json.dump(self.repos_doc, open(REPOS_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def refresh_repo_box(self):
        names = ["%s（视频%d）" % (r["name"], r["id"]) for r in self.repos_doc["repos"]]
        self.repo_box["values"] = names
        for idx, r in enumerate(self.repos_doc["repos"]):
            if r["id"] == self.active_id:
                self.repo_box.current(idx)
        r = self.active_repo()
        n_q = len(json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]) if self.active_id == 1 else len(json.load(open(repo_queue_f(self.active_id), encoding="utf-8"))["queue"])
        self.repo_info.set("目标视频：%s｜队列%d组" % (r["video"][:44], n_q))

    def on_repo_switch(self, e=None):
        idx = self.repo_box.current()
        if idx < 0 or idx >= len(self.repos_doc["repos"]):
            return
        new_id = self.repos_doc["repos"][idx]["id"]
        if new_id == self.active_id:
            return
        # 换出：当前标准文件 → 旧仓库文件
        old = self.active_id
        json.dump(json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8")), open(repo_queue_f(old), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8")), open(repo_prog_f(old), "w", encoding="utf-8"), ensure_ascii=False)
        # 换入：新仓库文件 → 标准文件
        self.active_id = new_id
        self.repos_doc["active"] = new_id
        self.save_repos()
        qdoc = json.load(open(repo_queue_f(new_id), encoding="utf-8")) if os.path.exists(repo_queue_f(new_id)) else BLANK_QUEUE
        prog = json.load(open(repo_prog_f(new_id), encoding="utf-8")) if os.path.exists(repo_prog_f(new_id)) else BLANK_PROG
        json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(prog, open(os.path.join(WORK, "top8_progress.json"), "w", encoding="utf-8"), ensure_ascii=False)
        r = self.active_repo()
        json.dump({"url": r["video"], "aid": r["aid"]}, open(os.path.join(WORK, "target.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.rebuild_tag_tabs()
        self.load_repo()
        self.refresh_stats()
        self.refresh_repo_box()
        self.rlog.insert("end", "🔁 已切换到仓库【%s】——请重新点【▶开始发送】生效\n" % r["name"])
        self.rlog.see("end")

    def new_repo(self):
        win = tk.Toplevel(self.root); win.title("新建仓库"); win.transient(self.root)
        win.geometry("520x220")
        tk.Label(win, text="仓库名：", font=("微软雅黑", 10)).pack(pady=(10, 2))
        name_e = ttk.Entry(win, width=30); name_e.pack()
        tk.Label(win, text="目标视频链接（BV开头）：", font=("微软雅黑", 10)).pack(pady=(8, 2))
        vid_e = ttk.Entry(win, width=48); vid_e.insert(0, DEFAULT_VIDEO); vid_e.pack()
        hint = tk.StringVar(value="")
        tk.Label(win, textvariable=hint, font=("微软雅黑", 9), fg="#e67e22").pack(pady=4)
        def ok():
            name = name_e.get().strip() or "新仓库%d" % (len(self.repos_doc["repos"]) + 1)
            m = re.search(r"(BV[0-9A-Za-z]{10})", vid_e.get().strip())
            if not m:
                hint.set("✗ 链接里没找到BV号"); return
            bvid = m.group(1)
            aid, title = fetch_aid(bvid)
            if not aid:
                hint.set("✗ 视频信息获取失败（稍后再试）"); return
            rid = max(r["id"] for r in self.repos_doc["repos"]) + 1
            self.repos_doc["repos"].append({"id": rid, "name": name,
                                            "video": "https://www.bilibili.com/video/" + bvid, "aid": aid,
                                            "tags": []})
            self.save_repos()
            json.dump(BLANK_QUEUE, open(repo_queue_f(rid), "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(BLANK_PROG, open(repo_prog_f(rid), "w", encoding="utf-8"), ensure_ascii=False)
            win.destroy()
            # ★关键：先把当前仓库的数据从标准槽位导出到它的仓库文件！
            # 否则下面写入新仓库空队列会把当前仓库的全部数据覆盖丢失（2026-10-06主仓库5306组就是这么丢的）
            old = self.active_id
            try:
                json.dump(json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8")),
                          open(repo_queue_f(old), "w", encoding="utf-8"), ensure_ascii=False)
                json.dump(json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8")),
                          open(repo_prog_f(old), "w", encoding="utf-8"), ensure_ascii=False)
            except Exception:
                pass
            # 直接切换到新仓库
            self.repo_box.set("")
            self.active_id = rid
            self.repos_doc["active"] = rid
            self.save_repos()
            qdoc = BLANK_QUEUE; prog = BLANK_PROG
            json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(prog, open(os.path.join(WORK, "top8_progress.json"), "w", encoding="utf-8"), ensure_ascii=False)
            json.dump({"url": "https://www.bilibili.com/video/" + bvid, "aid": aid},
                      open(os.path.join(WORK, "target.json"), "w", encoding="utf-8"), ensure_ascii=False)
            self.rebuild_tag_tabs()
            self.load_repo(); self.refresh_stats(); self.refresh_repo_box()
            self.rlog.insert("end", "📦 新仓库【%s】已创建并激活《%s》aid=%s\n（空队列：请去标签页探测或直接点开始发送）\n" % (name, (title or "")[:20], aid))
            self.rlog.see("end")
        ttk.Button(win, text="✅ 创建并切换", command=ok).pack(pady=8)
        win.bind("<Return>", lambda e: ok())

    def del_repo(self):
        if len(self.repos_doc["repos"]) <= 1:
            self.rlog.insert("end", "至少保留1个仓库\n"); return
        r = self.active_repo()
        self.repos_doc["repos"] = [x for x in self.repos_doc["repos"] if x["id"] != r["id"]]
        if self.repos_doc["repos"]:
            self.repos_doc["active"] = self.repos_doc["repos"][0]["id"]
        self.save_repos()
        for f in (repo_queue_f(r["id"]), repo_prog_f(r["id"])):
            try: os.remove(f)
            except Exception: pass
        # 切到第一个仓库
        first = self.repos_doc["repos"][0]
        self.active_id = first["id"]
        qdoc = json.load(open(repo_queue_f(first["id"]), encoding="utf-8")) if os.path.exists(repo_queue_f(first["id"])) else BLANK_QUEUE
        prog = json.load(open(repo_prog_f(first["id"]), encoding="utf-8")) if os.path.exists(repo_prog_f(first["id"])) else BLANK_PROG
        json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(prog, open(os.path.join(WORK, "top8_progress.json"), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump({"url": first["video"], "aid": first["aid"]}, open(os.path.join(WORK, "target.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.rebuild_tag_tabs(); self.load_repo(); self.refresh_stats(); self.refresh_repo_box()
        self.rlog.insert("end", "🗑️ 仓库【%s】已删除，已切回【%s】\n" % (r["name"], first["name"]))

    # ---------- 标签页 ----------
    def rebuild_tag_tabs(self):
        # 清空notebook重建（当前仓库的标签）
        for tab in self.tab_note.tabs():
            self.tab_note.forget(tab)
        self.tab_logs = {}
        self.tab_vars = {}
        repo = self.active_repo()
        for cfg in repo.get("tags", []):
            self.add_tag_tab(cfg["name"], cfg.get("maxv", 30), cfg.get("rng", "近90天"), save=False)
        addf = ttk.Frame(self.tab_note)
        self.tab_note.add(addf, text=" ＋添加标签 ")
        self._plus_index = len(repo.get("tags", []))

    def add_tag_tab(self, name, maxv=30, rng="近90天", save=True):
        f = ttk.Frame(self.tab_note)
        pos = getattr(self, "_plus_index", None)
        if pos is None or pos >= len(self.tab_note.tabs()):
            self.tab_note.add(f, text=" %s " % name[:14])
        else:
            self.tab_note.insert(pos, f, text=" %s " % name[:14])
        # 自适应：标签控件分两行摆放（窗口再窄也不会把探测按钮/输入框挤出视野）
        topA = ttk.Frame(f); topA.pack(fill="x", padx=4, pady=(3, 0))
        v = {"name": tk.StringVar(value=name), "maxv": tk.StringVar(value=str(maxv)), "rng": tk.StringVar(value=rng)}
        self.tab_vars[name] = v
        ttk.Label(topA, text="标签名：").pack(side="left")
        ttk.Entry(topA, textvariable=v["name"], width=10).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(topA, text="🚀 探测此标签", command=lambda n=name: self.probe_tag(n)).pack(side="left", padx=(6, 2))
        topB = ttk.Frame(f); topB.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(topB, text="最多视频：").pack(side="left")
        ttk.Entry(topB, textvariable=v["maxv"], width=5).pack(side="left", padx=2)
        ttk.Label(topB, text="范围：").pack(side="left")
        ttk.Combobox(topB, textvariable=v["rng"], values=["近30天", "近90天", "近365天", "全部时间"], width=9, state="readonly").pack(side="left", padx=2)
        log = scrolledtext.ScrolledText(f, font=("Consolas", 9), bg="#111", fg="#ddd", height=4, width=40)
        log.pack(fill="both", expand=True, padx=4, pady=(0, 3))
        self.tab_logs[name] = log
        if save:
            self.active_repo()["tags"].append({"name": name, "maxv": maxv, "rng": rng})
            self.save_repos()

    def _on_tab_change(self, e):
        repo = self.active_repo()
        cur = self.tab_note.index("current")
        if cur == len(repo.get("tags", [])):
            win = tk.Toplevel(self.root); win.title("新增标签"); win.geometry("380x150"); win.transient(self.root)
            tk.Label(win, text="B站话题/标签名：", font=("微软雅黑", 10)).pack(pady=8)
            ent = ttk.Entry(win, width=26); ent.pack(); ent.focus_set()
            def ok():
                n = ent.get().strip()
                if n:
                    win.destroy()
                    self.add_tag_tab(n)
                    self.tab_note.select(len(self.active_repo()["tags"]) - 1)
            ttk.Button(win, text="添加", command=ok).pack(pady=8)
            win.bind("<Return>", lambda e: ok())

    def del_tag(self):
        repo = self.active_repo()
        cur = self.tab_note.index("current")
        tags = repo.get("tags", [])
        if cur < len(tags):
            name = tags[cur]["name"]
            tags.pop(cur)
            self.save_repos()
            self.rebuild_tag_tabs()

    # ---------- 左栏（上：自定义话语·较大 / 下：人名仓库·略小，grid 55:45） ----------
    def build_left(self, left):
        left.grid_rowconfigure(0, weight=55, uniform="lrow")
        left.grid_rowconfigure(1, weight=45, uniform="lrow")
        left.grid_columnconfigure(0, weight=1)
        tplf = ttk.LabelFrame(left, text=" 自定义话语（🟡艾特区可挪动｜{token}=Token） ")
        tplf.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        bar = ttk.Frame(tplf); bar.pack(fill="x", padx=4, pady=3)
        ttk.Button(bar, text="📍 艾特区移到光标处", command=self.place_at).pack(side="left", padx=3)
        ttk.Button(bar, text="👀 预览3条", command=self.preview_tpl).pack(side="left", padx=3)
        ttk.Button(bar, text="💾 应用到队列", command=self.apply_tpl).pack(side="left", padx=3)
        self.apply_note = tk.StringVar(value="")
        self.wrap_label(tplf, textvariable=self.apply_note, font=("微软雅黑", 9), foreground="#2ecc71", anchor="w").pack(fill="x", padx=6, pady=(0, 2))
        self.txt = scrolledtext.ScrolledText(tplf, font=("微软雅黑", 10), height=4, width=30, wrap="word")
        self.txt.pack(fill="both", expand=True, padx=4, pady=3)
        self.txt.tag_configure("atzone", background="#ffd400", foreground="#000")
        self.txt.insert("1.0", open(TEMPLATE_F, encoding="utf-8").read())
        self.hl_at()
        self.txt.bind("<KeyRelease>", lambda e: self.root.after(60, self.hl_at))
        # 人名仓库（本仓库）：未艾特|已艾特 双栏
        repof = ttk.LabelFrame(left, text=" 📦 人名仓库（未艾特｜已艾特） ")
        repof.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        rbar = ttk.Frame(repof); rbar.pack(fill="x", padx=4, pady=2)
        ttk.Label(rbar, text="筛选：", font=("微软雅黑", 9)).pack(side="left")
        self.repo_filter = tk.StringVar()
        ttk.Entry(rbar, textvariable=self.repo_filter, width=10).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rbar, text="🔍刷新", command=self.load_repo).pack(side="left", padx=4)
        self.repo_stat = tk.StringVar(value="")
        self.wrap_label(repof, textvariable=self.repo_stat, font=("微软雅黑", 9), foreground="#0984e3", anchor="w").pack(fill="x", padx=4, pady=(0, 2))
        rcols = ttk.Frame(repof); rcols.pack(fill="both", expand=True, padx=4, pady=(0, 3))
        leftcol = ttk.Frame(rcols); leftcol.pack(side="left", fill="both", expand=True)
        midline = tk.Frame(rcols, bg="#444", width=3); midline.pack(side="left", fill="y", padx=2)
        rightcol = ttk.Frame(rcols); rightcol.pack(side="right", fill="both", expand=True)
        ttk.Label(leftcol, text="⬜ 未艾特人名", font=("微软雅黑", 9, "bold"), foreground="#aaa").pack(anchor="w")
        self.repo_unsent = scrolledtext.ScrolledText(leftcol, font=("Consolas", 9), bg="#111", fg="#cfc", height=4, width=20)
        self.repo_unsent.pack(fill="both", expand=True)
        ttk.Label(rightcol, text="✅ 已艾特人名", font=("微软雅黑", 9, "bold"), foreground="#2ecc71").pack(anchor="w")
        self.repo_sent = scrolledtext.ScrolledText(rightcol, font=("Consolas", 9), bg="#111", fg="#8f8", height=4, width=20)
        self.repo_sent.pack(fill="both", expand=True)
        self.load_repo()

    def load_repo(self):
        try:
            q = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]
            prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
            kw = self.repo_filter.get().strip()
            unsent_names, sent_names = [], []
            seen = set()
            for gi in range(min(prog["i"], len(q))):
                for n in q[gi]["names"]:
                    if n not in seen: seen.add(n); sent_names.append(n)
            for gi in range(prog["i"], len(q)):
                for n in q[gi]["names"]:
                    if n not in seen: seen.add(n); unsent_names.append(n)
            if kw:
                unsent_names = [n for n in unsent_names if kw in n]
                sent_names = [n for n in sent_names if kw in n]
            self.repo_unsent.delete("1.0", "end")
            self.repo_sent.delete("1.0", "end")
            self.repo_unsent.insert("end", "未艾特 %d人\n" % len(unsent_names))
            for n in unsent_names[:400]:
                self.repo_unsent.insert("end", n + "\n")
            if len(unsent_names) > 400:
                self.repo_unsent.insert("end", "…（共%d）\n" % len(unsent_names))
            self.repo_sent.insert("end", "已艾特 %d人\n" % len(sent_names))
            for n in sent_names[:400]:
                self.repo_sent.insert("end", n + "\n")
            if len(sent_names) > 400:
                self.repo_sent.insert("end", "…（共%d）\n" % len(sent_names))
            self.repo_stat.set("未艾特%d｜已艾特%d" % (len(unsent_names), len(sent_names)))
        except Exception as e:
            self.repo_unsent.insert("end", "读取出错 %r\n" % e)

    def hl_at(self):
        self.txt.tag_remove("atzone", "1.0", "end")
        s = "1.0"
        while True:
            pos = self.txt.search(AT_MARK, s, "end")
            if not pos:
                break
            self.txt.tag_add("atzone", pos, "%s+%dc" % (pos, len(AT_MARK)))
            s = "%s+%dc" % (pos, len(AT_MARK))

    def place_at(self):
        cur = self.txt.index("insert")
        content = self.txt.get("1.0", "end").replace(AT_MARK, "")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", content)
        try:
            self.txt.insert(cur, AT_MARK, ("atzone",))
        except Exception:
            self.txt.insert("end", AT_MARK, ("atzone",))
        self.hl_at()

    def get_tpl(self):
        return self.txt.get("1.0", "end").strip()

    def preview_tpl(self):
        tpl = self.get_tpl()
        prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
        q = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]
        win = tk.Toplevel(self.root); win.title("模板预览（前3组）"); win.transient(self.root)
        win.geometry("680x360")
        pv = scrolledtext.ScrolledText(win, font=("Consolas", 9), bg="#111", fg="#8f8")
        pv.pack(fill="both", expand=True, padx=6, pady=6)
        for gi in range(prog["i"], min(prog["i"] + 3, len(q))):
            g = q[gi]
            t = render_template(tpl, g["tok"], g["names"])
            pv.insert("end", "【第%d组 Token=%s 长度%d】\n%s\n\n" % (gi + 1, "{:,}".format(g["tok"]), len(t), t))
        if not q or prog["i"] >= len(q):
            pv.insert("end", "（本仓库队列为空：先去标签页探测入库）\n")
        pv.insert("end", "（点【💾应用到队列】才生效）\n")

    def apply_tpl(self):
        tpl = self.get_tpl()
        open(TEMPLATE_F, "w", encoding="utf-8").write(tpl)
        prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
        qdoc = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))
        q = qdoc["queue"]
        i = prog["i"]; n = 0
        for gi in range(i, len(q)):
            g = q[gi]
            t = render_template(tpl, g["tok"], g["names"])
            if len(t) > 999: t = t[:996] + "…"
            g["text"] = t; n += 1
        json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.apply_note.set("✅ 未发%d组已改写" % n)

    # ---------- 右栏 ----------
    def build_right(self, right):
        # 视频链接（用户自定义，绑定到当前仓库）
        vf = ttk.LabelFrame(right, text=" 🎯 目标视频 ")
        vf.pack(fill="x", padx=6, pady=(6, 2))
        vrow = ttk.Frame(vf); vrow.pack(fill="x", padx=4, pady=4)
        vrow.grid_columnconfigure(0, weight=1)
        self.video_var = tk.StringVar(value=self.active_repo()["video"])
        ttk.Entry(vrow, textvariable=self.video_var, width=20).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(vrow, text="🔗 绑定", command=self.bind_video).grid(row=0, column=1, padx=4)
        ttk.Button(vrow, text="🌐 打开页面", command=self.open_page).grid(row=0, column=2, padx=4)
        self.video_note = tk.StringVar(value="（绑定后需重新点开始发送生效）")
        self.wrap_label(vf, textvariable=self.video_note, font=("微软雅黑", 8), foreground="#888", anchor="w").pack(fill="x", padx=6, pady=(0, 2))
        # 启停
        btns = ttk.Frame(right); btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="▶ 开始发送", command=self.start_send).pack(side="left", padx=6)
        ttk.Button(btns, text="■ 停止发送", command=self.stop_send).pack(side="left", padx=6)
        ttk.Button(btns, text="🔄 刷新数据", command=self.refresh_stats).pack(side="left", padx=6)
        # 发送参数
        cfgf = ttk.LabelFrame(right, text=" ⚙️ 发送参数 ")
        cfgf.pack(fill="x", padx=6, pady=4)
        crow = ttk.Frame(cfgf); crow.pack(fill="x", padx=4, pady=4)
        ttk.Label(crow, text="间隔(秒)：").pack(side="left")
        iv = "35"
        try:
            iv = str(json.load(open(os.path.join(WORK, "sender_config.json"), encoding="utf-8"))["interval"])
        except Exception:
            pass
        self.interval_var = tk.StringVar(value=iv)
        ttk.Entry(crow, textvariable=self.interval_var, width=6).pack(side="left", padx=(2, 10))
        ttk.Label(crow, text="每条艾特人数：").pack(side="left")
        bv = "10"
        try:
            bv = str(json.load(open(os.path.join(WORK, "sender_config.json"), encoding="utf-8"))["batch"])
        except Exception:
            pass
        self.batch_var = tk.StringVar(value=bv)
        ttk.Entry(crow, textvariable=self.batch_var, width=4).pack(side="left", padx=2)
        ttk.Button(crow, text="💾 保存参数", command=self.save_send_config).pack(side="left", padx=10)
        self.cfg_note = tk.StringVar(value="（B站硬限：每条最多艾特10人）")
        self.wrap_label(cfgf, textvariable=self.cfg_note, font=("微软雅黑", 8), foreground="#e67e22", anchor="w").pack(fill="x", padx=4, pady=(0, 3))
        # UP主删评卫士：召唤评论发布后20~30秒删除（给@通知留足送达时间，同时压缩曝光窗口）
        delf = ttk.LabelFrame(right, text=" 🧹 删评卫士（UP主延时删评·发布后20~30秒） ")
        delf.pack(fill="x", padx=6, pady=4)
        drow1 = ttk.Frame(delf); drow1.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(drow1, text="UP主：", font=("微软雅黑", 9)).pack(side="left")
        self.del_up_var = tk.StringVar(value="未登录")
        tk.Label(drow1, textvariable=self.del_up_var, font=("微软雅黑", 9, "bold"), fg="#2ecc71").pack(side="left", padx=2)
        ttk.Button(drow1, text="📱 扫码登录UP主", command=lambda: self.open_qr_login(
            "扫码登录UP主号（发视频的那个号）——只用于删除评论，不会顶掉召唤号", target="up")).pack(side="left", padx=4)
        ttk.Button(drow1, text="▶ 启动删除", command=self.del_start).pack(side="left", padx=4)
        ttk.Button(drow1, text="■ 停止", command=self.del_stop).pack(side="left", padx=4)
        drow2 = ttk.Frame(delf); drow2.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Button(drow2, text="🧹 立即清理全部历史召唤评论", command=self.del_sweep).pack(side="left", padx=2)
        # 删评卫士专属运行日志
        self.del_log = scrolledtext.ScrolledText(delf, font=("Consolas", 8), bg="#111", fg="#cfc", height=3, width=30)
        self.del_log.pack(fill="both", expand=True, padx=4, pady=(2, 2))
        self.del_note = tk.StringVar(value="（UP主未登录：点【📱 扫码登录UP主】；启动后自动删除召唤号评论：发布后20~30秒）")
        self.wrap_label(delf, textvariable=self.del_note, font=("微软雅黑", 8), foreground="#888", anchor="w").pack(fill="x", padx=4, pady=(0, 3))
        self._del_deleted = set()
        self._del_stats = {"n": 0, "lat": 0.0}
        self.del_refresh_up()
        # 统计
        st = ttk.Frame(right); st.pack(fill="x", padx=6, pady=2)
        st.grid_columnconfigure(1, weight=1)
        self.sv_state = tk.StringVar(value="未知")
        self.sv_sent = tk.StringVar(value="-")
        self.sv_left = tk.StringVar(value="-")
        self.sv_tok = tk.StringVar(value="-")
        rows = [("状态", self.sv_state), ("已@人数", self.sv_sent), ("剩余人数", self.sv_left), ("最新Token", self.sv_tok)]
        for i, (k, v) in enumerate(rows):
            ttk.Label(st, text=k + "：").grid(row=i, column=0, sticky="e", pady=2)
            self.wrap_label(st, textvariable=v, foreground="#0984e3", anchor="w").grid(row=i, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="运行日志：", font=("微软雅黑", 9)).pack(anchor="w", padx=8)
        self.rlog = scrolledtext.ScrolledText(right, font=("Consolas", 8), bg="#111", fg="#ddd", height=5, width=30)
        self.rlog.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        self.refresh_stats()
        self.root.after(3000, self.auto_refresh)

    def bind_video(self):
        url = self.video_var.get().strip()
        m = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if not m:
            self.video_note.set("✗ 链接里没找到BV号"); return
        bvid = m.group(1)
        aid, title = fetch_aid(bvid)
        if not aid:
            self.video_note.set("✗ 视频信息获取失败"); return
        r = self.active_repo()
        r["video"] = "https://www.bilibili.com/video/" + bvid
        r["aid"] = aid
        self.save_repos()
        json.dump({"url": r["video"], "aid": aid}, open(os.path.join(WORK, "target.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.video_note.set("✅ 已绑定《%s》aid=%s（正在打开发送页面；重新点开始发送生效）" % ((title or "")[:18], aid))
        self.refresh_repo_box()
        if open_engine_page(r["video"]):   # 绑定成功 → 自动在发送浏览器弹出该页
            self.root.attributes("-topmost", False)   # 工作台让位给弹出的页面

    def open_page(self):
        """🌐 打开页面：在艾特机器人运行用的调试浏览器里打开目标页
        输入框里填了别的BV则优先打开那个页面，否则打开当前已绑定的视频页"""
        url = self.active_repo()["video"]
        cur = self.video_var.get().strip()
        m = re.search(r"(BV[0-9A-Za-z]{10})", cur)
        if m and m.group(1) not in url:
            url = "https://www.bilibili.com/video/" + m.group(1)
        if open_engine_page(url):
            self.root.attributes("-topmost", False)   # 工作台让位：页面才能真正弹到眼前
            self.video_note.set("🌐 已在发送浏览器打开：%s（点工作台可切回）" % url)
        else:
            self.video_note.set("✗ 未找到Edge浏览器，无法打开页面")

    def save_send_config(self):
        try: interval = max(5, int(self.interval_var.get()))
        except Exception: interval = 35
        try: batch = max(1, min(10, int(self.batch_var.get())))
        except Exception: batch = 10
        json.dump({"interval": interval, "batch": batch}, open(os.path.join(WORK, "sender_config.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.interval_var.set(str(interval)); self.batch_var.set(str(batch))
        self.cfg_note.set("✅ 间隔%d秒，每条%d人" % (interval, batch))
        if batch != 10:
            self.rechunk_unsent(batch)

    def rechunk_unsent(self, batch):
        try:
            prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
            qdoc = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))
            q = qdoc["queue"]
            i = prog["i"]
            unsent = []
            for g in q[i:]:
                unsent.extend(g["names"])
            tpl = open(TEMPLATE_F, encoding="utf-8").read()
            tok = q[i - 1]["tok"] if i > 0 and q else 100000
            new_groups = []
            k = 0
            while k < len(unsent):
                ch = unsent[k:k + batch]; k += batch
                tok += random.randint(800, 1300)
                t = render_template(tpl, tok, ch)
                if len(t) > 999: t = t[:996] + "…"
                new_groups.append({"tok": tok, "names": ch, "text": t})
            qdoc["queue"] = q[:i] + new_groups
            json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
            self.rlog.insert("end", "♻️ 队列已按每条%d人重切：%d组\n" % (batch, len(new_groups)))
            self.rlog.see("end")
            self.refresh_stats()
        except Exception as e:
            self.rlog.insert("end", "重切失败 %r\n" % e)

    def start_send(self):
        open(os.path.join(WORK, "flag.txt"), "w", encoding="utf-8").write("RUN")
        self.sv_state.set("▶ 运行中")
        import subprocess
        running = False
        try:
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'top8'} | Measure-Object).Count"],
                timeout=15, creationflags=_NOWIN).decode().strip()
            running = int(out or "0") > 0
        except Exception:
            pass
        if not running:
            subprocess.Popen(["python", os.path.join(WORK, "top8_slow.py")], cwd=WORK,
                             stdout=open(os.path.join(WORK, "top8_console.txt"), "a", encoding="utf-8"),
                             stderr=subprocess.STDOUT, creationflags=_NOWIN)
            self.rlog.insert("end", time.strftime("[%H:%M:%S] ") + "发送引擎已启动（目标=当前仓库视频）\n")
        self.refresh_stats()

    def stop_send(self):
        open(os.path.join(WORK, "flag.txt"), "w", encoding="utf-8").write("STOP")
        self.sv_state.set("■ 已请求停止")
        import subprocess
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'top8'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_NOWIN)
        self.rlog.insert("end", time.strftime("[%H:%M:%S] ") + "发送引擎已停止\n")

    def refresh_stats(self):
        try:
            p = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
            q = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]
            total = sum(len(g["names"]) for g in q)
            self.sv_sent.set("%d 人（%d条）" % (p["posted_n"], p["posted"]))
            self.sv_left.set("%d 人（约%d条）" % (total - p["posted_n"], max(0, len(q) - p["i"])))
            self.sv_tok.set("{:,}".format(p["last_tok"]))
            try:
                if open(os.path.join(WORK, "flag.txt"), encoding="utf-8").read().strip() == "RUN":
                    self.sv_state.set("▶ 运行中")
                else:
                    self.sv_state.set("■ 已停止")
            except Exception:
                pass
            try:
                lines = open(os.path.join(WORK, "top8_log.txt"), encoding="utf-8").read().strip().split("\n")
                if lines:
                    last = lines[-1]
                    if not hasattr(self, "_last_log") or self._last_log != last:
                        self._last_log = last
                        self.rlog.insert("end", last + "\n")
                        self.rlog.see("end")
            except Exception:
                pass
        except Exception as e:
            self.sv_state.set("读取出错 %r" % e)

    def auto_refresh(self):
        self.refresh_stats()
        self.root.after(3000, self.auto_refresh)

    # ---------- 标签探测（入当前仓库队列） ----------
    def probe_tag(self, name):
        v = self.tab_vars.get(name)
        if not v:
            return
        tag = v["name"].get().strip()
        try: maxv = int(v["maxv"].get())
        except Exception: maxv = 30
        rng = v["rng"].get()
        repo = self.active_repo()
        for t in repo["tags"]:
            if t["name"] == name:
                t.update({"name": tag, "maxv": maxv, "rng": rng})
        self.save_repos()
        log = self.tab_logs.get(tag) or self.tab_logs.get(name)
        if log:
            log.insert("end", time.strftime("[%H:%M:%S] ") + "开始探测【%s】→ 入仓库【%s】…\n" % (tag, repo["name"]))
            log.see("end")
        threading.Thread(target=self.probe_run, args=(tag, maxv, rng, repo["aid"]), daemon=True).start()

    def probe_run(self, tag, maxv, rng, own_aid):
        def lg(m):
            self.q.put(("tag", tag, m))
        try:
            since = {"近30天": 30, "近90天": 90, "近365天": 365, "全部时间": 0}.get(rng, 90)
            since = int(time.time()) - since * 86400 if since else 0
            vids = {}
            # 阶段1：搜索视频（带进度）
            for page in range(1, 6):
                lg("🔍 搜索中… 第%d页" % page)
                p = wbi_sign({"search_type": "video", "keyword": tag, "page": page,
                              "order": "pubdate" if since else "totalrank",
                              "pubtime_begin_s": since, "pubtime_end_s": int(time.time())})
                j = api_get("https://api.bilibili.com/x/web-interface/wbi/search/type", p)
                if not j or j.get("code") != 0:
                    break
                for it in ((j.get("data") or {}).get("result") or []):
                    aid = it.get("aid")
                    if aid and aid not in vids and aid != own_aid:
                        vids[aid] = {"title": re.sub(r"<[^>]+>", "", it.get("title", "")), "review": int(it.get("review") or 0)}
                time.sleep(random.uniform(0.8, 1.4))
                if len(vids) >= maxv:
                    break
            lg("✓ 搜索完成：共%d个视频待爬" % len(vids))
            master = json.load(open(os.path.join(WORK, "data", "users_master.json"), encoding="utf-8"))
            known = set(master.keys())
            qdoc = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))
            queue = qdoc["queue"]
            inqueue = set()
            for g in queue:
                inqueue.update(g["names"])
            # 本仓库目标视频线上已@名单（防重复）
            live = set()
            cur = 0
            for pg2 in range(8):
                try:
                    H = {"User-Agent": UA, "Referer": "https://www.bilibili.com/",
                         "Cookie": "; ".join("%s=%s" % (k, v) for k, v in sess.items() if v)}
                    d = json.loads(urllib.request.urlopen(urllib.request.Request(
                        "https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (own_aid, cur), headers=H), timeout=15).read())
                    dd = d.get("data") or {}
                    reps = dd.get("replies") or []
                    if not reps: break
                    for r in reps:
                        for m in re.findall(r"@([^\u200b@\n]+)", ((r.get("content") or {}).get("message") or "")):
                            live.add(m.strip())
                    cu = dd.get("cursor") or {}
                    cur = cu.get("next", 0)
                    if cu.get("is_end"): break
                    time.sleep(0.5)
                except Exception:
                    break
            optout = set()
            try:
                optout = set(json.load(open(os.path.join(WORK, "apology_state.json"), encoding="utf-8")).get("done_names", []))
            except Exception:
                pass
            new_names = []
            # 阶段3：逐个视频爬评论区（带"哪个视频+进度"日志）
            todo = list(vids.items())[:maxv]
            for vi, (aid, v) in enumerate(todo, 1):
                lg("📥 [%d/%d] 正在爬：《%s》（评论%d条）" % (vi, len(todo), v["title"][:30], v["review"]))
                users = crawl_video_users(aid)
                fresh = 0
                for mid, info in users.items():
                    n = info["uname"]
                    if mid == str(SELF_MID) or mid == str(load_accounts().get("active") or "") or mid in known or not n:
                        continue
                    if n in inqueue or n in live or n in optout:
                        continue
                    master[mid] = {"uname": n, "latest": info.get("ctime", int(time.time())), "count": 1, "vids": [aid]}
                    known.add(mid)
                    new_names.append(n)
                    fresh += 1
                lg("   ✓ 《%s》评论用户%d人，新入库%d人" % (v["title"][:24], len(users), fresh))
                time.sleep(0.8)
            lg("📊 探测完成：%d个视频，去重后共新增%d人" % (len(todo), len(new_names)))
            json.dump(master, open(os.path.join(WORK, "data", "users_master.json"), "w", encoding="utf-8"), ensure_ascii=False)
            tpl = open(TEMPLATE_F, encoding="utf-8").read()
            tok = queue[-1]["tok"] if queue else 100000
            k = 0; added = 0
            while k < len(new_names):
                ch = new_names[k:k + 10]; k += 10
                tok += random.randint(800, 1300)
                t = render_template(tpl, tok, ch)
                if len(t) > 999: t = t[:996] + "…"
                queue.append({"tok": tok, "names": ch, "text": t})
                added += 1
            qdoc["queue"] = queue
            json.dump(qdoc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)
            lg("✅ 入库+追加%d组（队尾Token %s）" % (added, "{:,}".format(tok)))
            self.q.put(("repo", None, "refresh"))
        except Exception as e:
            lg("异常 %r" % e)

    def pump(self):
        try:
            while True:
                kind, a, m = self.q.get_nowait()
                if kind == "ui":
                    try:
                        a()
                    except Exception:
                        pass
                    continue
                if kind == "repo" and m == "refresh":
                    self.load_repo(); self.refresh_stats(); self.refresh_repo_box()
                    continue
                log = self.tab_logs.get(a)
                if log:
                    log.insert("end", m + "\n")
                    log.see("end")
        except thq.Empty:
            pass
        self.root.after(600, self.pump)

    # ---------- 系统占用实时监控（右上角单一区域） ----------
    def _sys_monitor(self):
        """后台线程：每2秒采真实硬件读数，刷新右上角 CPU/运存/GPU 显示"""
        def ui(fn):
            self.q.put(("ui", fn, None))
        while True:
            try:
                cpu = cpu_usage()
                if cpu is None:      # 首次采样无差值，等下一轮
                    time.sleep(2)
                    continue
                # 定宽数字格式：数字位数变化时文本长度恒定，杜绝标签宽度呼吸
                parts = ["🖥️ CPU %3d%%" % int(cpu)]
                ram = ram_usage()
                if ram:
                    pct, total, avail = ram
                    parts.append("运存 %4.1f/%4.1fGB·%3d%%" % ((total - avail) / (1024 ** 3), total / (1024 ** 3), pct))
                gpu = gpu_sample()
                parts.append(("GPU %3d%%·显存%5dMB" % gpu) if gpu else "GPU 不可用")
                txt = " ｜ ".join(parts)
                ui(lambda t=txt: self.sys_var.set(t))
            except Exception:
                pass
            time.sleep(2)

    # ---------- UP主删评卫士 ----------
    def del_refresh_up(self):
        """刷新UP主登录状态显示（凭据存upmaster.json，与召唤号账号库完全独立）"""
        try:
            d = json.load(open(os.path.join(WORK, "upmaster.json"), encoding="utf-8"))
            if d.get("SESSDATA") and d.get("uname"):
                self.del_up_var.set(d["uname"][:14])
                self.del_note.set("UP主：%s（已登录，删评就绪）" % d["uname"])
                return
        except Exception:
            pass
        self.del_up_var.set("未登录")

    def _del_up_creds(self):
        """返回UP主专用凭据（upmaster.json），未登录返回None"""
        try:
            d = json.load(open(os.path.join(WORK, "upmaster.json"), encoding="utf-8"))
            if d.get("SESSDATA"):
                return {k: d.get(k) or "" for k in
                        ("SESSDATA", "bili_jct", "DedeUserID", "buvid3", "ac_time_value", "DedeUserID__ckMd5", "sid")
                        if d.get(k)}
        except Exception:
            pass
        return None

    def _del_up_mid(self):
        try:
            return str(json.load(open(os.path.join(WORK, "upmaster.json"), encoding="utf-8")).get("mid"))
        except Exception:
            return None

    def _del_log_msg(self, m):
        """删评卫士专属运行日志（UI线程执行）"""
        try:
            self.del_log.insert("end", time.strftime("[%H:%M:%S] ") + m + "\n")
            self.del_log.see("end")
        except Exception:
            pass

    def dlog(self, m):
        """线程安全写删评日志"""
        self.q.put(("ui", lambda: self._del_log_msg(m), None))

    def del_start(self):
        if getattr(self, "_del_on", False):
            return
        if not self._del_up_creds():
            self.del_note.set("✗ UP主未登录：点【📱 扫码登录UP主】登录发视频的号")
            return
        self._del_on = True
        self.del_note.set("监听中… 发现召唤评论后20~30秒删除")
        self.dlog("🧹 删评卫士已启动（UP主=%s）——召唤评论将于发布后20~30秒删除（监听召唤号【%s】）" % (
            self.del_up_var.get(), active_uname() or "?"))
        threading.Thread(target=self._deleter_loop, daemon=True).start()

    def del_stop(self):
        self._del_on = False
        self.del_note.set("已停止（本次共删%d条）" % self._del_stats.get("n", 0))
        self.dlog("🧹 删评卫士已停止（本次共删%d条）" % self._del_stats.get("n", 0))

    def del_sweep(self):
        """立即清理该视频下全部历史召唤评论（所有召唤账号发布的，含被隐藏的）"""
        creds = self._del_up_creds()
        if not creds:
            self.del_note.set("✗ UP主未登录：点【📱 扫码登录UP主】登录发视频的号")
            return
        from tkinter import messagebox
        if not messagebox.askyesno("清理历史", "将删除该视频下所有召唤评论（含被隐藏的历史评论）。\n确定执行？（逐条慢删，防止UP主号被风控）"):
            return
        self.dlog("🧹 开始清理历史召唤评论…")
        threading.Thread(target=self._del_sweep_run, args=(creds,), daemon=True).start()

    def _del_sweep_run(self, creds):
        def ui(fn):
            self.q.put(("ui", fn, None))
        try:
            doc = load_accounts()
            summon_mids = {str(a.get("mid")) for a in doc["accounts"]}
            summon_mids.discard(self._del_up_mid())   # UP主自己的评论（如祭台）不删
            aid = int(self.active_repo()["aid"])
            reps = deleter_scan_comments(creds, aid, pages=40)
            hits = []
            seen = set()
            for r in reps:
                mid = str((r.get("member") or {}).get("mid") or "")
                msg = ((r.get("content") or {}).get("message") or "")
                rpid = r.get("rpid")
                if mid in summon_mids and "已消耗" in msg and rpid and rpid not in seen:
                    seen.add(rpid)
                    hits.append(rpid)
            ui(lambda n=len(hits): self._del_log_msg("🧹 找到历史召唤评论 %d 条，开始逐条删除…" % n))
            ok = 0
            for i, rpid in enumerate(hits, 1):
                done, code, m = deleter_del_comment(creds, aid, rpid)
                self._del_deleted.add(rpid)
                if done:
                    ok += 1
                ui(lambda i=i, ok=ok, done=done, c=code, m=m: self._del_log_msg(
                    "🧹 [%d/%d] %s rpid=%s%s" % (i, len(hits), "✅已删" if done else "✗失败 code=%s" % c, rpid, (" " + m) if (not done and m) else "")))
                time.sleep(2.0)   # 慢删防风控
            ui(lambda ok=ok, n=len(hits): self._del_log_msg("🧹 历史清理完成：成功%d/%d" % (ok, len(hits))))
            ui(lambda ok=ok: self.del_note.set("历史清理完成：删除%d条" % ok))
        except Exception as e:
            ui(lambda m=repr(e): self._del_log_msg("🧹 清理异常 %s" % m))

    def _deleter_loop(self):
        """后台监听：召唤号发布的评论一出现就登记，发布后20~30秒删除（给@通知留足送达时间）"""
        def ui(fn):
            self.q.put(("ui", fn, None))
        pending = {}   # rpid -> {"t": 到点时间戳, "ctime": 发布时间, "tries": 重试次数}
        while getattr(self, "_del_on", False):
            try:
                creds = self._del_up_creds()
                if not creds:
                    ui(lambda: self.del_note.set("✗ UP主账号无效，已停止"))
                    self.dlog("⛔ UP主账号无效，监听已停止")
                    self._del_on = False
                    break
                doc = load_accounts()
                summon_mid = str(doc.get("active"))     # 当前召唤号=工作台激活账号
                aid = int(self.active_repo()["aid"])
                reps = deleter_scan_comments(creds, aid, pages=1)
                now = time.time()
                # 1) 登记新发现的召唤评论 → 延迟20~30秒再删（给@通知留足送达时间）
                for r in reps:
                    mid = str((r.get("member") or {}).get("mid") or "")
                    msg = ((r.get("content") or {}).get("message") or "")
                    rpid = r.get("rpid")
                    if (mid == summon_mid and "已消耗" in msg and rpid
                            and rpid not in pending and rpid not in self._del_deleted):
                        # 以评论发布时间为基准延迟20~30秒：新评论落在发布后20~30秒；
                        # 离线期间漏掉的老评论到点即删
                        ctime0 = r.get("ctime") or now
                        delay = random.uniform(20, 30)
                        pending[rpid] = {"t": ctime0 + delay, "ctime": ctime0, "tries": 0}
                        if now < ctime0 + delay:
                            self.dlog("👀 发现召唤评论 rpid=%s，发布后%.0f秒将删除" % (rpid, delay))
                        else:
                            self.dlog("👀 发现历史召唤评论 rpid=%s（已发布%.0f秒），到点即删" % (rpid, max(0.0, now - ctime0)))
                # 2) 到点的执行删除（失败自动重试，最多3次）
                for rpid in list(pending.keys()):
                    if rpid in self._del_deleted:      # 已被"清理历史"等其他路径删掉
                        pending.pop(rpid, None)
                        continue
                    if time.time() < pending[rpid]["t"]:
                        continue
                    ctime = pending[rpid]["ctime"]
                    done, code, m = deleter_del_comment(creds, aid, rpid)
                    if done:
                        pending.pop(rpid, None)
                        self._del_deleted.add(rpid)
                        lat = max(0.0, time.time() - ctime)
                        self._del_stats["n"] += 1
                        self._del_stats["lat"] += lat
                        n = self._del_stats["n"]
                        avg = self._del_stats["lat"] / n
                        ui(lambda rp=rpid, la=lat, n=n, av=avg: self._del_log_msg(
                            "🧹 已删除召唤评论 rpid=%s（发布后%.0f秒｜已删%d条·平均%.0f秒）" % (rp, la, n, av)))
                    elif code == -101:
                        ui(lambda: self.del_note.set("✗ UP主凭据已失效，请重新扫码后再启动"))
                        self.dlog("⛔ UP主凭据已失效（服务端-101），监听已停止——请重新扫码登录UP主")
                        self._del_on = False
                        break
                    else:
                        pending[rpid]["tries"] += 1
                        if pending[rpid]["tries"] >= 3:
                            pending.pop(rpid, None)
                            self._del_deleted.add(rpid)
                            ui(lambda c=code, m=m, rp=rpid: self._del_log_msg(
                                "✗ 放弃删除 rpid=%s（重试3次 code=%s %s）" % (rp, c, m)))
                        else:
                            pending[rpid]["t"] = time.time() + 5   # 5秒后重试
                            ui(lambda c=code, m=m, rp=rpid: self._del_log_msg(
                                "⚠️ 删除失败 rpid=%s code=%s %s，5秒后重试" % (rp, c, m)))
                    time.sleep(0.5)
                n = self._del_stats["n"]
                if self._del_on:
                    ui(lambda n=n, p=len(pending): self.del_note.set(
                        "监听中… 已删%d条｜待删%d条" % (n, p)))
                # 待删队列非空或引擎在跑→2秒一轮（延时到点精准）；空闲→12秒一轮
                engine_running = False
                try:
                    engine_running = open(os.path.join(WORK, "flag.txt"), encoding="utf-8").read().strip() == "RUN"
                except Exception:
                    pass
                time.sleep(2 if (pending or engine_running) else 12)
            except Exception as e:
                self.dlog("监听异常 %s（5秒后自动重试）" % repr(e))
                time.sleep(5)

    # ---------- 登录态：左上角模块 / 账号管理 / 扫码登录 / 首启引导 ----------
    def refresh_login_btn(self):
        name = active_uname() or ("已登录" if sess.get("SESSDATA") else None)
        self.login_var.set("👤 " + (name if name else "未登录（点击登录）"))

    def _login_health(self):
        """后台线程：启动时+每5分钟到B站服务端验证当前凭据是否仍然有效。
        本地记录的"已登录"不等于服务端有效——凭据被风控踢下线后，
        按钮要立刻显示警告，避免用户误以为登录着就点发送。"""
        def ui(fn):
            self.q.put(("ui", fn, None))
        while True:
            try:
                mid, uname = fetch_nav_info()
                ok = mid is not None
                self._login_ok = ok
                if ok:
                    ui(self.refresh_login_btn)
                else:
                    ui(lambda: self.login_var.set("⚠️ 登录已失效（点击重新扫码）"))
            except Exception:
                pass
            time.sleep(300)

    def _rlog_msg(self, m):
        try:
            self.rlog.insert("end", m + "\n")
            self.rlog.see("end")
        except Exception:
            pass

    def _maybe_first_run(self):
        # 新用户初次启动：本机没有任何B站登录凭据 → 自动引导扫码登录自己的账号
        if getattr(self, "_first_shown", False) or sess.get("SESSDATA"):
            return
        self._first_shown = True
        win = tk.Toplevel(self.root); win.title("欢迎使用 召唤&艾特 工作台"); win.transient(self.root)
        win.geometry("560x330")
        tk.Label(win, text="首次使用：请登录你自己的B站账号", font=("微软雅黑", 12, "bold")).pack(pady=(14, 6))
        msg = ("本程序发布评论使用「当前登录的B站账号」。\n"
               "请用B站手机App扫描二维码，登录你自己的账号（不要借用他人凭据）。\n"
               "登录凭据只保存在你自己的电脑里，不会上传。\n"
               "登录后可随时点左上角【👤 登录】按钮添加、切换或退出账号。")
        ttk.Label(win, text=msg, font=("微软雅黑", 10), justify="left").pack(padx=16)
        brow = ttk.Frame(win); brow.pack(pady=12)
        def go():
            win.destroy()
            self.open_qr_login("首次使用：请登录你的账号")
        ttk.Button(brow, text="📱 立即扫码登录", command=go).pack(side="left", padx=6)
        ttk.Button(brow, text="稍后再说", command=win.destroy).pack(side="left", padx=6)

    def open_account_mgr(self):
        if getattr(self, "_mgr_win", None) and self._mgr_win.winfo_exists():
            self._mgr_win.lift()
            self.mgr_refresh()
            return
        win = tk.Toplevel(self.root); win.title("账号管理"); win.transient(self.root)
        win.geometry("620x440")
        self._mgr_win = win
        # 开/关留痕：万一再出现"自动关闭"有据可查
        try:
            open(os.path.join(WORK, "mgr_close.log"), "a", encoding="utf-8").write(time.strftime("[%m-%d %H:%M:%S] 打开\n"))
        except Exception:
            pass
        def _mgr_destroy_log(e=None):
            try:
                open(os.path.join(WORK, "mgr_close.log"), "a", encoding="utf-8").write(time.strftime("[%m-%d %H:%M:%S] 销毁\n"))
            except Exception:
                pass
        win.bind("<Destroy>", _mgr_destroy_log, add="+")
        top = ttk.Frame(win); top.pack(fill="x", padx=10, pady=(10, 2))
        self._mgr_cur = tk.StringVar(value="")
        ttk.Label(top, textvariable=self._mgr_cur, font=("微软雅黑", 11, "bold"), foreground="#0984e3").pack(side="left")
        self.wrap_label(win, text="凭据仅保存在本机；切换/退出账号后需重新点【▶ 开始发送】生效（引擎会把当前账号写入浏览器再发评论）",
                        font=("微软雅黑", 8), foreground="#888", anchor="w").pack(fill="x", padx=10, pady=(0, 6))
        self._mgr_tree = ttk.Treeview(win, show="headings", columns=("uname", "mid", "cur"), height=8)
        self._mgr_tree.heading("uname", text="账号昵称")
        self._mgr_tree.heading("mid", text="mid")
        self._mgr_tree.heading("cur", text="状态")
        self._mgr_tree.column("uname", width=240)
        self._mgr_tree.column("mid", width=180)
        self._mgr_tree.column("cur", width=100)
        self._mgr_tree.pack(fill="both", expand=True, padx=10, pady=4)
        brow = ttk.Frame(win); brow.pack(fill="x", padx=10, pady=8)
        ttk.Button(brow, text="📱 扫码添加账号", command=self.open_qr_login).pack(side="left", padx=4)
        ttk.Button(brow, text="✅ 切换为当前", command=self.mgr_switch).pack(side="left", padx=4)
        ttk.Button(brow, text="🚪 退出并移除", command=self.mgr_remove).pack(side="left", padx=4)
        ttk.Button(brow, text="🔄 刷新", command=self.mgr_refresh).pack(side="left", padx=4)
        ttk.Button(brow, text="关闭", command=win.destroy).pack(side="right", padx=4)
        self.mgr_refresh()
        # 模态：账号管理开着时主窗口完全不可点——杜绝"再点一下主窗口，弹窗被全屏主窗盖住像消失"
        try:
            win.wait_visibility()
            win.grab_set()
        except Exception:
            pass

    def mgr_refresh(self):
        if not (getattr(self, "_mgr_win", None) and self._mgr_win.winfo_exists()):
            self.refresh_login_btn()
            return
        doc = try_migrate_session(load_accounts())
        tree = self._mgr_tree
        tree.delete(*tree.get_children())
        for a in doc["accounts"]:
            cur = "✅ 当前" if str(a.get("mid")) == str(doc.get("active")) else ""
            tree.insert("", "end", iid="m" + str(a.get("mid")), values=(a.get("uname") or "?", a.get("mid") or "?", cur))
        name = active_uname(doc) or ("已登录" if sess.get("SESSDATA") else "未登录")
        self._mgr_cur.set("当前登录：%s" % name)
        self.refresh_login_btn()

    def mgr_switch(self):
        sel = getattr(self, "_mgr_tree", None) and self._mgr_tree.selection()
        if not sel:
            return
        mid = sel[0][1:]
        doc = load_accounts()
        acc = next((a for a in doc["accounts"] if "m" + str(a.get("mid")) == sel[0]), None)
        if not acc:
            return
        doc["active"] = str(acc.get("mid"))
        save_accounts(doc)
        apply_session(account_creds(acc))
        self.mgr_refresh()
        self._rlog_msg("👤 已切换当前账号为【%s】——请重新点【▶开始发送】生效（引擎将用此账号发评论）" % acc.get("uname"))

    def mgr_remove(self):
        sel = getattr(self, "_mgr_tree", None) and self._mgr_tree.selection()
        if not sel:
            return
        doc = load_accounts()
        acc = next((a for a in doc["accounts"] if "m" + str(a.get("mid")) == sel[0]), None)
        if not acc:
            return
        from tkinter import messagebox
        if not messagebox.askyesno("退出登录", "确定退出并移除账号【%s】吗？\n（会尝试让B站服务端登录态失效，并删除本机凭据）" % (acc.get("uname") or "?")):
            return
        threading.Thread(target=server_logout, args=(account_creds(acc),), daemon=True).start()
        was_active = str(doc.get("active")) == str(acc.get("mid"))
        doc["accounts"] = [a for a in doc["accounts"] if "m" + str(a.get("mid")) != sel[0]]
        if was_active:
            if doc["accounts"]:
                nxt = doc["accounts"][0]
                doc["active"] = str(nxt.get("mid"))
                apply_session(account_creds(nxt))
            else:
                doc["active"] = None
                apply_session({k: "" for k in ("SESSDATA", "bili_jct", "DedeUserID", "buvid3")})
        save_accounts(doc)
        self.mgr_refresh()
        self._rlog_msg("🚪 账号【%s】已退出并移除" % (acc.get("uname") or "?"))

    def open_qr_login(self, note="", target="summon"):
        if getattr(self, "_qr_win", None) and self._qr_win.winfo_exists():
            self._qr_restart(target=target)
            self._qr_win.lift()
            return
        parent = self._mgr_win if (getattr(self, "_mgr_win", None) and self._mgr_win.winfo_exists()) else self.root
        win = tk.Toplevel(parent)
        win.title("扫码登录UP主号" if target == "up" else "扫码登录B站账号")
        win.transient(parent); win.attributes("-topmost", True)
        win.geometry("430x600")
        self._qr_win = win
        ttk.Label(win, text="请用【B站手机App】扫下面的二维码", font=("微软雅黑", 10, "bold")).pack(pady=(10, 2))
        if note:
            ttk.Label(win, text=note, font=("微软雅黑", 9), foreground="#e67e22").pack(pady=(0, 2))
        self._qr_img_lbl = ttk.Label(win); self._qr_img_lbl.pack(pady=4)
        self._qr_status = tk.StringVar(value="正在生成二维码…")
        self.wrap_label(win, textvariable=self._qr_status, font=("微软雅黑", 9), foreground="#0984e3", anchor="w").pack(fill="x", padx=12)
        brow = ttk.Frame(win); brow.pack(pady=8)
        ttk.Button(brow, text="🔄 刷新二维码", command=self._qr_restart).pack(side="left", padx=4)
        ttk.Button(brow, text="取消", command=self._qr_close).pack(side="left", padx=4)
        win.protocol("WM_DELETE_WINDOW", self._qr_close)
        self._qr_restart(target=target)

    def _qr_restart(self, target="summon"):
        self._qr_token = (getattr(self, "_qr_token", 0) or 0) + 1
        tok = self._qr_token
        try:
            self._qr_status.set("正在生成二维码…")
        except Exception:
            pass
        threading.Thread(target=self._qr_flow, args=(tok, target), daemon=True).start()

    def _qr_close(self):
        self._qr_token = (getattr(self, "_qr_token", 0) or 0) + 1000
        try:
            if getattr(self, "_qr_win", None) and self._qr_win.winfo_exists():
                self._qr_win.destroy()
        except Exception:
            pass
        self._qr_win = None

    def _qr_autoclose(self):
        try:
            if getattr(self, "_qr_win", None) and self._qr_win.winfo_exists():
                self._qr_win.after(1200, self._qr_close)
        except Exception:
            pass

    def _qr_flow(self, tok, target="summon"):
        def ui(fn):
            self.q.put(("ui", fn, None))
        def alive():
            return getattr(self, "_qr_token", 0) == tok
        try:
            if qrcode is None:
                ui(lambda: self._qr_status.set("缺少qrcode库：请在命令行执行 pip install qrcode 后重试"))
                return
            import requests as rq
            q = rq.Session()
            q.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com"})
            r = q.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=15).json()
            q.cookies.set("buvid3", r["data"]["b_3"])
            q.cookies.set("buvid4", r["data"]["b_4"])
            while alive():
                g = q.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate", timeout=15).json()
                if g.get("code") != 0:
                    ui(lambda m=str(g.get("message")): self._qr_status.set("生成二维码失败：%s，5秒后自动重试" % m))
                    time.sleep(5)
                    continue
                key = g["data"]["qrcode_key"]; url = g["data"]["url"]
                qr = qrcode.QRCode(box_size=6, border=3)
                qr.add_data(url); qr.make(fit=True)
                img = qr.make_image()
                ui(lambda im=img: self._set_qr_img(im))
                ui(lambda: self._qr_status.set("等待扫码：请用B站手机App扫码，扫过后在手机上点【确认登录】"))
                t0 = time.time()
                expired = False
                while alive() and time.time() - t0 < 175:
                    try:
                        p = q.get("https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                                  params={"qrcode_key": key}, timeout=15).json()
                    except Exception:
                        time.sleep(2)
                        continue
                    d = p.get("data") or {}
                    code = d.get("code")
                    if code == 0:
                        cookies = {c["name"]: c["value"] for c in ((d.get("cookie_info") or {}).get("cookies") or [])}
                        creds = {
                            "SESSDATA": cookies.get("SESSDATA") or q.cookies.get("SESSDATA") or "",
                            "bili_jct": cookies.get("bili_jct") or q.cookies.get("bili_jct") or "",
                            "DedeUserID": cookies.get("DedeUserID") or q.cookies.get("DedeUserID") or "",
                            "buvid3": q.cookies.get("buvid3") or "",
                        }
                        # 存全套cookie（含ac_time_value/DedeUserID__ckMd5/sid等风控辅助）——
                        # 注入浏览器/拼请求头更完整，降低风控与CSRF类校验失败概率
                        for k, v in cookies.items():
                            if v and k not in creds:
                                creds[k] = v
                        mid, uname = fetch_nav_info(creds)
                        if not mid:
                            ui(lambda: self._qr_status.set("✗ 登录成功但获取账号信息失败，请点【🔄 刷新二维码】重试"))
                            return
                        if target == "up":
                            # UP主专用登录：独立存upmaster.json，不进账号库、不占召唤号槽位
                            up = dict(creds); up.update({"mid": mid, "uname": uname, "saved_at": int(time.time())})
                            json.dump(up, open(os.path.join(WORK, "upmaster.json"), "w", encoding="utf-8"), ensure_ascii=False)
                            ui(lambda m=uname: self._qr_status.set("✅ UP主登录成功：%s（窗口将自动关闭）" % m))
                            ui(self.del_refresh_up)
                            ui(lambda m=uname: self._del_log_msg("✅ UP主【%s】已扫码登录，删评卫士就绪" % m))
                            ui(lambda m=uname: self._rlog_msg("🧹 UP主【%s】已登录，删评卫士就绪" % m))
                            ui(self._qr_autoclose)
                            return
                        doc = load_accounts()
                        doc["accounts"] = [a for a in doc["accounts"] if str(a.get("mid")) != mid]
                        acc = dict(creds); acc.update({"mid": mid, "uname": uname, "saved_at": int(time.time())})
                        doc["accounts"].append(acc)
                        doc["active"] = mid
                        save_accounts(doc)
                        apply_session(creds)
                        ui(lambda m=uname: self._qr_status.set("✅ 登录成功：%s（已设为当前账号，窗口将自动关闭）" % m))
                        ui(self.refresh_login_btn)
                        ui(lambda m=uname: self._rlog_msg("👤 账号【%s】扫码登录成功并设为当前——请重新点【▶开始发送】生效" % m))
                        ui(self.mgr_refresh)
                        ui(self._qr_autoclose)
                        return
                    if code == 86090:
                        ui(lambda: self._qr_status.set("已扫码，请在手机上点【确认登录】"))
                    elif code == 86038:
                        ui(lambda: self._qr_status.set("二维码已过期，正在生成新二维码…"))
                        expired = True
                        break
                    time.sleep(2)
                if expired and alive():
                    continue
        except Exception as e:
            ui(lambda m=repr(e): self._qr_status.set("出错 %s" % m))

    def _set_qr_img(self, pil_img):
        try:
            from PIL import ImageTk
            self._qr_photo = ImageTk.PhotoImage(pil_img)
            self._qr_img_lbl.configure(image=self._qr_photo)
        except Exception as e:
            try:
                self._qr_status.set("二维码显示失败 %r" % e)
            except Exception:
                pass

def _find_workbench_hwnd():
    """查找已在运行的工作台主窗口（按精确标题匹配）"""
    try:
        import ctypes, ctypes.wintypes
        user32 = ctypes.windll.user32
        res = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def cb(h, l):
            if not user32.IsWindowVisible(h):
                return True
            n = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, n, 256)
            if n.value == "召唤&艾特 工作台":
                res.append(h)
            return True
        user32.EnumWindows(cb, 0)
        return res[0] if res else None
    except Exception:
        return None

if __name__ == "__main__":
    # 单实例保护：已有工作台在运行时，再点图标只把旧窗口调到前台（防止多实例互相全屏遮挡，
    # 造成"弹出的窗口1~2秒就消失"的假象）
    _h = _find_workbench_hwnd()
    if _h:
        try:
            import ctypes
            u32 = ctypes.windll.user32
            if u32.IsIconic(_h):
                u32.ShowWindow(_h, 9)      # SW_RESTORE
            u32.SetForegroundWindow(_h)
        except Exception:
            pass
        sys.exit(0)
    root = tk.Tk()
    Workbench(root)
    root.mainloop()
