# -*- coding: utf-8 -*-
"""首次使用初始化：检查必需文件，缺失的生成模板（道歉模板/空队列/空状态），
生成 session.json 占位并提示扫码登录。这样别人克隆仓库后能直接跑。"""
import io, sys, json, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))

def need(name, maker):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        maker(p)
        print("已生成模板:", name)
    else:
        print("已存在:", name)

def mk_apologies(p):
    # 生成2个简版模板（真正跑之前建议跑 build_apologies.py 生成10版完整模板）
    base = "@{name} 您好！您的111已经收到，非常抱歉这次召唤打扰到了您。正如承诺的那样，您的名字已经从召唤名单中永久移除，今后无论发动多少次召唤魔法，都不会再@您，请放心。这次召集本意只是想找到同样喜欢这部作品的朋友，一起聊聊，但方式确实唐突了。感谢您愿意花一条评论来告知。愿您以后刷到的每一条视频都合心意，每一份热爱都不被辜负。祝您生活顺利，天天开心！另外说明一下：您不需要再做任何操作，退订即刻生效，也不会有任何后续打扰。如果哪天您又想被召唤了，随时回来留一句话，名册永远为您留一页空白。打扰这种事，说一次就是失礼，我们不会犯第二次。感谢您愿意用一条评论来告知，而不是默默划走，这份直率也很好。愿您以后刷到的每一条视频都合心意，每一个深夜都有好番陪伴。祝您生活顺利，学业工作顺心，天天都能遇到值得开心的小事。"
    json.dump({"apologies": [base]}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def mk_queue(p):
    json.dump({"queue": []}, open(p, "w", encoding="utf-8"), ensure_ascii=False)

def mk_prog(p):
    json.dump({"i": 0, "last_tok": 0, "posted": 0, "posted_n": 0, "fails": 0},
              open(p, "w", encoding="utf-8"), ensure_ascii=False)

def mk_state(p):
    json.dump({"sent_set": [], "remaining": []}, open(p, "w", encoding="utf-8"), ensure_ascii=False)

def mk_apology_state(p):
    json.dump({"done_rpids": [], "done_names": [], "count": 0, "fails": {}},
              open(p, "w", encoding="utf-8"), ensure_ascii=False)

def mk_target(p):
    json.dump({"url": "https://www.bilibili.com/video/BV1VdHE6PEEa", "aid": 117384258060764},
              open(p, "w", encoding="utf-8"), ensure_ascii=False)

def mk_flag(p):
    open(p, "w", encoding="utf-8").write("STOP")

def mk_apology_flag(p):
    open(p, "w", encoding="utf-8").write("RUN")

def mk_session(p):
    json.dump({"SESSDATA": "", "bili_jct": "", "DedeUserID": "", "buvid3": ""},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    need("apologies.json", mk_apologies)
    need("top5_queue.json", mk_queue)
    need("top8_progress.json", mk_prog)
    need("sent_state.json", mk_state)
    need("apology_state.json", mk_apology_state)
    need("target.json", mk_target)
    need("flag.txt", mk_flag)
    need("apology_flag.txt", mk_apology_flag)
    need("session.json", mk_session)
    print("\n初始化完成！接下来：")
    print("1. 双击 start_panel.bat 或运行 python qr_login_new.py 扫码登录")
    print("2. 用 probe_new_fans.py / merge_new_fans.py 或手工构建你的 top5_queue.json（10人/组）")
    print("3. start_panel.bat → 拉取 → 开始发送")
