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
| **版本** | v0.8.4 |
| **当前阶段** | 阶段二（回测 + VN.py对接） |

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
