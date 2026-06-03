# 项目结构：4 大功能模块 + 目录树

> 文档版本：v1.5
> 创建日期：2026-06-03
> 修订日期：2026-06-03
> 负责人：Alex + Blex
> 状态：✅ 完成

> **本文档是 `0006_数据模型与界面重构设计.md` 的"项目结构视角"补充**。从目录树 + 模块职责 + 依赖关系的角度描述项目代码组织。

---

## 一、项目目录树（当前实际 + v1.5 设计目标）

```
stock-quant/
├── 0001_项目设计.md                # 顶层项目设计（历史）
├── 0002_技术设计.md                # 技术栈选型
├── 0003_变更日志.md                # 全局变更日志
├── 0004_数据源设计.md              # 数据源设计（v1.0）
├── 0005_海龟信号监控设计.md        # 海龟信号监控（v1.0）
├── 0006_数据模型与界面重构设计.md  # ★ 主设计文档（v1.5 最新）
├── 0006_数据模型与界面重构设计.v1.3.bak.md  # v1.3 备份
├── PROJECT.md                      # 项目元信息
├── SOUL.md                         # 项目原则 / 风格
├── requirements.txt                # Python 依赖
│
├── data/                           # 【数据层】领域 1：合约行情
│   ├── data_loader.py              # 数据同步服务（Sina / AkShare）
│   └── futures_akshare.db          # SQLite 数据库（22 张表）
│
├── api/                            # 【API 层】FastAPI 后端服务
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口（路由注册 + 中间件）
│   ├── routes/                     # ★ v1.5 拆分：路由层
│   │   ├── accounts.py             # /accounts
│   │   ├── strategies.py           # /strategies
│   │   ├── contracts.py            # /contracts /quotes
│   │   ├── sessions.py             # ★ v1.4 新增：/session
│   │   ├── trading.py              # /sim/orders /sim/trades
│   │   ├── backtest.py             # /backtest/runs
│   │   └── lines.py                # ★ v1.3 新增：/session/{id}/lines
│   ├── services/                   # ★ v1.5 拆分：服务层（3 大引擎）
│   │   ├── sim_engine.py           # 撮合引擎
│   │   ├── session_lifecycle.py    # ★ v1.4 新增：Session 生命周期管理器
│   │   ├── line_calculator.py      # ★ v1.3 新增：价格线计算服务
│   │   └── event_logger.py         # ★ v1.4 新增：事件流写入服务
│   ├── models/                     # ★ v1.5 拆分：数据模型（SQLAlchemy ORM）
│   │   ├── base.py                 # Base
│   │   ├── futures.py              # 合约行情 4 张表
│   │   ├── strategy.py             # 策略 6 张表
│   │   ├── trading.py              # 交易账户 10 张表
│   │   └── backtest.py             # 跨领域 1 张表
│   ├── schemas/                    # ★ v1.5 拆分：Pydantic schemas
│   │   ├── session.py              # Session / Order / Trade / Unit
│   │   ├── line.py                 # PriceLine
│   │   └── signal.py               # Signal
│   └── db/                         # ★ v1.5 拆分：数据库连接
│       ├── __init__.py
│       └── session.py              # async_session
│
├── strategies/                     # 【策略层】领域 2：策略代码
│   ├── __init__.py
│   ├── base.py                     # ★ v1.3 新增：BaseStrategy 抽象基类
│   ├── loader.py                   # ★ v1.3 新增：策略动态加载器
│   ├── turtle/                     # 海龟策略
│   │   ├── __init__.py
│   │   ├── factors.py              # calc_atr / calc_breakout_55（v1.0 旧版）
│   │   ├── position.py             # 持仓管理（v1.0 旧版）
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_turtle_unit.py # Unit 单元测试
│   │   ├── V1/                     # ★ v1.3 新增：多版本目录
│   │   │   ├── __init__.py
│   │   │   ├── strategy.py         # TurtleV1Strategy
│   │   │   ├── factors.py          # 因子计算
│   │   │   ├── position.py         # 持仓管理
│   │   │   ├── signal.py           # 信号检测
│   │   │   └── default_params.json # 默认参数
│   │   └── V2/                     # ★ v1.3 预留：实验性版本
│   │       ├── __init__.py
│   │       ├── strategy.py         # TurtleV2Strategy
│   │       └── ...
│   ├── dual_ma/                    # ★ v1.3 预留：双均线策略
│   │   └── V1/
│   │       ├── __init__.py
│   │       └── strategy.py         # DualMAV1Strategy
│   └── breakout/                   # ★ v1.3 预留：突破策略
│       └── V1/
│           └── strategy.py
│
├── backtest/                       # 【回测引擎】跨领域
│   ├── __init__.py
│   ├── backtest_engine.py          # 回测主引擎
│   ├── config.py                   # 回测配置
│   └── data_loader.py              # 回测数据加载
│
├── scripts/                        # 工具脚本
│   ├── run_backtest.py             # 跑回测入口
│   ├── test_engine.py              # 引擎测试
│   └── migrate.py                  # ★ DB migration 工具
│
├── config/                         # 配置文件
│   └── instruments.yaml            # 品种配置
│
├── vnpy_strategies/                # 【可选】vnpy 对接
│   └── cta_strategies/
│       ├── ctp_config_guide.md     # CTP 配置指南
│       └── dual_ma_strategy.py     # vnpy 双均线策略
│
├── www/                            # 【前端层】Vite + React/Vue
│   ├── index.html                  # 单页面应用入口
│   ├── package.json                # 依赖
│   ├── vite.config.ts              # Vite 配置
│   ├── src/
│   │   ├── main.ts                 # 入口
│   │   ├── App.tsx                 # 根组件
│   │   ├── api/                    # ★ 前端 API 客户端
│   │   │   ├── client.ts           # axios 实例 + 拦截器
│   │   │   ├── sessions.ts         # Session API
│   │   │   ├── strategies.ts       # Strategy API
│   │   │   ├── lines.ts            # PriceLine API
│   │   │   └── ...
│   │   ├── components/             # ★ 组件
│   │   │   ├── TopBar.tsx          # 顶部栏
│   │   │   ├── KLineChart.tsx      # K 线图（核心组件）
│   │   │   ├── PriceLineLayer.tsx  # 价格线层
│   │   │   ├── DraggableLine.tsx   # 可拖动价格线
│   │   │   ├── UnitCard.tsx        # Unit 卡片
│   │   │   ├── ContractGrid.tsx    # 品种网格
│   │   │   ├── SessionList.tsx     # session 列表
│   │   │   ├── ManualEntryModal.tsx# 手动建仓模态框
│   │   │   ├── ManualAddReduceModal.tsx
│   │   │   ├── CloseAllModal.tsx   # 全部平仓模态框
│   │   │   └── ConfirmPriceChangeModal.tsx
│   │   ├── tabs/                   # ★ 5 个 Tab
│   │   │   ├── SignalTab.tsx
│   │   │   ├── SimTab.tsx
│   │   │   ├── LiveTab.tsx         # 占位
│   │   │   ├── BacktestTab.tsx
│   │   │   └── SessionTab.tsx      # ★ v1.4 新增
│   │   ├── stores/                 # ★ Pinia / Redux
│   │   │   ├── global.ts           # 全局账户 + 策略
│   │   │   ├── ui.ts               # UI 状态
│   │   │   └── ...
│   │   ├── hooks/                  # ★ 自定义 Hooks
│   │   │   ├── usePolling.ts       # 轮询
│   │   │   ├── usePriceLines.ts    # 价格线
│   │   │   └── ...
│   │   ├── types/                  # ★ TypeScript 类型
│   │   │   ├── session.ts
│   │   │   ├── signal.ts
│   │   │   ├── line.ts
│   │   │   └── ...
│   │   └── utils/
│   │       ├── format.ts           # 时间 / 金额 / 数量格式化
│   │       └── errors.ts           # 错误码本地化
│   └── public/
│       └── ...
│
├── notebooks/                      # 调研 + 实验（不入主流程）
│   ├── turtle-strategy/            # 海龟策略调研材料
│   └── research/                   # 量化技术调研
│
└── _requirements/                  # 需求管理（AGENTS.md 规范）
    └── data-model-redesign/        # 当前需求
        ├── README.md
        ├── 01-design/
        │   ├── README.md
        │   ├── 01-overall.md       # ★ 总体设计
        │   ├── 02-backend.md       # ★ 后端设计
        │   ├── 03-frontend.md      # ★ 前端设计
        │   ├── 04-integration.md   # ★ 整合文档
        │   ├── 05-project-structure.md  # ★ 本文档
        │   ├── _process/           # 过程记录
        │   └── _iterations/        # 迭代快照
        ├── 02-plan/
        ├── 03-execution/
        └── 04-verification/
```

---

## 二、4 大功能模块划分

### 2.1 模块总览

| # | 模块 | 路径 | 职责 | 主要技术 |
|---|------|------|------|---------|
| 1 | **数据层** | `data/` + `data/futures_akshare.db` | 行情数据同步 + SQLite 持久化 | Python + AkShare + SQLite |
| 2 | **API 层** | `api/` | HTTP API + 服务层引擎 + ORM | FastAPI + SQLAlchemy + Pydantic |
| 3 | **策略层** | `strategies/` | 策略代码组织 + 多版本管理 | Python 动态加载（importlib）|
| 4 | **前端层** | `www/` | Web UI + 状态管理 + API 客户端 | Vite + React/Vue + Pinia/Redux + TypeScript |

> **辅助模块**：`backtest/`（回测引擎）、`scripts/`（工具）、`config/`（配置）、`vnpy_strategies/`（vnpy 对接，可选）

### 2.2 模块依赖关系

```
        ┌─────────────────────────────────┐
        │       前端层（www/）              │
        │   Vite + React/Vue + TS         │
        │   5 Tab + 4 Modal + K线图       │
        └────────────────┬────────────────┘
                         │ HTTP/REST
                         │ （axios + 拦截器）
                         ↓
        ┌─────────────────────────────────┐
        │       API 层（api/）              │
        │   FastAPI + Uvicorn              │
        │   routes/ + services/ + models/  │
        │   3 大引擎 + 22 表 ORM           │
        └──────┬──────────────────┬───────┘
               │                  │
               │ ORM / SQL        │ 动态加载
               ↓                  ↓
    ┌──────────────────┐  ┌──────────────────┐
    │   数据层（data/） │  │  策略层（strategies/）│
    │ SQLite + AkShare │  │ 多版本目录 + 加载器   │
    │ 22 张表           │  │ turtle/V1/V2 等   │
    └──────────────────┘  └──────────────────┘
               ↑                  ↑
               │  行情数据          │  信号
               │                  │
               └─────【回测引擎 backtest/】─────┘
                       跨领域：复用 data + strategies
```

### 2.3 模块间数据流

| 流向 | 数据 | 触发 |
|------|------|------|
| data/ → api/services/ | K 线 / 行情 | 策略执行时读取 |
| data/ → backtest/ | 历史 K 线 | 回测时读取 |
| strategies/loader.py → api/services/ | 信号事件 | 每根 K 线 tick |
| api/services/sim_engine.py → data/ | 成交记录 | 撮合成功后写入 |
| api/services/line_calculator.py → data/ | 实时计算（不写）| 用户打开 K 线图 |
| www/ → api/ | HTTP 请求 | 用户操作 |
| api/ → www/ | HTTP 响应 | API 返回 |

---

## 三、模块详细职责

### 3.1 数据层（`data/`）

**核心职责**：
- 同步品种/合约/行情数据（Sina / AkShare）
- 持久化所有 22 张表（SQLite）
- 提供 K 线查询接口

**关键文件**：

| 文件 | 职责 |
|------|------|
| `data/data_loader.py` | 数据同步入口（每日 16:00 同步日线 + 增量同步分时）|
| `data/futures_akshare.db` | SQLite 数据库（22 张表）|

**对外接口**：
- `fetch_daily_data(symbol, start_date, end_date) → pd.DataFrame`
- `fetch_minute_data(symbol, date) → pd.DataFrame`
- `sync_all_contracts() → List[Contract]`
- `sync_all_minute_data() → int` (返回同步条数)

**依赖**：
- 上游：AkShare / Sina 财经 API
- 下游：`api/services/`, `backtest/`

### 3.2 API 层（`api/`）

**核心职责**：
- 提供 HTTP REST API
- 实现 3 大引擎（撮合 / Session 生命周期 / 策略执行）
- 价格线实时计算
- 事件流写入
- ORM 映射 22 张表

**关键文件**：

| 文件/目录 | 职责 |
|----------|------|
| `api/main.py` | FastAPI 入口（路由注册 + 中间件 + lifespan）|
| `api/routes/` | 按领域拆分的路由（accounts / strategies / contracts / sessions / trading / backtest / lines）|
| `api/services/sim_engine.py` | 撮合引擎（市价单 + 限价单）|
| `api/services/session_lifecycle.py` | Session 生命周期管理器（v1.4 核心）|
| `api/services/line_calculator.py` | 价格线计算服务（v1.3 核心）|
| `api/services/event_logger.py` | 事件流写入服务（v1.4 核心）|
| `api/models/` | SQLAlchemy ORM 模型（按领域拆分）|
| `api/schemas/` | Pydantic 请求/响应 schemas |
| `api/db/` | 数据库连接管理 |

**对外接口**：
- 28 个 HTTP API（详见 `02-backend.md` §二）
- 3 大引擎内部接口

**依赖**：
- 上游：`data/`, `strategies/`
- 下游：`www/` (前端)

### 3.3 策略层（`strategies/`）

**核心职责**：
- 策略代码组织（多版本管理）
- 动态加载策略类
- 实现策略接口（`on_bar` / `on_session_update`）

**关键文件**：

| 文件/目录 | 职责 |
|----------|------|
| `strategies/base.py` | BaseStrategy 抽象基类 |
| `strategies/loader.py` | 策略动态加载器（importlib）|
| `strategies/turtle/V1/strategy.py` | TurtleV1Strategy（实盘）|
| `strategies/turtle/V2/strategy.py` | TurtleV2Strategy（实验性）|
| `strategies/dual_ma/V1/strategy.py` | DualMAV1Strategy（预留）|
| `strategies/breakout/V1/strategy.py` | BreakoutV1Strategy（预留）|

**目录命名约定**（v1.3 核心实施约束）：

| 规则 | 说明 |
|------|------|
| 文件夹 | `<strategy_type>/V<版本号>/` 全大写 V + 数字 |
| 主类 | `<StrategyType>V<版本号>Strategy` |
| strategy_id | `<type>_v<n>` 小写 |

**对外接口**：
```python
class BaseStrategy(ABC):
    def on_bar(self, kline: dict, session_context: dict) -> Optional[SignalEvent]: ...
    def on_session_update(self, session: Session) -> None: ...

def load_strategy(strategy_id: str) -> BaseStrategy: ...
```

**依赖**：
- 上游：无
- 下游：`api/services/` (策略执行器)

### 3.4 前端层（`www/`）

**核心职责**：
- 5 个 Tab + 4 个模态框
- K 线图渲染 + 价格线拖动
- 状态管理（Pinia/Redux）
- API 客户端

**关键文件**：

| 文件/目录 | 职责 |
|----------|------|
| `www/src/main.ts` | 入口 |
| `www/src/App.tsx` | 根组件（含 5 Tab 容器）|
| `www/src/api/` | API 客户端（axios + 拦截器）|
| `www/src/components/` | 通用组件（KLineChart / Modal / UnitCard）|
| `www/src/tabs/` | 5 个 Tab 组件 |
| `www/src/stores/` | 状态管理（Pinia/Redux）|
| `www/src/hooks/` | 自定义 Hooks（usePolling 等）|
| `www/src/types/` | TypeScript 类型 |
| `www/src/utils/` | 工具函数（格式化 / 错误码本地化）|

**对外接口**：
- 5 Tab + 4 Modal + 顶部栏

**依赖**：
- 上游：`api/`
- 下游：用户浏览器

---

## 四、辅助模块

### 4.1 回测引擎（`backtest/`）

**职责**：
- 历史数据回放
- 复用 `data/` + `strategies/`
- 回测结果落 `backtest_runs` 表

**关键文件**：

| 文件 | 职责 |
|------|------|
| `backtest/backtest_engine.py` | 回测主引擎（事件循环）|
| `backtest/config.py` | 回测配置（起始资金 / 手续费）|
| `backtest/data_loader.py` | 回测数据加载（复用 `data/data_loader.py`）|

### 4.2 工具脚本（`scripts/`）

| 文件 | 职责 |
|------|------|
| `scripts/run_backtest.py` | 跑回测 CLI 入口 |
| `scripts/test_engine.py` | 引擎冒烟测试 |
| `scripts/migrate.py` | DB migration 工具（v1.0 → v1.5）|

### 4.3 配置文件（`config/`）

| 文件 | 职责 |
|------|------|
| `config/instruments.yaml` | 品种配置（代码 / 交易所 / 合约乘数）|

### 4.4 vnpy 对接（`vnpy_strategies/`，可选）

| 文件 | 职责 |
|------|------|
| `vnpy_strategies/cta_strategies/dual_ma_strategy.py` | vnpy 双均线策略（实验性）|
| `vnpy_strategies/cta_strategies/ctp_config_guide.md` | CTP 配置指南 |

> v1.5 状态：未启用，Phase 7 可选。

---

## 五、模块演进路径（v1.0 → v1.5）

| 版本 | data/ | api/ | strategies/ | www/ | backtest/ |
|------|------|------|------------|------|----------|
| v1.0 | 4 张表 | 14 个 API + main.py | turtle/ 硬编码 | index.html 单页 | backtest_engine.py 基础版 |
| v1.2 | +contracts +quotes | +6 个 API | — | — | — |
| v1.3 | +main_contract_code +date +atr | +lines API +override API | ★ base.py + loader.py + V1/V2 目录 | K线图 + 价格线 | — |
| v1.4 | — | ★ session_lifecycle.py + 6 个新 API | — | ★ Session Tab + 4 Modal | — |
| v1.5 | +turtle_trade_process | +trade-process API | — | ★ 海龟过程流水面板 | — |

---

## 六、依赖与耦合度

### 6.1 模块依赖图

```
www/  →  api/  →  data/
              ↘  strategies/
              ↘  backtest/  →  data/
                          ↘  strategies/
```

### 6.2 耦合度分析

| 耦合 | 说明 | 风险 |
|------|------|------|
| api/ ↔ data/ | ORM 强依赖 | 中（DB schema 变更影响 API）|
| api/ ↔ strategies/ | 动态加载（importlib）| 中（策略代码异常影响 API）|
| api/ ↔ backtest/ | 复用回测引擎 | 低（独立 CLI）|
| www/ ↔ api/ | HTTP 协议 | 低（OpenAPI 自动生成类型）|
| strategies/ ↔ 其他 | 无依赖 | 无（可独立编译）|

### 6.3 解耦措施

- **数据层解耦**：ORM 模型 + Pydantic schemas 分离（模型变 → schema 不变）
- **策略层解耦**：通过 BaseStrategy 抽象类 + loader 动态加载
- **前后端解耦**：OpenAPI 自动生成 TypeScript 类型
- **回测解耦**：独立 CLI + 复用 data + strategies

---

## 七、CI/CD 与代码组织约定

### 7.1 代码风格

- **Python**：PEP 8 + Black 格式化 + isort import 排序 + mypy 类型检查
- **TypeScript**：ESLint + Prettier
- **SQL**：表名小写下划线 + 字段名小写下划线 + 注释含表用途/写入方/读取方

### 7.2 提交规范

- Conventional Commits：`feat:` / `fix:` / `docs:` / `refactor:` / `test:`
- 分支：`master`（主分支）+ `feature/<name>`（功能分支）

### 7.3 测试

| 类型 | 位置 | 工具 |
|------|------|------|
| 后端单元测试 | `strategies/turtle/tests/` + `api/tests/` | pytest |
| 前端单元测试 | `www/src/**/*.test.ts` | vitest |
| 集成测试 | `api/tests/integration/` | pytest + httpx |
| 端到端测试 | `www/tests/e2e/` | playwright |

---

## 八、与总体 / 后端 / 前端的衔接

- **总体设计**：详见 `01-overall.md`
- **后端设计**（API + 服务层）：详见 `02-backend.md`
- **前端设计**（页面 + 组件）：详见 `03-frontend.md`
- **整合方案**（联调 + 部署 + 监控）：详见 `04-integration.md`
- **主设计文档**（最详细）：`../../0006_数据模型与界面重构设计.md`

---

*本文档是 _requirements/data-model-redesign/01-design/ 下的项目结构文档（v1.5），与主设计文档（0006）保持一致。*
