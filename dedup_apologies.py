# -*- coding: utf-8 -*-
"""删除重复道歉：
1) 深扫自己视频全部楼层，收集我(mid=SELF_MID)发出的道歉回复（含道歉标记词）
2) 规则A：同一个@用户名的道歉回复 >1 条 → 保留最早1条，删除其余
3) 规则B：道歉所在楼层 ≠ 该用户实际发111的楼层 → 删除（错位道歉）
4) 通过 x/v2/reply/del API 删除（自己的评论可删，已验证）"""
import io, sys, json, time, re, os, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = r"E:\欧尼酱_召唤工作区"
AID = 117384258060764
SELF_MID = 3706929960454980

ck = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
     "Referer": "https://www.bilibili.com/video/BV1VdHE6PEEa",
     "Origin": "https://www.bilibili.com",
     "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items() if v)}

def get(url):
    r = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post_del(rpid):
    data = urllib.parse.urlencode({"oid": AID, "type": 1, "rpid": rpid, "csrf": ck["bili_jct"]}).encode()
    r = urllib.request.Request("https://api.bilibili.com/x/v2/reply/del", headers=dict(H, **{"Content-Type": "application/x-www-form-urlencoded"}), data=data)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

APOLOGY_MARK = re.compile(r"(已经收到|收到您的111|您的111|退订|永久移除|免打扰|深表歉意|打扰了，实在抱歉|对不起，打扰您了|十分抱歉！您的111)")
TARGET = re.compile(r"^@(.+?)\s")
OPTOUT_MSG = re.compile(r"1{3,}")

# 1) 收集所有楼层根 + 每楼全部回复
roots = []
cur = 0
for pg in range(10):
    try:
        d = get("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (AID, cur))
        dd = d.get("data") or {}
        reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
        if not reps:
            break
        for r_ in reps:
            roots.append({"rpid": r_.get("rpid"), "rcount": r_.get("rcount") or 0, "msg": (r_.get("content") or {}).get("message", "")})
        cu = dd.get("cursor") or {}
        cur = cu.get("next", 0)
        if cu.get("is_end"):
            break
        time.sleep(0.5)
    except Exception as e:
        print("main err", e); break
print("顶层评论数:", len(roots))

# 2) 每楼深扫全部子回复
my_apologies = []   # (rpid, root, msg, ctime, target)
user_111_root = {}  # uname -> root (该用户发111的楼层)
for rt in roots:
    rpid0, rc = rt["rpid"], rt["rcount"]
    if rc <= 0:
        continue
    pn = 1
    while True:
        try:
            d2 = get("https://api.bilibili.com/x/v2/reply/reply?type=1&oid=%d&root=%d&pn=%d&ps=20" % (AID, rpid0, pn))
        except Exception as e:
            print("floor err", e); break
        if d2.get("code") != 0:
            break
        reps2 = (d2.get("data") or {}).get("replies") or []
        if not reps2:
            break
        for sub in reps2:
            mid = str((sub.get("member") or {}).get("mid") or "")
            uname = (sub.get("member") or {}).get("uname", "")
            msg = ((sub.get("content") or {}).get("message") or "")
            # 我发出的道歉
            if mid == str(SELF_MID) and APOLOGY_MARK.search(msg):
                m2 = TARGET.match(msg.strip())
                tgt = m2.group(1) if m2 else "?"
                my_apologies.append({"rpid": sub.get("rpid"), "root": rpid0, "msg": msg, "ctime": sub.get("ctime", 0), "target": tgt})
            # 任何用户的111评论（定位其楼层）
            elif mid != str(SELF_MID) and OPTOUT_MSG.search(msg.strip()) and len(msg.strip()) <= 30:
                user_111_root[uname] = rpid0
        page = (d2.get("data") or {}).get("page") or {}
        if pn * 20 >= (page.get("count") or 0):
            break
        pn += 1
        time.sleep(0.5)

print("我发出的道歉回复数:", len(my_apologies))
for a in sorted(my_apologies, key=lambda x: x["ctime"]):
    print("  target=%s root=%s ctime=%s rpid=%s" % (a["target"], a["root"], time.strftime("%H:%M:%S", time.localtime(a["ctime"])), a["rpid"]))

# 3) 判定删除：同target多于一律保最早；错位(root != 用户111楼层)也删
to_del = []
by_target = {}
for a in my_apologies:
    by_target.setdefault(a["target"], []).append(a)
for tgt, lst in by_target.items():
    lst.sort(key=lambda x: x["ctime"])
    keep = lst[0]
    correct_root = user_111_root.get(tgt)
    if correct_root and keep["root"] != correct_root:
        # 错位道歉——删掉，若后面有正确楼层的则保留那条
        right = [x for x in lst if x["root"] == correct_root]
        if right:
            to_del.extend([x for x in lst if x not in right[:1]])
        else:
            # 全部错位：只保留最早1条（仍当作已道歉）
            pass
    else:
        to_del.extend(lst[1:])
print("判定删除条数:", len(to_del))

# 4) 执行删除
for a in to_del:
    try:
        d = post_del(a["rpid"])
        print("del rpid=%s code=%s %s" % (a["rpid"], d.get("code"), d.get("message")))
    except Exception as e:
        print("del fail rpid=%s %r" % (a["rpid"], e))
    time.sleep(1.0)

# 5) 把已道歉名单固化（target set），写进 apology_state.json 的 done_names
st_path = os.path.join(WORK, "apology_state.json")
st = json.load(open(st_path, encoding="utf-8")) if os.path.exists(st_path) else {"done_rpids": [], "done_names": [], "count": 0, "fails": {}}
for tgt, lst in by_target.items():
    if tgt != "?" and tgt not in st["done_names"]:
        st["done_names"].append(tgt)
        st["done_rpids"].extend([x["rpid"] for x in lst[:1]])
json.dump(st, open(st_path, "w", encoding="utf-8"), ensure_ascii=False)
print("done_names 固化:", st["done_names"])
