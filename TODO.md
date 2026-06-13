# TODO — 项目待办

## Phase 1：新闻简报 v2 当前第一目标

- [x] RSS 抓取（httpx + feedparser）
- [x] 四类新闻按权重筛选（政治30% / 财经30% / 科技25% / 加密15%）
- [x] AI 翻译标题
- [x] Markdown 简报输出
- [x] 每条新闻输出：中文标题 + 2-3 句中文总结 + 原始链接
- [x] 批量摘要/翻译，减少逐条模型调用开销
- [x] 模型角色配置化（fast / general / reasoner / coder / embedding）
- [x] 新闻去重（同一事件多源报道合并）
- [x] 来源健康记录（成功、超时、403、解析失败）
- [x] APScheduler 或 launchd 每日定时运行（早上 7:00 BJT）
- [x] 简报发送到指定位置（本地邮件草稿 HTML / EML）
- [x] Gmail MCP 可用后创建 Gmail 草稿
- [x] 正式运行生成 Gmail 草稿请求（Codex/Gmail MCP draft-only handoff）
- [x] 增加 `.env.example`，明确 `AI_INFRA_BRIEFING_TO` 等本地配置
- [ ] 观察下一次 launchd 自动运行是否生成 Gmail 草稿请求
- [ ] 草稿模式验证后再决定是否每日自动发送

## Phase 1 基础设施收口

- [x] 记录本地+云端混合模型策略与执行顺序（见 `docs/MODEL_POLICY.md`）
- [x] 重建 `.venv`，修复旧路径残留
- [x] 增加 `requirements.txt` 或 `pyproject.toml`
- [x] 增加 `.gitignore`，排除 `.DS_Store`、`__pycache__`、运行日志、`.env`
- [x] 增加 dry-run / smoke test，避免验证时写入新简报

## 模型策略与评估

- [x] 盘点本机已下载模型
- [x] 根据最新模型发展现况列出候选替换模型
- [x] 设计项目任务基准测试：新闻翻译、2-3 句摘要、分类、去重、加密监管摘要、工业 AI 路线分析、长文本综合、格式稳定性、速度和内存
- [x] 运行本地 `qwen2.5-coder:7b` quick baseline（见 `docs/local_model_benchmark_quick.json`）
- [ ] 运行完整多模型项目任务基准测试
- [ ] 根据基准结果决定是否替换当前默认本地模型
- [x] 实现 `shared/models.py` 的 role/mode 策略层：`fast` / `general` / `reasoner` / `coder` / `embedding` + `local_only` / `low_cost` / `auto` / `quality`
- [x] 保持云端 provider / model 可配置，不在 Agent 逻辑中写死

## Phase 2：工具 Agent 🔲

- [x] LangGraph 图骨架
- [x] 本地工具请求 JSON handoff（不直接执行 Gmail/Calendar）
- [x] 接入 Gmail MCP（邮件读取、草稿）
- [x] 从 reviewed Tool Agent JSON 准备 Gmail MCP 草稿创建 handoff（不发送）
- [ ] 接入 Google Calendar MCP（日程查询、创建）
- [ ] 自然语言日程管理（"下周三下午安排客户拜访"）
- [ ] 任务清单管理

## Phase 3：研究 Agent 🔲

- [x] 明确本地模型与云端顶级模型的混合策略（见 `docs/MODEL_POLICY.md`）
- [ ] ChromaDB 初始化
- [ ] 文档摄取流水线（PDF / 网页 / 文章）
- [ ] 跨会话记忆存储
- [ ] 加密货币专题知识库
- [ ] 按需研究报告生成
- [ ] 深度分析和报告生成节点支持 `quality` 模式

## Phase 4：审议式多模型 🔲

- [ ] 适配 16GB 内存（双模型方案）
- [ ] 与工业 AI 咨询场景对接
- [ ] 质量门控调优
- [ ] 最终审议综合者支持 `quality` 模式和可配置云端高级模型

## 基础设施

- [ ] 环境变量 Ollama 设置（`OLLAMA_MAX_LOADED_MODELS=1`）
- [ ] 统一日志格式
- [ ] 错误告警机制
