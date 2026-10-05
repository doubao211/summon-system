# -*- coding: utf-8 -*-
"""持续增量探测+入库+入队（安全合并版）：
1) 扫描近N天新视频+自己视频新评论 → 新用户（去重已库/已退订/已@）
2) 760+线上已@名字实时剔除（防止重复）
3) 新用户追加到发送队列尾部（"放到后面"），不打乱当前进度指针
"""
import io, sys, json, time, random, hashlib, urllib.parse, re, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

WORK = r"E:\欧尼酱_召唤工作区"
DATA = os.path.join(WORK, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SINCE = int(time.time()) - 7 * 86400  # 近7天
OWN_AID = 117384258060764
SELF_MID = 3706929960454980

sess = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
S = requests.Session()
S.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com",
                  "Accept": "application/json, text/plain, */*", "Accept-Language": "zh-CN,zh;q=0.9"})
for k in ("buvid3", "SESSDATA", "bili_jct", "DedeUserID"):
    if sess.get(k):
        S.cookies.set(k, sess[k])

def log(m):
    print(time.strftime("[%H:%M:%S] ") + str(m), flush=True)

def safe_int(v):
    try: return int(v)
    except Exception: return 0

# wbi
r = S.get("https://api.bilibili.com/x/web-interface/nav", timeout=15).json()
img_key = r["data"]["wbi_img"]["img_url"].rsplit("/", 1)[1].split(".")[0]
sub_key = r["data"]["wbi_img"]["sub_url"].rsplit("/", 1)[1].split(".")[0]
MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,37,12,13,25,40,34,55,48,17,54,51,36,0,39,6,30,44,52,1,57,56,26,41,11,22,4,24,20,21,7,38,16,59]
mixin_key = "".join((img_key + sub_key)[i] for i in MIXIN)[:32]
CHAR_REMOVE = set("!'()*")
def wbi_sign(params):
    p = {k: "".join(ch for ch in str(v) if ch not in CHAR_REMOVE) for k, v in params.items()}
    p["wts"] = int(time.time())
    p = dict(sorted(p.items()))
    q = urllib.parse.urlencode(p)
    p["w_rid"] = hashlib.md5((q + mixin_key).encode()).hexdigest()
    return p

def api_get(url, params=None, retries=4):
    for a in range(retries):
        try:
            j = S.get(url, params=params, timeout=20).json()
            if j.get("code", -1) in (-412, -352):
                log("  风控code=%s，退避90s" % j["code"]); time.sleep(90); continue
            return j
        except Exception as e:
            log("  GET fail %r" % e); time.sleep(3 + a * 5)
    return None

# ---------- 1) 线上已@名字实时扫描（防重复核心） ----------
def scan_live():
    live = set()
    cur = 0
    H = {"User-Agent": UA, "Referer": "https://www.bilibili.com/video/BV1VdHE6PEEa",
         "Cookie": "; ".join("%s=%s" % (k, v) for k, v in sess.items() if v)}
    for pg in range(80):
        try:
            rq = urllib.request.Request("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (OWN_AID, cur), headers=H)
            d = json.loads(urllib.request.urlopen(rq, timeout=15).read())
        except Exception:
            break
        dd = d.get("data") or {}
        reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
        if not reps:
            break
        for r_ in reps:
            t = ((r_.get("content") or {}).get("message") or "")
            for m in re.findall(r"@([^\u200b@\n]+)", t):
                live.add(m.strip())
            for sub in (r_.get("replies") or []):
                t2 = ((sub.get("content") or {}).get("message") or "")
                for m in re.findall(r"@([^\u200b@\n]+)", t2):
                    live.add(m.strip())
        cu = dd.get("cursor") or {}
        cur = cu.get("next", 0)
        if cu.get("is_end"):
            break
        time.sleep(0.5)
    return live

# ---------- 2) 搜新视频 ----------
KEYWORDS = ["别当欧尼酱了", "别当欧尼酱", "欧尼酱了", "不当哥哥了", "别当哥哥了", "onimai", "まひろ",
            "绪山真寻", "真寻", "美波里", "别当欧尼酱了 MAD", "别当欧尼酱了 手书", "别当欧尼酱了 二创", "真寻 最新"]
MARKERS = ["欧尼酱", "不当哥哥", "别当哥哥", "お兄ちゃん", "おしまい", "onimai", "Onimai", "ONIMAI",
           "まひろ", "マヒロ", "緒山", "绪山", "美波里", "みはり", "真寻", "真尋", "不是哥们", "你币有了"]
known_aids = {OWN_AID}
try:
    for fn in os.listdir(os.path.join(DATA, "crawl")):
        if fn.endswith(".json"):
            known_aids.add(int(fn[:-5]))
except Exception:
    pass

newvids = {}
for kw in KEYWORDS:
    for page in (1, 2):
        p = wbi_sign({"search_type": "video", "keyword": kw, "page": page,
                      "order": "pubdate", "pubtime_begin_s": SINCE, "pubtime_end_s": int(time.time())})
        j = api_get("https://api.bilibili.com/x/web-interface/wbi/search/type", p)
        if not j or j.get("code") != 0:
            continue
        for it in ((j.get("data") or {}).get("result") or []):
            aid = safe_int(it.get("aid"))
            pub = safe_int(it.get("pubdate"))
            if not aid or aid in known_aids or pub < SINCE:
                continue
            title = re.sub(r"<[^>]+>", "", it.get("title", ""))
            tags = ""
            if not any(m in title for m in MARKERS):
                tj = api_get("https://api.bilibili.com/x/tag/archive/tags", {"aid": aid})
                if tj and tj.get("code") == 0:
                    tags = " ".join(t.get("tag_name", "") for t in (tj.get("data") or []))
            if any(m in (title + " " + tags) for m in MARKERS):
                newvids[aid] = {"aid": aid, "title": title, "review": safe_int(it.get("review"))}
        time.sleep(random.uniform(0.8, 1.4))
log("近7天新增相关视频: %d" % len(newvids))

# ---------- 3) 爬新视频评论+自己视频新评论 ----------
master = json.load(open(os.path.join(DATA, "users_master.json"), encoding="utf-8"))
known_mids = set(master.keys())
st = json.load(open(os.path.join(WORK, "apology_state.json"), encoding="utf-8")) if os.path.exists(os.path.join(WORK, "apology_state.json")) else {"done_names": []}
optout = set(st.get("done_names", []))

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
        for r_ in reps:
            m = r_.get("member") or {}
            mid = str(m.get("mid") or "")
            if mid:
                out[mid] = {"uname": m.get("uname", ""), "msg": (r_.get("content") or {}).get("message", "")[:60], "ctime": r_.get("ctime", 0)}
            for sub in (r_.get("replies") or []):
                m2 = sub.get("member") or {}
                mid2 = str(m2.get("mid") or "")
                if mid2 and mid2 not in out:
                    out[mid2] = {"uname": m2.get("uname", ""), "msg": (sub.get("content") or {}).get("message", "")[:60], "ctime": sub.get("ctime", 0)}
        cu = d.get("cursor") or {}
        cur = cu.get("next", 0)
        if cu.get("is_end"):
            break
        time.sleep(0.7)
    return out

all_new = {}
for v in newvids.values():
    if v["review"] <= 0:
        continue
    users = crawl_video_users(v["aid"])
    log("爬 aid=%s 得 %d" % (v["aid"], len(users)))
    for mid, info in users.items():
        info["src_aid"] = v["aid"]
        all_new.setdefault(mid, info)
    time.sleep(1.0)
own = crawl_video_users(OWN_AID, pages_max=10)

# ---------- 4) 过滤 ----------
live = scan_live()
log("线上已@名字: %d" % len(live))
candidates = {}
for mid, info in list(all_new.items()) + list(own.items()):
    if mid == str(SELF_MID) or mid in known_mids:
        continue
    if info["uname"] in optout or info["uname"] in live:
        continue
    candidates[mid] = info
log("过滤后新增用户: %d" % len(candidates))

FAN_MARKERS = ["真寻", "真尋", "まひろ", "マヒロ", "mahiro", "Mahiro", "MAHIRO", "绪山", "緒山", "欧尼酱", "お兄ちゃん",
               "美波里", "みはり", "美夜", "枫", "かえで", "萌黄", "もみじ", "朝日", "あさひ", "别当", "おしまい", "onimai"]
fans = {mid: i for mid, i in candidates.items() if any(m.lower() in i["uname"].lower() for m in FAN_MARKERS)}
if candidates:
    for mid, info in list(fans.items())[:15]:
        log("  ♥ %s" % info["uname"])

# ---------- 5) 入库 users_master ----------
now = int(time.time())
for mid, info in candidates.items():
    master[mid] = {"uname": info["uname"], "latest": info.get("ctime", now), "count": 1, "vids": [info.get("src_aid", OWN_AID)]}
json.dump(master, open(os.path.join(DATA, "users_master.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---------- 6) 追加到队列尾部（不打乱进度） ----------
prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
queue_doc = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))
queue = queue_doc["queue"]
TITLE = "⚡大型召唤魔法发动中⚡"
APOLOGY = "如果你被打扰了，那么很抱歉，请在本条评论下方回复111，以后将不会再打扰您。"
inqueue = set()
for g in queue:
    inqueue.update(g["names"])
new_names = [info["uname"] for info in candidates.values() if info["uname"] not in inqueue]
tok = queue[-1]["tok"] if queue else prog["last_tok"]
added_groups = 0
k = 0
while k < len(new_names):
    ch = new_names[k:k + 10]; k += 10
    tok += random.randint(800, 1300)
    text = TITLE + " 已消耗 {:,} Token ".format(tok) + " ".join("@" + n for n in ch) + " " + APOLOGY
    if len(text) > 999:
        text = text[:996] + "…"
    queue.append({"tok": tok, "names": ch, "text": text})
    added_groups += 1
queue_doc["queue"] = queue
json.dump(queue_doc, open(os.path.join(WORK, "top5_queue.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---------- 7) 归档 ----------
arc = r"C:\Users\Administrator\Desktop\欧尼酱_艾特召唤\增量探测日志.txt"
with open(arc, "a", encoding="utf-8") as f:
    f.write("\n== %s == 新视频%d 新用户%d(真寻味%d) 追加组%d 队列尾Token=%s\n" % (
        time.strftime("%Y-%m-%d %H:%M"), len(newvids), len(candidates), len(fans), added_groups, "{:,}".format(tok)))
    for mid, info in candidates.items():
        f.write("%s %s (mid=%s aid=%s)\n" % ("♥" if mid in fans else " ", info["uname"], mid, info.get("src_aid", OWN_AID)))
log("完成：新用户%d 真寻味%d 追加%d组（队尾Token {:,}）".format(tok).replace("%d", "{}").format(len(candidates), len(fans), added_groups))
