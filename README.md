# onimai-summon-system（欧尼酱召唤系统）

B站评论区"@召唤同好"自动化工具包：批量@召唤 + 111退订自动道歉 + 新粉丝探测，全图形界面控制。

## ⚠️ 免责声明
本项目仅供学习交流自动化技术。请遵守B站社区规则与用户意愿（"回复111退出"机制是本系统的核心承诺）。请自行控制发送频率。

## 快速开始

```bash
# 1) 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2) 初始化（自动生成配置模板）
python init.py

# 3) 扫码登录B站（浏览器自动弹出二维码）
python qr_login_new.py

# 4) 打开控制面板（图形界面）
双击 start_panel.bat   # 召唤发送面板：链接框→拉取→开始发送
双击 start_watch.bat   # 道歉监测面板：每5~6分钟体检评论区，自动道歉@退订者
```

## 组件

| 文件 | 说明 |
|---|---|
| `summon_panel.py` | 召唤发送控制台（GUI）：视频链接拉取/开始/停止/实时计数 |
| `top8_slow.py` | 发送引擎：每条评论@10人，30~45秒一条，断点续传，hidden节流自动兜底 |
| `apology_watch_gui.py` | 道歉监测台（GUI）：5~6分钟/轮体检，含"1"即判退订，@他发道歉，每分钟1人 |
| `probe_new_fans.py` | 探测新视频/新评论用户入库 |
| `incremental_probe.py` | 增量探测（含暂停/恢复发送器编排逻辑） |
| `merge_new_fans.py` | 新用户并入发送队列（线上已@名单全量去重） |
| `build_apologies.py` | 生成10个900~1000字节道歉模板 |
| `dedup_apologies.py` | 清理重复道歉（保最早删其余+错位道歉删除） |
| `audit_sendings.py` | 对账：队列已发 vs 评论区真实可见 |
| `find_missed.py` | 找出漏发的人（从未成功@过） |
| `check_who.py` | 检查当前浏览器登录态归属 |
| `qr_login_new.py` | 扫码登录（浏览器方案，自动提取cookie） |
| `init.py` | 首次使用初始化（生成全部配置模板） |
| `cdp.py` | CDP浏览器调试驱动 |

## 数据文件（`.gitignore` 已排除，勿上传）

`session.json`（登录凭据）· `top5_queue.json`（发送队列）· `top8_progress.json`（进度）·
`sent_state.json`（去重名单）· `apologies.json`（道歉模板）· `apology_state.json`（道歉进度）·
`target.json`（目标视频）· `edge_profile/`（浏览器配置）

## 技术原理速记

- 评论区是Web组件（300+ shadowRoot），必须深度遍历
- **纯文本`@名字 `即可被服务器自动解析成真实@**，无需@面板选人
- **真实键鼠输入（CDP Input域）才会激活B站状态机**；纯JS focus+execCommand会让发布按钮挂hidden类
- hidden节流兜底：js移除hidden类+jsClick（实测有效）
- 每条最多@10个不同用户（B站硬限）
- 单用户单视频评论可见上限：超快频率/文案突变会被审核池吞（编辑器清空≠发出，必须API回读验证）
- 道歉绝不重复：state去重+每轮API实扫已发道歉双保险

## License

MIT
