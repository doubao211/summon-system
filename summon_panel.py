# -*- coding: utf-8 -*-
"""发送器控制面板 v2：
- 顶部：视频链接输入框 + 【拉取】按钮（自动开调试浏览器、载入9222端口、锁定目标视频）
- 中部：▶开始发送 / ■停止发送
- 底部：已@人数 / 剩余人数 / 最新Token 实时显示"""
import io, sys, os, json, time, re
import tkinter as tk
from tkinter import ttk
import subprocess, urllib.request, threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = r"E:\欧尼酱_召唤工作区"
FLAG = os.path.join(WORK, "flag.txt")
PROG = os.path.join(WORK, "top8_progress.json")
QUEUE = os.path.join(WORK, "top5_queue.json")
TARGET = os.path.join(WORK, "target.json")
DEFAULT_URL = "https://www.bilibili.com/video/BV1VdHE6PEEa"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE):
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

def set_flag(v):
    open(FLAG, "w", encoding="utf-8").write(v)

def read_flag():
    try:
        return open(FLAG, encoding="utf-8").read().strip()
    except Exception:
        return "STOP"

def port_ok():
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=3)
        return True
    except Exception:
        return False

class Panel:
    def __init__(self, root):
        self.root = root
        root.title("召唤发送器控制台 v2")
        root.geometry("560x400")
        root.attributes("-topmost", True)
        self.status = tk.StringVar(value="未知")
        self.sent = tk.StringVar(value="-")
        self.left = tk.StringVar(value="-")
        self.tok = tk.StringVar(value="-")
        self.pull_state = tk.StringVar(value="端口未就绪")
        self.build()
        self.refresh()

    def build(self):
        # 顶部：视频链接 + 拉取
        f0 = tk.Frame(self.root); f0.pack(pady=8, padx=10, fill="x")
        tk.Label(f0, text="视频链接：", font=("微软雅黑", 10)).pack(side="left")
        self.entry = tk.Entry(f0, font=("微软雅黑", 10), width=42)
        cur = DEFAULT_URL
        try:
            t = json.load(open(TARGET, encoding="utf-8"))
            if t.get("url"): cur = t["url"]
        except Exception:
            pass
        self.entry.insert(0, cur)
        self.entry.pack(side="left", padx=6)
        self.btn_pull = tk.Button(f0, text="拉取", font=("微软雅黑", 10, "bold"), width=6,
                                  bg="#0984e3", fg="white", command=self.pull_thread)
        self.btn_pull.pack(side="left")
        tk.Label(self.root, textvariable=self.pull_state, font=("微软雅黑", 9), fg="#636e72").pack()
        # 中部：开始/停止
        f1 = tk.Frame(self.root); f1.pack(pady=8)
        self.btn_start = tk.Button(f1, text="▶ 开始发送", font=("微软雅黑", 12, "bold"),
                                   width=13, bg="#2ecc71", fg="white", command=self.start)
        self.btn_start.pack(side="left", padx=8)
        self.btn_stop = tk.Button(f1, text="■ 停止发送", font=("微软雅黑", 12, "bold"),
                                  width=13, bg="#e74c3c", fg="white", command=self.stop)
        self.btn_stop.pack(side="left", padx=8)
        # 底部：数据
        f2 = tk.Frame(self.root); f2.pack(pady=6)
        rows = [("运行状态", self.status), ("已@人数", self.sent), ("剩余人数", self.left), ("最新Token", self.tok)]
        for i, (k, v) in enumerate(rows):
            tk.Label(f2, text=k + "：", font=("微软雅黑", 11), width=8, anchor="e").grid(row=i, column=0, sticky="e", pady=3)
            tk.Label(f2, textvariable=v, font=("微软雅黑", 11, "bold"), fg="#0984e3", width=28, anchor="w").grid(row=i, column=1, sticky="w", pady=3)
        tk.Label(self.root, text="用法：粘贴视频链接→点【拉取】（自动开浏览器+载端口）→点【开始发送】。\n停止只是暂停，进度自动保存，再点开始即续发。",
                 font=("微软雅黑", 9), fg="#636e72", justify="left").pack(pady=4)

    # ---------- 拉取 ----------
    def pull_thread(self):
        self.pull_state.set("正在拉取…")
        threading.Thread(target=self.pull, daemon=True).start()

    def pull(self):
        url = self.entry.get().strip()
        m = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if not m:
            self.pull_state.set("✗ 链接里没找到BV号")
            return
        bvid = m.group(1)
        # 取aid + 标题
        try:
            ck = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
            H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
                 "Referer": "https://www.bilibili.com/",
                 "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items() if v)}
            rq = urllib.request.Request("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid, headers=H)
            d = json.loads(urllib.request.urlopen(rq, timeout=15).read())
            if d.get("code") != 0:
                self.pull_state.set("✗ 视频信息获取失败: %s" % d.get("message"))
                return
            aid = d["data"]["aid"]
            title = d["data"]["title"][:24]
        except Exception as e:
            self.pull_state.set("✗ 获取视频信息出错 %r" % e)
            return
        json.dump({"url": url, "aid": aid, "bvid": bvid}, open(TARGET, "w", encoding="utf-8"), ensure_ascii=False)
        # 开浏览器（若9222没通）
        if not port_ok():
            subprocess.Popen([EDGE, "--remote-debugging-port=9222",
                              '--user-data-dir="E:\\欧尼酱_召唤工作区\\edge_profile"',
                              "--no-first-run", "--window-size=1500,1300", url],
                             cwd=os.path.dirname(EDGE))
        else:
            # 已开调试浏览器：新标签打开该视频
            subprocess.Popen([EDGE, "--remote-debugging-port=9222",
                              '--user-data-dir="E:\\欧尼酱_召唤工作区\\edge_profile"', url],
                             cwd=os.path.dirname(EDGE))
        # 等端口
        for i in range(30):
            time.sleep(1)
            if port_ok():
                self.pull_state.set("✓ 端口已就绪 · aid=%s《%s》可以点开始发送" % (aid, title))
                return
        self.pull_state.set("✗ 30秒内端口未就绪")

    # ---------- 开始/停止 ----------
    def sender_running(self):
        try:
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'top8'} | Measure-Object | Select-Object -ExpandProperty Count"],
                timeout=15).decode().strip()
            return int(out or "0") > 0
        except Exception:
            return False

    def start(self):
        if not port_ok():
            self.pull_state.set("端口未就绪：请先点【拉取】")
            return
        set_flag("RUN")
        self.status.set("▶ 运行中")
        if not self.sender_running():
            subprocess.Popen(["python", os.path.join(WORK, "top8_slow.py")], cwd=WORK,
                             stdout=open(os.path.join(WORK, "top8_console.txt"), "a", encoding="utf-8"),
                             stderr=subprocess.STDOUT)
        self.refresh()

    def stop(self):
        set_flag("STOP")
        self.status.set("■ 已请求停止")
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'top8'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.refresh()

    # ---------- 刷新 ----------
    def refresh(self):
        try:
            p = json.load(open(PROG, encoding="utf-8"))
            q = json.load(open(QUEUE, encoding="utf-8"))["queue"]
            total = sum(len(g["names"]) for g in q)
            done = p["posted_n"]
            self.sent.set("%d 人（%d 条评论）" % (done, p["posted"]))
            self.left.set("%d 人（约%d 条）" % (total - done, max(0, len(q) - p["i"])))
            self.tok.set("{:,} Token".format(p["last_tok"]))
            if read_flag() == "RUN" and self.status.get().startswith("■"):
                self.status.set("▶ 运行中")
            elif read_flag() == "STOP" and self.status.get().startswith("▶"):
                self.status.set("■ 已停止")
        except Exception as e:
            self.status.set("读取进度出错: %r" % e)
        self.root.after(3000, self.refresh)

if __name__ == "__main__":
    if not os.path.exists(FLAG):
        set_flag("STOP")
    root = tk.Tk()
    Panel(root)
    root.mainloop()
