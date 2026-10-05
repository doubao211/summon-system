# -*- coding: utf-8 -*-
"""全量对账：队列理论已发 vs 评论区真实存在的Token评论。
- 统计评论区所有可见的"已消耗 X Token"评论（含每个的@人数）
- 与 top8_progress.json 的"已发组数"对比，找出：
  ① 计入已发但评论区不存在的（可能未发出/被删/审核隐藏）
  ② 名单完整性：每个Token评论实际包含几个@名字（应有10个）
- B站评论总数上限验证：数全部顶层评论数"""
import io, sys, json, time, re, os, urllib.request

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

TOKRE = re.compile(r"已消耗\s*([\d,]+)\s*Token")
# 1) 扫全部顶层评论（翻到底）
all_top = []
cur = 0
pages = 0
while True:
    d = get("https://api.bilibili.com/x/v2/reply/main?type=1&oid=%d&mode=3&next=%d" % (AID, cur))
    dd = d.get("data") or {}
    reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
    if not reps:
        break
    all_top.extend(reps)
    cu = dd.get("cursor") or {}
    cur = cu.get("next", 0)
    pages += 1
    if cu.get("is_end"):
        break
    time.sleep(0.5)

print("== 评论区顶层评论总数: %d（翻%d页）" % (len(all_top), pages))

# 2) Token召唤评论
tok_comments = []
for r in all_top:
    t = ((r.get("content") or {}).get("message") or "")
    m = TOKRE.search(t)
    if m and "召唤魔法" in t:
        tok = int(m.group(1).replace(",", ""))
        at_names = re.findall(r"@([^\u200b@\n]+)", t)
        at_map = (r.get("content") or {}).get("at_name_to_mid") or {}
        tok_comments.append({
            "tok": tok, "rpid": r.get("rpid"), "ctime": r.get("ctime"),
            "names_n": len(at_names), "at_resolved": len(at_map),
            "msg_head": t[:50],
        })
tok_comments.sort(key=lambda x: x["tok"])
print("== Token召唤评论（顶层可见）: %d 条" % len(tok_comments))

# 3) 对照队列已发
prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
queue = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]
i = prog["i"]
sent_groups = queue[:i]
print("== 队列标记已发: %d 组（=%d人）" % (i, i * 10))

# 4) 找出：队列已发但评论区没有的Token
live_toks = {c["tok"] for c in tok_comments}
missing = []
for g in sent_groups:
    if g["tok"] not in live_toks:
        missing.append(g)
print("== 计入已发但评论区查无: %d 组" % len(missing))
for g in missing[:20]:
    names_preview = " ".join(g["names"][:3])
    print("   缺失 Token=%s（%s…）" % ("{:,}".format(g["tok"]), names_preview))

# 5) 每条Token评论的@人数是否满10
bad_count = [c for c in tok_comments if c["names_n"] < 10]
print("== @名字少于10个的Token评论: %d 条" % len(bad_count))
for c in bad_count[:15]:
    print("   Token=%s @数=%d 解析=%d | %s" % ("{:,}".format(c["tok"]), c["names_n"], c["at_resolved"], c["msg_head"]))

# 6) Token 评论里有多少是队列之外的（老批次78,007之前的+手工的等）
sent_toks = {g["tok"] for g in sent_groups}
extra = [c for c in tok_comments if c["tok"] not in sent_toks]
print("== 评论区有但不在本队列已发段内的Token评论: %d 条（含手工/早期批次）" % len(extra))

# 7) 汇总
uniq_people = set()
for c in tok_comments:
    t = None
    for r in all_top:
        if r.get("rpid") == c["rpid"]:
            t = ((r.get("content") or {}).get("message") or "")
    for nm in re.findall(r"@([^\u200b@\n]+)", t or ""):
        uniq_people.add(nm.strip())
print("== 全部Token评论合计@人次: %d，去重后: %d 人" % (sum(c["names_n"] for c in tok_comments), len(uniq_people)))

json.dump({
    "top_total": len(all_top),
    "tok_comments": tok_comments,
    "queue_sent_groups": i,
    "missing_groups": [{"tok": g["tok"], "names": g["names"]} for g in missing],
    "under10": bad_count,
    "uniq_people": len(uniq_people),
}, open(os.path.join(WORK, "audit_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("报告已存 audit_report.json")
