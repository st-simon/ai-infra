# Personal AI Infrastructure

个人 AI 基础设施——本地优先、云端可选的多 Agent 系统。当前第一目标是把“每日新闻”做成稳定、快速、覆盖面广的日常工作流。

## 当前优先级

1. 每日新闻简报：快而全，每条新闻包含中文标题、2-3 句中文总结、原始链接。
2. 研究 Agent：加密货币、工业 AI，后续单独讨论本地/顶尖模型 API 的混合方案。
3. 工具 Agent：Gmail / Calendar 等云端能力可接受，但要先明确授权和隐私边界。

## 硬件与模型

| 项目 | 规格 |
|------|------|
| 设备 | MacBook Pro M4，16GB 统一内存 |
| 推理框架 | Ollama 0.18.3 |
| 主模型 | qwen3.5:9b / qwen35-fast（本地默认） |
| 代码/工具模型 | qwen2.5-coder:7b |

模型策略：16GB 统一内存下默认使用 4B-9B 本地模型，14B 只作为可选质量模式，27B+ 不作为常规本地路径。模型名称应通过配置映射到 `fast` / `general` / `reasoner` / `coder` / `embedding` 等角色，便于后续升级。

## Agent 架构

```
ai-infra/
├── agents/
│   ├── news_briefing/      # Phase 1 ✅ 每日新闻简报
│   ├── tool_agent/         # Phase 2 🔲 Gmail + Calendar
│   ├── research/           # Phase 3 🔲 RAG 深度研究
│   └── deliberation/       # Phase 4 🔲 审议式多模型
├── shared/
│   └── models.py           # 统一模型调用接口
├── memory/
│   └── chromadb/           # 本地向量数据库
├── config/
│   └── news_sources.yaml   # 新闻来源配置
└── logs/                   # 简报输出目录
```

## 快速开始

```bash
cd ~/codex-projects/projects/ai-infra
source .venv/bin/activate

# 运行每日简报
python agents/news_briefing/agent.py

# dry-run 验证，不写入 logs/
python agents/news_briefing/agent.py --dry-run
```

## 每日自动运行

macOS 默认使用 `launchd` 定时运行：

```bash
scripts/install_daily_briefing_launchd.sh
```

详见 `docs/SCHEDULING.md`。

## 环境变量

见 `.env` 文件（不纳入版本控制）。

## 开发规范

- 所有模型调用通过 `shared/models.py` 的 `chat()` / `chat_with_history()` 接口
- 翻译/摘要等简单任务使用 `role="coder"`（无 thinking，速度快）
- 复杂推理使用 `role="reasoner"`
- 每个 Agent 是独立的 LangGraph 图，状态用 `TypedDict` 定义

## 关键文档

- `DECISIONS.md`：长期设计决策
- `docs/SCHEDULING.md`：每日自动运行、launchd 安装与排查
- `docs/MODEL_POLICY.md`：本地+云端混合模型策略与执行顺序
- `docs/LOCAL_MODEL_EVALUATION.md`：本地模型盘点、候选方向和基准测试计划
- `docs/2026-06-07-ai-infra-audit.md`：本次审核结论与后续路线
- `../../codex-workspace-governance/skills/project-intake/SKILL.md`：适用于所有项目的软件/AI 项目创建与审核流程 skill
