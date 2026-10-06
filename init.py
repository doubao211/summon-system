# -*- coding: utf-8 -*-
"""首次使用初始化：生成空白数据模板（run.bat 会自动执行，无需手动跑）。"""
import io, sys, json, os
if sys.stdout and getattr(sys.stdout, "buffer", None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))

def need(rel, data):
    p = os.path.join(BASE, rel)
    if os.path.exists(p):
        print("已存在:", rel)
        return
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d)
    if isinstance(data, str):
        open(p, "w", encoding="utf-8").write(data)
    else:
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已生成模板:", rel)

if __name__ == "__main__":
    need("top5_queue.json", {"queue": []})
    need("top8_progress.json", {"i": 0, "last_tok": 0, "posted": 0, "posted_n": 0, "fails": 0})
    need("sent_state.json", {"sent_set": [], "remaining": [], "max_token": 0})
    need("target.json", {"url": "", "aid": 0})
    need("flag.txt", "STOP")
    need("sender_config.json", {"interval": 35, "batch": 10})
    need("data/users_master.json", {})
    print("初始化完成！")
