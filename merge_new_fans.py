# -*- coding: utf-8 -*-
import io, sys, json, random, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = r"E:\欧尼酱_召唤工作区"
TITLE = "⚡大型召唤魔法发动中⚡"
APOLOGY = "如果你被打扰了，那么很抱歉，请在本条评论下方回复111，以后将不会再打扰您。"

t0 = time.time()
prog = json.load(open(os.path.join(WORK, "top8_progress.json"), encoding="utf-8"))
print("prog loaded", time.time() - t0, flush=True)
queue = json.load(open(os.path.join(WORK, "top5_queue.json"), encoding="utf-8"))["queue"]
print("queue loaded %d" % len(queue), time.time() - t0, flush=True)
st = json.load(open(os.path.join(WORK, "sent_state.json"), encoding="utf-8"))
remaining = st["remaining"]
print("remaining %d" % len(remaining), time.time() - t0, flush=True)

i = prog["i"]
sent_names = set()
for g in queue[:i]:
    sent_names.update(g["names"])
old_unsent = []
for g in queue[i:]:
    old_unsent.extend(g["names"])
print("sent=%d old_unsent=%d" % (len(sent_names), len(old_unsent)), time.time() - t0, flush=True)

unsent = [n for n in remaining if n not in sent_names]
# 剔除线上已@过的人（扫描自己视频全部可见评论里的@名字，防重复）
import urllib.request, re as _re
ck = json.load(open(os.path.join(WORK, "session.json"), encoding="utf-8"))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
     "Referer": "https://www.bilibili.com/video/BV1VdHE6PEEa",
     "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items() if v)}
live = set()
cur2 = 0
for pg in range(60):
    try:
        rq = urllib.request.Request("https://api.bilibili.com/x/v2/reply/main?type=1&oid=117384258060764&mode=3&next=%d" % cur2, headers=H)
        d = json.loads(urllib.request.urlopen(rq, timeout=15).read())
    except Exception:
        break
    dd = d.get("data") or {}
    reps = (dd.get("replies") or []) + (dd.get("top_replies") or [])
    if not reps:
        break
    for r_ in reps:
        t = ((r_.get("content") or {}).get("message") or "")
        for m in _re.findall(r"@([^\u200b@\n]+)", t):
            live.add(m.strip())
        for sub in (r_.get("replies") or []):
            t2 = ((sub.get("content") or {}).get("message") or "")
            for m in _re.findall(r"@([^\u200b@\n]+)", t2):
                live.add(m.strip())
    cu = dd.get("cursor") or {}
    cur2 = cu.get("next", 0)
    if cu.get("is_end"):
        break
    time.sleep(0.5)
print("live已@名字(含历史)=%d" % len(live), flush=True)
unsent = [n for n in unsent if n not in live]
uset = set(unsent)
oset = set(old_unsent)
lost = [n for n in old_unsent if n not in uset]
gained = [n for n in unsent if n not in oset]
print("unsent=%d 丢失=%d 新增=%d" % (len(unsent), len(lost), len(gained)), flush=True)
if lost:
    print("丢失:", lost[:15], flush=True)

tok = prog["last_tok"]
random.seed()
new_groups = []
k = 0
while k < len(unsent):
    ch = unsent[k:k + 10]; k += 10
    tok += random.randint(800, 1300)
    text = TITLE + " 已消耗 {:,} Token ".format(tok) + " ".join("@" + n for n in ch) + " " + APOLOGY
    if len(text) > 999:
        text = text[:996] + "…"
    new_groups.append({"tok": tok, "names": ch, "text": text})
print("groups built", time.time() - t0, flush=True)

final = queue[:i] + new_groups
tmp = os.path.join(WORK, "top5_queue.json.tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"queue": final}, f, ensure_ascii=False)
os.replace(tmp, os.path.join(WORK, "top5_queue.json"))
print("saved. total=%d (sent %d / unsent %d) elapsed=%.1fs" % (len(final), i, len(new_groups), time.time() - t0), flush=True)
lens = [len(g["text"]) for g in new_groups]
print("未发文本 %d~%d 超限=%d" % (min(lens), max(lens), sum(1 for x in lens if x > 999)))
print("下一条(第%d组):" % (i + 1))
print(final[i]["text"][:150])
print("最后Token: {:,}".format(new_groups[-1]["tok"]))
