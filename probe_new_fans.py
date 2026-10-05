# -*- coding: utf-8 -*-
"""探测新增真寻狂热者：
1) 搜索近3天新发布的相关视频（复用stage2b逻辑，起始时间=上次爬取后）
2) 爬取新视频评论 + 我们自己视频BV1VdHE6PEEa的最新评论（含召唤楼里的回复者）
3) 过滤已知用户（users_master + 已发名单），剔除回复111者与本账号
4) 真寻味名字单独标记；全部新增入库（users_master + sent_state.remaining + 桌面归档文件）
"""
import io, sys, json, time, random, hashlib, urllib.parse, re, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

WORK = r"E:\欧尼酱_召唤工作区"
DATA = os.path.join(WORK, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SINCE = int(time.time()) - 3 * 86400  # 近3天
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

# wbi sign
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

# ---------- 1) 搜新视频 ----------
KEYWORDS = ["别当欧尼酱了", "别当欧尼酱", "欧尼酱了", "不当哥哥了", "别当哥哥了", "onimai", "まひろ",
            "绪山真寻", "真寻", "美波里", "别当欧尼酱了 MAD", "别当欧尼酱了 手书", "别当欧尼酱了 二创", "真寻 最新"]
MARKERS = ["欧尼酱", "不当哥哥", "别当哥哥", "お兄ちゃん", "おしまい", "onimai", "Onimai", "ONIMAI",
           "まひろ", "マヒロ", "緒山", "绪山", "美波里", "みはり", "真寻", "真尋", "不是哥们", "你币有了"]
known_aids = set()
try:
    for fn in os.listdir(os.path.join(DATA, "crawl")):
        if fn.endswith(".json"):
            known_aids.add(int(fn[:-5]))
except Exception:
    pass
known_aids.add(OWN_AID)
log("已知已爬视频数: %d" % len(known_aids))

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
                newvids[aid] = {"aid": aid, "bvid": it.get("bvid"), "title": title,
                                "author": it.get("author"), "review": safe_int(it.get("review")), "pub": pub}
        time.sleep(random.uniform(0.8, 1.5))
log("近3天新增相关视频: %d" % len(newvids))
for v in list(newvids.values())[:20]:
    log("  新视频 aid=%s 评论%d 《%s》 up=%s" % (v["aid"], v["review"], v["title"][:40], v["author"]))

# ---------- 2) 爬新视频评论 + 自己视频新评论 ----------
master = json.load(open(os.path.join(DATA, "users_master.json"), encoding="utf-8"))  # mid->info
known_mids = set(master.keys())

def crawl_video_users(aid, pages_max=6):
    """收集该视频顶层+楼中楼用户"""
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
                if mid2:
                    out.setdefault(mid2, {"uname": m2.get("uname", ""), "msg": (sub.get("content") or {}).get("message", "")[:60], "ctime": sub.get("ctime", 0)})
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
    log("爬 aid=%s 得 %d 用户" % (v["aid"], len(users)))
    for mid, info in users.items():
        info["src_aid"] = v["aid"]
        all_new.setdefault(mid, info)
    time.sleep(1.0)

# 自己视频（含楼中楼回复者与111退订者）
own = crawl_video_users(OWN_AID, pages_max=10)
log("自己视频用户数: %d" % len(own))

# ---------- 3) 过滤 ----------
optout_mids = set()
for mid, info in own.items():
    msg = info.get("msg", "")
    if re.search(r"(^|\s|[，。!！])1{3,}(\s|$|。|！|!)", msg) or msg.strip() in ("111", "1111", "11111", "111111"):
        optout_mids.add(mid)

candidates = {}
for mid, info in list(all_new.items()) + list(own.items()):
    if mid == str(SELF_MID):
        continue
    if mid in known_mids:
        continue
    if mid in optout_mids:
        continue
    if "机器人" in info["uname"] or info["uname"].startswith("bili_") is False and False:
        pass
    candidates[mid] = info

log("过滤后新增用户: %d（其中退订111者 %d 已剔除）" % (len(candidates), len(optout_mids)))
for mid in optout_mids:
    log("  退订者: %s %s (%s)" % (mid, own.get(mid, {}).get("uname", "?"), own.get(mid, {}).get("msg", "")[:30]))

# 真寻味名字标记
FAN_MARKERS = ["真寻", "真尋", "まひろ", "マヒロ", "mahiro", "Mahiro", "MAHIRO", "绪山", "緒山", "欧尼酱", "お兄ちゃん",
               "美波里", "みはり", "美夜", "枫", "かえで", "萌黄", "もみじ", "朝日", "あさひ", "别当", "おしまい", "onimai"]
fan_users = {mid: info for mid, info in candidates.items() if any(m.lower() in info["uname"].lower() for m in FAN_MARKERS)}
log("真寻狂热者风格用户名: %d" % len(fan_users))
for mid, info in list(fan_users.items())[:30]:
    log("  ♥ %s" % info["uname"])

# ---------- 4) 入库 ----------
now = int(time.time())
for mid, info in candidates.items():
    master[mid] = {"uname": info["uname"], "latest": info.get("ctime", now), "count": 1, "vids": [info.get("src_aid", OWN_AID)]}
json.dump(master, open(os.path.join(DATA, "users_master.json"), "w", encoding="utf-8"), ensure_ascii=False)
log("users_master 更新: %d" % len(master))

# sent_state.remaining 追加（去重保序）
st = json.load(open(os.path.join(WORK, "sent_state.json"), encoding="utf-8"))
rem = st["remaining"]
remset = set(rem)
added_names = []
for mid, info in candidates.items():
    if info["uname"] not in remset:
        rem.append(info["uname"]); remset.add(info["uname"]); added_names.append(info["uname"])
st["remaining"] = rem
json.dump(st, open(os.path.join(WORK, "sent_state.json"), "w", encoding="utf-8"), ensure_ascii=False)
log("remaining 追加 %d 个名字 → 总 %d" % (len(added_names), len(rem)))

# 退订者从 remaining 中剔除（防再打扰）
removed_optout = [own[m]["uname"] for m in optout_mids if own.get(m, {}).get("uname") in remset]
st["remaining"] = [n for n in st["remaining"] if n not in set(removed_optout)]
json.dump(st, open(os.path.join(WORK, "sent_state.json"), "w", encoding="utf-8"), ensure_ascii=False)
log("退订者已从待发名单剔除: %d" % len(removed_optout))

# 桌面归档
arc_dir = r"C:\Users\Administrator\Desktop\欧尼酱_艾特召唤"
lines = ["== 新增真寻狂热者探测 %s ==" % time.strftime("%Y-%m-%d %H:%M"), "新视频 %d 个 / 新用户 %d 人 / 真寻味名字 %d 人 / 退订111 %d 人" % (len(newvids), len(candidates), len(fan_users), len(optout_mids)), ""]
lines.append("-- 新增视频 --")
for v in newvids.values():
    lines.append("aid=%s 评论%d 发布%s 《%s》 up=%s" % (v["aid"], v["review"], time.strftime("%m-%d %H:%M", time.localtime(v["pub"])), v["title"][:40], v["author"]))
lines.append("")
lines.append("-- 新增用户（全部入库，♥=真寻味名字）--")
for mid, info in sorted(candidates.items(), key=lambda x: -x[1].get("ctime", 0)):
    tag = "♥" if mid in fan_users else " "
    lines.append("%s %s (mid=%s, 来自aid=%s)" % (tag, info["uname"], mid, info.get("src_aid", OWN_AID)))
lines.append("")
lines.append("-- 回复111退订者（已从待发名单剔除）--")
for mid in optout_mids:
    lines.append("%s (mid=%s) %s" % (own.get(mid, {}).get("uname", "?"), mid, own.get(mid, {}).get("msg", "")[:40]))
with open(os.path.join(arc_dir, "新增狂热者探测_20261005.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
log("桌面归档已写: 新增狂热者探测_20261005.txt")
print("DONE 新用户=%d 真寻味=%d 退订剔除=%d" % (len(candidates), len(fan_users), len(removed_optout)))
