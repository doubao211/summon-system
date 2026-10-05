# -*- coding: utf-8 -*-
"""精确计算漏网人员：
1) 6条被吞评论（133,904~138,564）的60人，谁在其它可见评论里已被成功@过（有at_name_to_mid解析）→ 不漏；否则漏
2) 老评论31,453（只发出6人）与1,763（2人粘连未解析）的缺漏人
3) 输出 补发名单.txt"""
import io, sys, json, re, os, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = r"E:\欧尼酱_召唤工作区"
AID = 117384258060764
ck = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
     "Referer": "https://www.bilibili.com/video/BV1VdHE6PEEa",
     "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items() if v)}

def get(url):
    r = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 全部可见评论（顶层+楼中楼）里被真实解析@过的名字
resolved = set()
cur = 0
while True:
    d = get("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (AID, cur))
    dd = d.get("data") or {}
    reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
    if not reps:
        break
    for r_ in reps:
        at = (r_.get("content") or {}).get("at_name_to_mid") or {}
        resolved.update(at.keys())
        for sub in (r_.get("replies") or []):
            at2 = (sub.get("content") or {}).get("at_name_to_mid") or {}
            resolved.update(at2.keys())
    cu = dd.get("cursor") or {}
    cur = cu.get("next", 0)
    if cu.get("is_end"):
        break
    time.sleep(0.4)
print("评论区真实解析@过的名字: %d" % len(resolved))

# 6条被吞评论的人名（从audit_report.json取）
rep = json.load(open(os.path.join(WORK, "audit_report.json"), encoding="utf-8"))
missing_names = []
for g in rep["missing_groups"]:
    missing_names.extend(g["names"])
print("被吞6组人名共: %d" % len(missing_names))

# 31,453老评论缺的人：从油猴名单.json找该组的10人
hmm = json.load(open(r"C:\Users\Administrator\Desktop\欧尼酱_艾特召唤\油猴名单.json", encoding="utf-8"))["groups"]
g31453 = None
for g in hmm:
    if "31,453" in g.get("g", "") or "31453" in str(g.get("g", "")):
        g31453 = g; break
names_31453 = [p["n"] for p in g31453["l"]] if g31453 else []
print("31,453组名单:", names_31453)

# 1,763组：粘连"@寒葉ねknight_影"=寒葉ね+knight_影两人
names_1763_extra = ["knight_影", "寒葉ね"]

# 汇总漏网
missed = []
for n in missing_names:
    if n not in resolved:
        missed.append(n + "  (来自被吞Token评论)")
for n in names_31453:
    if n not in resolved:
        missed.append(n + "  (来自31,453老评论只发出6人)")
for n in names_1763_extra:
    if n not in resolved:
        missed.append(n + "  (来自1,763老评论粘连未解析)")

print("\n== 漏网名单（该@到但从未成功@过的）: %d 人" % len(missed))
for n in missed:
    print("  ", n)

with open(os.path.join(WORK, "补发名单.txt"), "w", encoding="utf-8") as f:
    f.write("== 补发名单（%d人，生成于 %s）==\n" % (len(missed), time.strftime("%Y-%m-%d %H:%M")))
    f.write("说明：被B站审核池吞掉的6条评论(133904~138564)的60人 + 老评论缺漏者\n")
    f.write("以下人名从未在任何可见评论中被成功@过：\n\n")
    for n in missed:
        f.write(n.split("  (")[0] + "\n")
print("\n已存 补发名单.txt")
