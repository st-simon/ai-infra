# AGENTS.md — Agent 注册表与设计决策

本文件记录每个 Agent 的职责、当前状态和关键设计决策，供开发时参考。

---

## Agent 1：新闻简报 (news_briefing) 当前第一目标

**文件：** `agents/news_briefing/agent.py`
**状态：** Phase 1 v2 已实现基础收口；本地邮件草稿和 Gmail 草稿 handoff 已接入
**触发方式：** 手动 / macOS launchd 每日 07:00 / 前台 APScheduler 备用

### 职责
每日抓取四类新闻（政治30% / 财经30% / 科技25% / 加密15%），
生成快而全的 Markdown 简报保存到 `logs/`。

每条新闻目标输出：
- 中文标题
- 2-3 句中文总结
- 原始链接

### LangGraph 节点
```
load_config → fetch_rss → filter_items → summarize → generate_briefing
```

### 关键设计决策
- RSS 抓取用 `httpx`（`trust_env=True`，走系统 VPN 代理），不用 `feedparser` 直连
- 模型调用统一走 `shared/models.py`
- 模型名称通过 `config/model_policy.yaml` 配置化为角色：`fast` / `general` / `reasoner` / `coder` / `embedding`
- 模型执行模式区分：`local_only` / `low_cost` / `auto` / `quality`
- 16GB Mac 默认使用 4B-9B 本地模型；14B 只作为可选质量模式；允许云端 API 作为质量补充
- 新闻来源在 `config/news_sources.yaml` 配置，`enabled: false` 即可关闭
- 新闻 v2 已实现 30/30/25/15 配额、基础去重、多源轮转、按类别批量摘要、来源健康记录和 `--dry-run`
- 每日自动运行优先使用 `docs/SCHEDULING.md` 中的 launchd 方案；`scheduler.py` 保留为前台备用
- 正式运行会生成本地邮件草稿 HTML/EML，并在配置收件人后生成 Gmail 草稿请求；自动发送默认关闭，见 `docs/DELIVERY.md`
- Phase 1 主交付物是 Markdown 简报；HTML/EML/Gmail request 是交付包装和排障产物

### 已知问题 / TODO
- Reuters/AP/BBC RSS 在当前网络环境下连接失败（ConnectError），已有足够替代来源
- Caixin Global 返回 403，暂时禁用
- 完整多模型 benchmark 尚未跑完；当前仅有 `qwen2.5-coder:7b` quick baseline
- Gmail MCP 已验证 labels/drafts/test draft；下一步观察 launchd 自动运行是否生成 Gmail 草稿请求，自动发送需另行确认

---

## Agent 2：工具 Agent (tool_agent)

**文件：** `agents/tool_agent/agent.py`
**状态：** Phase 2 ◐ 最小骨架已启动；reviewed Gmail draft handoff 已接入；本地仍不直接执行账号动作
**依赖：** Gmail MCP、Google Calendar MCP（Codex 中 Gmail 已验证；Calendar 待接入）

### 职责
- 管理日程：安排会议、客户拜访
- 邮件处理：草拟回复、整理收件箱
- 任务提醒：跨应用任务跟踪

### 关键设计决策
- 本地 Python 进程不直接读写 Gmail/Calendar
- `agents/tool_agent/agent.py` 先把自然语言请求转成 `logs/tool_agent_requests/*.json`
- reviewed `email_draft` JSON 可通过 `--gmail-draft-handoff ... --reviewed` 生成 Gmail MCP `create_draft` 参数
- 所有远程账号动作必须经 Codex MCP connector 和用户确认
- 发送邮件、创建日程、归档/删除邮件都不是 Phase 2 骨架的默认行为

---

## Agent 3：研究 Agent (research)

**文件：** `agents/research/agent.py`
**状态：** Phase 3 🔲 待开发
**依赖：** ChromaDB（`memory/chromadb/`）

### 职责
- 收集并存储特定领域资料（加密货币、工业 AI 等）
- 跨会话知识积累，支持"上周研究了什么"式查询
- 按需生成深度研究报告

---

## Agent 4：审议式多模型 (deliberation)

**文件：** `agents/deliberation/agent.py`
**状态：** Phase 4 🔲 待开发（代码框架已有）

### 职责
- 工业 AI 项目框架设计
- 复杂决策的多角度提案 + 交叉审议 + 综合

---

## 共享组件

### `shared/models.py`
- `chat(role, prompt, num_ctx, thinking)` — 单轮对话
- `chat_with_history(role, messages, num_ctx, thinking)` — 多轮对话
- `role` 映射：`reasoner=qwen35-fast`，`generalist=qwen35-fast`，`coder=qwen2.5-coder:7b`
- 所有请求 `trust_env=False`（避免系统代理干扰本地 Ollama）
- 输出自动清理 `</think>` 残留

### 模型选用原则
| 任务类型 | 推荐 role | 原因 |
|----------|-----------|------|
| 翻译、格式转换 | coder | 无 thinking，快速干净 |
| 摘要、分类 | coder | 同上 |
| 推理、分析 | reasoner | 需要深度 |
| 代码生成 | coder | 专项优化 |
| 审议综合 | reasoner | 需要判断力 |
