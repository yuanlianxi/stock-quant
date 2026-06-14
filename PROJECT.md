# Stock Quant - 项目总览

> 项目路径：`~/.openclaw/workspace/projects/stock-quant/`

## 基本信息

| 项目 | 值 |
|------|---|
| **项目名称** | Stock Quant |
| **项目路径** | `~/.openclaw/workspace/projects/stock-quant/` |
| **仓库** | Gitee + GitHub 双端同步 |
| **主要语言** | Python |

## 当前状态

| 项目 | 值 |
|------|---|
| **状态** | 进行中 |
| **版本** | v0.18.12（v0.18.10 + 12 hotfix / v0.18.11 pushall 升级 / v0.18.12 0007 D+E 完工 + 2 hotfix）|
| **当前阶段** | 阶段三（前端模块化 v1.6 完工 + 后端 API 模块化 v1.7+sq-0008 完工 + 缓存层优化 v1.7+sq-0009 round-5 收尾）|

## 项目结构

```
stock-quant/
├── notebooks/
│   └── research/           # 研究文档
│       ├── 0001_量化技术调研.md
│       ├── 0002_量化投资案例调研.md
│       ├── 0003_技术栈实操手册.md
│       ├── 0004_策略回测报告.md
│       └── 0005_海龟交易策略深度调研.md
├── scripts/               # 交易脚本
├── data/                  # 数据存储
├── api/                   # FastAPI 服务（v0.8.4 新增）
├── 0001_项目设计.md
├── 0002_技术设计.md
├── 0003_变更日志.md
└── requirements.txt
```

## 研究进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 量化技术调研 | ✅ 完成 | v0.2.0 |
| 量化投资案例调研 | ✅ 完成 | v0.3.0 |
| 技术栈实操手册 | ✅ 完成 | v0.4.0 |
| 策略回测报告 | ✅ 完成 | v0.5.0 |
| 海龟交易策略深度调研 | ✅ 完成 | v0.5.1 |
| T1基金交易系统 | ✅ 完成 | v0.5.3 |

## 飞书知识库

- 父节点：https://openclaw.feishu.cn/wiki/CAmhwOvBLiXhaUkVidccCluDnxg
- **Token 映射表**：详见 `0001_项目设计.md` §2.2

## 最近更新

- 2026-06-14：**v0.18.12** 阶段 — 0007 v1.6 D 联调 + E 切版完工（FastAPI 挂载 webapp dist + /legacy + SPA fallback）+ hotfix1（生产 API 404）+ hotfix2（KLineChart 空数据崩溃）；D 阶段 6 项 curl 验证全过
- 2026-06-11：**v0.18.11** pushall alias 升级（curl → git ls-remote + timeout 20）+ GitHub PAT 安全提醒
- 2026-06-10：**v0.18.10** sq-0009-round-5 收尾（K 线日线支持 + 混合展示，hotfix1-12 共 12 commits）
- 2026-06-08：0007 v1.6 Phase B 基础能力完工（5 store + 8 services + 3 组件 + composables）
- 2026-06-04：**v1.7+sq-0008** 后端 API 模块化完工（main.py 1848→80 行 / 9 域 router / 82 pytest）
- 2026-06-03：v1.6 项目使用文档（README.md）补充，v1.5 遗漏项补救
- 2026-05-26：版本更新到 v0.8.4，FastAPI 框架，position.py skip_adjust 修复
- 2026-05-11：项目迁移到统一项目目录
- 2026-05-07：T1基金交易系统文档完成
- 2026-05-06：版本更新到 v0.8.0

---

## v1.6 项目使用文档

> **v1.5 遗漏项补救**（2026-06-03）

- **SSOT 规范抽取**（避免内容漂移）：README.md 必含 6 大内容**只在** `~/.openclaw/workspace/PROJECT_ZONE.md` §5.4 维护。AGENTS.md / SOUL.md / 本 PROJECT.md 只**引用**，不重复内容。
- **README.md**（项目根）：`/home/yuan/.openclaw/workspace/projects/stock-quant/README.md` —— 实际启动流程 / 47 端点清单 / 飞书链接
- **未来 v2+** 必须在设计阶段规划 README.md，不能遗漏（见 PROJECT_ZONE.md §5.4）。
