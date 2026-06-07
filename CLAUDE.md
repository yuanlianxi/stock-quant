# CLAUDE.md - Claude Code 项目工作上下文

> 项目：Stock Quant（股票量化）
> 最后更新：2026-06-07

---

## 项目元信息

| 字段 | 值 |
|------|---|
| 名称 | Stock Quant（股票量化）|
| 路径 | (本目录) |
| 版本 | v0.18.4（v1.6 含 README.md 补救）|
| 状态 | 进行中（FastAPI 后端已模块化拆分）|
| 语言 | Python 3.11+ |
| 框架 | FastAPI + SQLAlchemy + Pandas + pytest |
| 仓库 | Gitee + GitHub 双端（nowcrown/stock-quant, yuanlianxi/stock-quant）|
| 飞书父节点 | `CAmhwOvBLiXhaUkVidccCluDnxg`（Space ID: `7615250576154037472`）|

## 引导词策略

> 本 CLAUDE.md 是 Claude 进入本项目的引导词。**进入项目时按以下 6 个必选文档顺序阅读**：

| 顺序 | 文档 | 用途 |
|------|------|------|
| 1 | `CLAUDE.md`（本文件）| 项目工作上下文 |
| 2 | `0001_项目设计.md` | 项目设计（含飞书 Token 集中清单 §2.2）|
| 3 | `0002_技术设计.md` | 技术方案与模块设计 |
| 4 | `0003_变更日志.md` | 变更记录（变更频繁，使用前看末尾最新版本）|
| 5 | `PROJECT.md` | 项目总览 |
| 6 | `README.md` | 使用文档（启动流程 / 47 端点清单 / 飞书链接）|

> **忽略 `SOUL.md`**：项目人格文件保留在仓库但不参与引导词阅读。
>
> 详细模块设计（按需读取）：`0004-0008_*.md` / `_requirements/<需求名>/01-design/`

## 新需求判定（询问式）

> 本节定义"新需求出现时 Claude 如何询问用户"。**强制规则**：必须先询问，不允许跳过。

**触发询问的两种场景**（满足任一即主动询问用户）：

**场景 A**：新需求 ∉ 当前需求范围
- 当前 `_requirements/` 下任何需求都不在"计划/执行/验收"阶段
- 新需求被提出时，**必须**先询问用户

**场景 B**：所有当前需求已结束
- 当前 `_requirements/` 下所有需求 `feedback.md` 决策 = `closed`
- 新需求被提出时，**必须**先询问用户

**询问模板**（**固定格式，不允许跳过**）：

```
🔔 新需求检测：检测到新需求"X"

📊 当前 _requirements/ 状态：
- <需求 1>：阶段 = <阶段>（决策 = <closed/iterate: v1.X+/blocked>）
- <需求 2>：阶段 = <阶段>（决策 = ...）

❓ 请选择（必须先选才能继续）：
A. 开启独立 _requirements/sq-新需求名/  （前提：所有当前需求都已 closed）
B. 作为现有需求的 _iterations/v1.X+sq-新需求名/
C. 不开 _requirements/，直接走 000X_xxx.md 主设计文档（一次性小需求）
```

**强制规则**：
- **必须**等待用户明确选择 A/B/C 才能继续
- **禁止**默认"按推荐方案"自动建
- **禁止**"先建了再说"

**结构硬性要求**（一旦选 A）：`_requirements/<需求名>/` 下必须用 `01-design/02-plan/03-execution/04-verification` 4 个数字目录（**不是** phase-a/b/c/d/e 派发目录）

> 详细规范见 workspace 根 `PROJECT_ZONE.md §八` + `PROJECT_COLLAB_RULES.md §X`

## 项目内规范（必读）

| 任务 | 文档 |
|------|------|
| 了解项目 | `0001_项目设计.md`（含飞书 Token 集中清单 §2.2）|
| 改代码 | `0002_技术设计.md` |
| 查变更 | `0003_变更日志.md`（变更频繁，使用前看末尾最新版本）|
| 数据源 | `0004_数据源设计.md` |
| 海龟信号 | `0005_海龟信号监控设计.md` |
| 数据模型 | `0006_数据模型与界面重构设计.md` |
| 前端模块化 | `0007_前端模块化重构设计.md` |
| 后端 API | `0008_后端API模块化拆分设计.md` |
| 使用文档 | `README.md`（启动流程 / 47 端点清单 / 飞书链接）|
| 需求追踪 | `_requirements/<需求名>/01-design/` |

## 项目真实结构

```
stock-quant/
├── api/                   # FastAPI 后端（v0.18.x 模块化拆分后）
│   ├── routers/           # 9 域 router（signal/cache/position/account/market/backtest/turtle/strategy/session）
│   ├── schemas/           # 8 个 Pydantic schemas
│   ├── state.py           # 共享状态
│   ├── helpers.py
│   └── main.py            # 入口（80 行）
├── backtest/              # 回测引擎
│   └── backtest_engine.py
├── notebooks/
│   └── research/          # 调研文档（0001-0015+）
├── data/                  # 数据存储
├── config/                # 配置文件
├── scripts/               # 交易脚本
├── tests/                 # pytest 测试（69 单测 + 13 集成）
├── _requirements/         # 多需求管理
├── 0001_项目设计.md       # [必选]
├── 0002_技术设计.md       # [必选]
├── 0003_变更日志.md       # [必选]（85KB，最详细）
├── 0004-0008_*.md         # 模块设计
├── CLAUDE.md              # [必选] 本文件
├── PROJECT.md             # [必选]
├── SOUL.md                # [忽略] 保留在仓库但不参与引导词阅读
├── README.md              # [必选] 项目使用文档（26KB）
├── requirements.txt
├── pytest.ini
└── .gitignore
```

## 架构设计

- **核心**：FastAPI 股票量化研究/回测/海龟交易策略系统
- **模块**（9 域 API）：
  - **signal**（信令）：股票信号管理
  - **cache**（缓存）：缓存层
  - **position**（仓位）：仓位管理
  - **account**（账户）：账户中心（v0.18 Phase 5）
  - **market**（市场）：市场数据
  - **backtest**（回测）：回测引擎 + 任务调度
  - **turtle**（海龟）：海龟交易策略监控
  - **strategy**（策略）：策略管理
  - **session**（会话）：会话管理
- **数据流**：
  ```
  行情数据 → 数据源 → backtest_engine → 信号生成 → signal API → 前端展示
                                    ↓
                              海龟策略 → turtle API → 实时监控
  ```
- **依赖**：FastAPI 0.110+、SQLAlchemy 2.x、Pandas、pytest、locust（性能测试）
- **数据库**：SQLite（轻量级），预留 PostgreSQL 迁移路径

## 架构设计规范

- **命名规范**：
  - 文件名：`snake_case.py`
  - 类名：`PascalCase`
  - 函数/变量：`snake_case`
  - 常量：`UPPER_SNAKE_CASE`
- **模块边界**：
  - `api/routers/` 一个域一个文件（9 域对应 9 router）
  - `api/schemas/` 一个域一个 Pydantic schemas
  - `api/state.py` 集中管理共享状态（避免循环 import）
  - `data/` 只放数据，不放代码
- **接口设计**：
  - RESTful 风格
  - 入参出参用 Pydantic schemas（`api/schemas/`）
  - 错误统一为 `HTTPException(status_code, detail)`
  - 所有端点有 docstring 说明
- **错误处理**：
  - 业务异常自定义 `BusinessException`
  - 全局异常处理 `app.exception_handler`
- **测试规范**：
  - 单元测试 `tests/unit/`，覆盖核心函数（`sim_engine` 80% 覆盖率）
  - 集成测试 `tests/integration/`，端到端 13 个场景
  - 性能基线：100 session < 1s，100 调价 < 0.5s

## 项目协作规范大纲

> 完整规范在 workspace 根目录，Claude 实施前可按需读完整文件（绝对路径）。

### PROJECT_COLLAB_RULES.md

**路径**：`~/.openclaw/workspace/PROJECT_COLLAB_RULES.md`

**关键规范**（执行前必读）：

- **§一 三阶执行**：所有项目任务必须走"设计→审核→执行"，先出设计文档等用户确认才能执行
- **§二 设计前置**：5 条适用范围（项目任务 / workspace 根 .md / ~/projects/ / Cron / 飞书同步），4 类必审批变更（Cron / 协作规范 / 项目区 / 飞书同步）
- **§三 Git 双端推送**：Gitee + GitHub + `git pushall`；⚠️ `hexo init` / `npm init` 覆盖 .git 危险
- **§四 飞书同步**：Node Token（结构）vs Obj Token（内容）；前置检查清单；本项目飞书 Token 在 `0001_项目设计.md` §2.2 集中清单
- **§五 文档序号**：4 位；**必选 = 0001/0002/0003/CLAUDE.md**
  > ⚠️ **本项目例外**：引导词按 6 个，详见顶部「引导词策略」
- **§六 变更日志**：每次变更必更新（版本/日期/类型/内容）；本项目 0003 已有 85KB 详细历史
- **§七 执行计划追踪**：Phase 状态 ⏳→🔄→✅→❌

### PROJECT_ZONE.md

**路径**：`~/.openclaw/workspace/PROJECT_ZONE.md`

**关键规范**（执行前必读）：

- **§一 项目区定义**：隔离、自包含、可移植、可继承、可覆盖
- **§二 项目区结构**：必选文件 = SOUL.md / PROJECT.md / 0001/0002/0003/CLAUDE.md / README.md
  > ⚠️ **本项目例外**：引导词按 6 个，忽略 SOUL.md，详见顶部「引导词策略」
- **§三 项目生命周期**：初始化中→进行中→暂停中→已完成→已归档
- **§四 安全边界**：禁止跨项目写文件；危险命令（rm/dd/fork bomb）禁止
- **§五 继承优先级**：项目 CLAUDE.md > PROJECT_ZONE > PROJECT_COLLAB_RULES（项目文档按需读取）
- **§七 项目使用文档**：README.md 必含 6 大内容（本项目 README.md 已含全部）
- **§八 _requirements 目录**：多需求项目的子目录结构（本项目已用）

### 何时读完整文件

- 实施某条规范前**不确定细节** → Read 对应文件对应章节
- 提交前自查**漏改条目** → 通读相关章节

## 已知约束 / 坑

- ⚠️ **飞书 Token 集中存储在 `0001_项目设计.md` §2.2**，不要在其他文档散落
- ⚠️ `0003_变更日志.md` 已 85KB，**改之前看末尾确认最新版本号**（避免版本号冲突）
- ⚠️ `main.py` 是入口（80 行），业务逻辑在 `api/routers/` 9 个域文件中
- ⚠️ **回测是 CPU 密集型**（100 session 0.84s），不要在前端直接调用
- ⚠️ **GitHub push 不稳定**（HTTPS hang），失败时检查后用 Gitee 单端推送兜底
- ⚠️ **v1.5 教训**：项目完工时遗漏了 README.md，v1.6 补救——未来版本设计阶段就规划 README

## 不要做

- ❌ 修改 `~/.openclaw/workspace/*.md`（只读，那是 OpenClaw 管的）
- ❌ 删文件不确认
- ❌ force push 到 main/master
- ❌ 直接给用户发飞书消息
- ❌ 在 `0003_变更日志.md` 中间插版本记录（永远 append 到末尾）
- ❌ 散落飞书 Token 到多个文件（必须在 `0001_项目设计.md` §2.2）
