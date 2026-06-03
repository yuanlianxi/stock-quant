# 总体设计：数据模型与界面重构

> 文档版本：v1.5
> 创建日期：2026-06-01
> 修订日期：2026-06-02
> 负责人：Alex + Blex
> 状态：✅ 完成（v1.5 最新版）

> **本文档是 `0006_数据模型与界面重构设计.md` 的"总体视角"摘要**。详细表/接口/页面请看：
> - 数据模型 + API + 服务层 → `02-backend.md`
> - 页面 + 组件 + 状态 + 操作流 → `03-frontend.md`
> - 联调 + 错误 + 性能 + 部署 → `04-integration.md`

---

## 一、业务目标

### 1.1 现状痛点

经过 `www/index.html` + `data/data_loader.py` + `api/main.py` + `strategies/turtle/position.py` 全链路梳理，发现当前架构有 **4 个结构性缺陷**：

1. **合约维度缺失**：品种（AG）和合约（ag2607）混用
2. **策略写死**：`strategies/turtle/` 硬编码路径
3. **交易层缺失**：没有 `orders` / `trades` / `account` 表
4. **真实持仓未设计**：CTP 未对接，持仓模型未预留

### 1.2 改造目标

| # | 目标 | 用户场景 |
|---|------|---------|
| 1 | 看到品种下所有合约报价 + 主力合约高亮 | "AG 下有 4 个合约，ag2607 是主力" |
| 2 | 策略可切换 / 可并行 + 参数迭代可追溯 + 多版本代码隔离 | "海龟 V1 / V2 共存，V1 跑实盘 V2 跑回测" |
| 3 | 模拟交易全程落盘 + 回测结果持久化 | "每个成交都存，重启还能看" |
| 4 | 真实持仓模型完整 + 与 0016 通达信策略字段对齐 | "4 Unit 详情 + 锁定初始 ATR + 跳空标志" |
| 5 | 多账户支持 | "sim 账户 + live 账户并存，不同策略可挂不同账户" |
| 6 | 价格线实时计算 + 用户调价 | "K 线图上画价格线，用户拖动调整后实时重算" |
| 7 | 子策略特有事实落库（v1.4 补全）| "海龟字段不污染通用表，未来加 dual_ma 也有扩展位" |
| 8 | Session 生命周期显式化（v1.4 补全）| "信号建仓 vs 手动建仓 复用 / 隔离规则明确" |
| 9 | 海龟交易过程数据子表（v1.5 补全）| "海龟逐根 K 线决策可回放" |

---

## 二、核心概念

### 2.1 领域划分（3 大基础领域）

```
┌──────────────────────────────────────────────────────────────────┐
│ 领域 1：合约行情（4 张表）                                       │
│   futures_contracts / futures_quotes / futures_daily / futures_min│
│   职责：品种 / 合约 / 行情 / K 线                                │
├──────────────────────────────────────────────────────────────────┤
│ 领域 2：策略（6 张表 + 事件流水 + 代码组织）                     │
│   strategies / strategy_param_history / strategy_signals          │
│   strategy_event_log (v1.4) / turtle_trade_process (v1.5)        │
│   代码：strategies/<type>/V<N>/strategy.py                       │
│   职责：策略注册 / 参数迭代 / 信号流水 / 执行过程 / 子策略过程  │
├──────────────────────────────────────────────────────────────────┤
│ 领域 3：交易 / 账户（10 张表 + 事件流水）                        │
│   trade_sessions / sim_account / sim_orders / sim_trades         │
│   sim_positions / position_units / turtle_session_data (v1.4)   │
│   session_event_log (v1.4) / live_orders / live_trades / live_positions│
│   职责：账户 / 委托 / 成交 / 持仓 / Unit / Session / 子策略事实 │
└──────────────────────────────────────────────────────────────────┘
   跨领域：backtest_runs（1 张）
```

### 2.2 通用表 vs 子策略特有事实

**v1.4 关键设计**：通用表只放"所有子策略共用"的字段；子策略特有事实放专属子表。

| 表 | 类型 | 字段 |
|----|------|------|
| `trade_sessions` | 通用 | session_id, account_id, strategy_id, symbol, direction, status, entry_time, exit_time, current_units, **entry_basis_price（通用语义）**, **entry_locked_atr（通用语义）**, price_overrides_json |
| `position_units` | 通用（海龟字段为主）| unit_id, session_id, account_id, open_price, current_price, stop_price, status + 海龟字段（注释说明）|
| `turtle_session_data` | ★ 子策略特有 | 海龟专属：N_value, entry_N, max_units_reached, last_add_unit_at, last_stop_check_at, ... |
| `turtle_trade_process` | ★ 子策略过程（v1.5）| 海龟逐根 K 线事件：event_type (10 个枚举), kline_time, price, context_json |

**未来扩展**：加 `dual_ma` / `breakout` 时，类似建 `dual_ma_session_data` / `breakout_session_data` 子表，不污染通用表。

### 2.3 Session 生命周期（v1.4 核心概念）

- **Session = 一次完整交易**（建仓 → 加仓/减仓 → 全部平仓）
- **触发源 6 类**：
  1. 信号触发开仓（自动建 session）
  2. 手动建仓（API `POST /session`）
  3. 信号触发加仓（复用 open session）
  4. 手动加仓/减仓（API `POST /session/{id}/orders`，复用指定 session）
  5. 信号触发止损/退出（复用 open session）
  6. 全部平仓（API `POST /session/{id}/close`）
- **唯一性保证**：
  - DB 层：`UNIQUE (account_id, strategy_id, direction, entry_time)`
  - 应用层：asyncio.Lock（`POST /session` 拿 `session_lock`，HTTP 423 拒绝冲突）

### 2.4 子策略过程数据（v1.5 核心概念）

- **turtle_trade_process** 表：海龟策略逐根 K 线决策流水
- **10 个 event_type**：
  - `entry_signal` / `entry_filled`
  - `add_signal` / `add_filled` / `add_skipped_gap`
  - `stop_loss_check` / `stop_loss_triggered`
  - `check_exit` / `exit_20_triggered` / `unit_closed`
- **check 类事件优化存储（C 方案）**：触发存前后 5 根 K 线，平时不存
- **退仓优先顺序**：止损 > 加仓（同根 K 线时）
- **加仓次数**：4 Unit = 1 首仓 + 3 加仓

---

## 三、整体架构

### 3.1 数据层（22 张表）

| 领域 | 表数 | 表名 |
|------|------|------|
| 领域 1：合约行情 | 4 | futures_contracts, futures_quotes, futures_daily, futures_min |
| 领域 2：策略 | 6 | strategies, strategy_param_history, strategy_signals, strategy_event_log (v1.4), turtle_trade_process (v1.5), ~~strategy_signal_states~~ (v1.3 删除) |
| 领域 3：交易账户 | 10 | trade_sessions, sim_account, sim_orders, sim_trades, sim_positions, position_units, turtle_session_data (v1.4), session_event_log (v1.4), live_orders, live_trades, live_positions |
| 跨领域 | 1 | backtest_runs |
| 代码 | — | strategies/<type>/V<N>/strategy.py |
| **合计** | **22 张** | （含 3 张预留 live_*） |

### 3.2 API 层（6 个核心新 API + 22 个原有/改造）

**v1.4 + v1.5 核心新 API**（★ 是新增重点）：

| 方法 | 路径 | 用途 | 引入版本 |
|------|------|------|---------|
| POST | `/session` | 手动建仓（新建 session）| v1.4 |
| POST | `/session/{id}/orders` | 手动加仓/减仓 | v1.4 |
| POST | `/session/{id}/close` | 全部平仓 | v1.4 |
| GET | `/session/{id}/events` | 事件流（session_event_log）| v1.4 |
| GET | `/sessions?status=open` | open session 列表 | v1.4 |
| GET | `/session/{id}/trade-process` | 海龟交易过程流水 | v1.5 |

**原有 + 改造 API**（22 个，含 4 个重定向）：账户 / 策略 / 合约 / 信号 / 模拟持仓 / 回测 / 价格线 / 调价等。详见 `02-backend.md` §二。

### 3.3 服务层（3 大引擎）

1. **撮合引擎**（`sim_engine.py`）：市价单撮合 + 限价单撮合
2. **Session 生命周期管理器**（`session_lifecycle.py`）：6 类触发源处理 + 应用锁 + DB 唯一性
3. **策略执行器**（`strategies/loader.py`）：动态加载 `strategies/<type>/V<N>/strategy.py`

### 3.4 界面层（5 个 Tab + 4 个模态框）

**5 个 Tab**：
1. **信号 Tab**（v1.3 起为"详情·信号"）：实时 JOIN 算
2. **模拟 Tab**：sim_positions + sim_orders + sim_trades
3. **真实 Tab**：live_* 预留
4. **回测 Tab**：backtest_runs 历史
5. **Session Tab**（v1.4 新增）：trade_sessions 列表 + 详情

**4 个模态框**（v1.4 新增）：
- 手动建仓模态框
- 手动加仓/减仓模态框
- 全部平仓模态框
- 用户调价模态框（拖动 K 线水平线）

**顶部新增**（v1.3 起）：
- 策略切换器
- 账户切换器
- 操作组（建仓 / 加仓 / 减仓 / 全部平仓）

详见 `03-frontend.md`。

---

## 四、关键决策记录

### 4.1 v1.0 决策（2026-06-01）— 基础设计

- ✅ 3 大领域划分（合约行情 / 策略 / 交易账户）
- ✅ 16 张表（v1.0 起步数，实际 v1.2 起表数有调整）
- ✅ 信号主表 `strategy_signals` + 状态表 `strategy_signal_states`（v1.3 后者删除）
- ✅ 多版本代码组织：`strategies/<type>/V<N>/strategy.py`

### 4.2 v1.1 决策（2026-06-01）— 5 项关键修订

- 表注释补全
- 策略版本字段（`strategies.version`）
- 信号主表命名统一
- 交易会话（trade_sessions）引入
- ~~策略状态表拆分~~（v1.2 已替代）

### 4.3 v1.2 决策（2026-06-01）— 三大基础领域重构

- ✅ **领域划分**：明确划分 3 个基础领域
- ✅ **删除**：`turtle_states` / `dual_ma_states`（状态属于交易事实）
- ✅ **新增**：`trade_sessions`（交易领域主表）
- ✅ **核心原则**：**策略是无状态规则引擎**，锁定值在交易领域落库

### 4.4 v1.3 决策（2026-06-01）— 多项强化

| # | 决策 | 备选 |
|---|------|------|
| 1 | 多账户支持：所有交易表加 `account_id` | 单账户 |
| 2 | **价格线实时计算（不持久化）** | 持久化 `trade_session_lines` 表 |
| 3 | 用户调价：`trade_sessions.price_overrides_json` | 独立表 |
| 4 | 策略代码组织：`strategies/<type>/V<N>/strategy.py` | 单一路径 |
| 5 | K 线数据保留期：daily 3 年 / min 半年 | 14 天 / 7 天 |
| 6 | ATR 整合到 `futures_daily.atr` | 独立 `futures_atr` 表 |
| 7 | `futures_min` 加 `date` 字段（从 datetime 派生）| 不冗余 |
| 8 | `futures_daily` 加 `main_contract_code` | 不预留 |
| 9 | 精简信号表 + 删除 `strategy_signal_states` | 完整信号状态 |
| 10 | 交易/账户/订单表加 `platform_name` 等外部信息 | 不预留 |
| 11 | `trade_sessions` 加 UNIQUE 约束 | 仅 PK 唯一 |

### 4.5 v1.4 决策（2026-06-02）— 子策略特有事实 + Session 生命周期

| # | 决策 | 备选 |
|---|------|------|
| 1 | `turtle_session_data` 字段范围：7 字段 | 8 字段（含 `max_units_reached`）|
| 2 | `dual_ma_session_data` 占位：**不预留** | 预留空表 |
| 3 | `session_event_log.event_type` 枚举：8 个 | 6 个精简版 |
| 4 | 老 session 归档：v1.4 不实施，靠索引兜底 | 30 天归档到 `trade_sessions_archive` |
| 5 | `position_units` 海龟字段：继续放，加注释 | 拆到 `turtle_unit_data` |
| 6 | 手动 vs 信号并发：应用层互斥锁（HTTP 423）| DB 事务锁 / 不处理 |
| 7 | 用户入口分散 3 处：保持分散 | 合并为 1 个总控按钮 |
| 8 | 版本策略：v1.4 独立版本（保留 v1.3 全部内容）| 在 v1.3 上修改 |

### 4.6 v1.5 决策（2026-06-02）— 海龟交易过程数据子表

| # | 决策 | 备选 |
|---|------|------|
| 1 | 加仓次数：4 Unit（1 首仓 + 3 加仓）| 其他次数 |
| 2 | 退仓优先：止损优先 | 加仓优先 |
| 3 | check 类存储：C 方案（触发存前后 5 根）| 全量存 / 不存 |
| 4 | `dual_ma_trade_process`：v1.5 不做 | v1.6 一起做 |

### 4.7 命名微调（v1.5 末）— check_exit 命名

- `check_exit_20` → `check_exit`（简化）
- `exit_20_signal` → `exit_20_triggered`（明确"已触发"语义）
- `entry_signal` → 保持
- `stop_loss_signal` → `stop_loss_triggered`

**原因**：
- `check_exit_20` 名字太具体，check 类事件应统一不带数字后缀
- `exit_20_triggered` 用"triggered"明确是已触发事件，对应"信号"用 `signal`

---

## 四.5、价格线设计哲学（v1.3 核心新增）

> 本节为总体设计层加的"价格线设计哲学"，细节算法 / API / 调价见 `02-backend.md` §5。

价格线是**派生数据**而非持久化事实，核心思想：

- **不持久化价格线表**：不新建 `trade_session_lines` 表，每次需要时调用算法实时计算
- **数据来源**：基础事实（`trade_sessions` + `position_units` + 策略参数 + K 线）实时 JOIN
- **override 持久化**：用户调价通过 `trade_sessions.price_overrides_json` 字段持久化
- **override 优先级**：用户 override 优先于算法值；已成交的 line 不应用 override（用 actual_fill）
- **生命周期跟随 session**：session 建则有线、session close 则线失效
- **触发场景**：仅 session.status='open' 或 'pending' 时可调价

**计算 API**：`GET /session/{id}/lines?account_id=...`（不写库，实时返回）
**调价 API**：`PUT /session/{id}/line/{line_type}?account_id=...`（写 price_overrides_json）

**关联表**：
- 实时计算读：`trade_sessions` + `position_units` + `turtle_session_data` + K 线
- override 持久化写：`trade_sessions.price_overrides_json`

详见 `02-backend.md` §5。

## 四.6、Session 生命周期（v1.4 核心概念 — 总体视角）

> 本节为高层摘要；完整流程 + 互斥锁 + 6 类触发源细节见 `02-backend.md` §7.5。

**Session = 一次完整交易**（建仓 → 加仓/减仓 → 全部平仓）

**6 类触发源**：

| # | 触发源 | session 来源 | 实现位置 |
|---|--------|-------------|---------|
| 1 | 信号触发开仓（entry_long/entry_short）| 新建 | 策略执行器 → SessionLifecycle.on_signal_entry |
| 2 | 手动建仓（POST /session）| 新建 | API 路由 → SessionLifecycle.on_manual_entry |
| 3 | 信号触发加仓（add_unit_N）| 复用 open session | 策略执行器 → SessionLifecycle.on_signal_add |
| 4 | 手动加仓/减仓（POST /session/{id}/orders）| 复用指定 session | API 路由 → SessionLifecycle.on_manual_add/reduce |
| 5 | 信号触发止损/退出（stop_loss/exit_20）| 复用 open session | 策略执行器 → SessionLifecycle.on_signal_close |
| 6 | 全部平仓（手动 POST /session/{id}/close）| 复用指定 session | API 路由 → SessionLifecycle.on_close_all |

**双层唯一性约束**：
- DB 层：`trade_sessions UNIQUE (account_id, strategy_id, direction, entry_time)` 兜底
- 应用层：`asyncio.Lock` 串行化（HTTP 423 拒绝并发）

**事件流水**：
- `session_event_log`（8 个 event_type）记录所有状态变化
- `turtle_trade_process`（10 个 event_type）记录海龟逐根 K 线决策

**操作流程图**（详见 02-backend.md §7.6）：
- 手动建仓 → 手动加仓 → 手动减仓 → 全部平仓（4 个流程）

---

## 四.7、22 张表清单速查（v1.4 完整版）

> 本节为 22 张表汇总表，引用自 `02-backend.md` §1.1。建表 SQL 见 `02-backend.md` §1.1。

| # | 表名 | 领域 | 状态 | 说明 |
|---|------|------|------|------|
| 1 | `futures_contracts` | 1 合约行情 | v1.2 新增 | 合约静态信息 + is_main |
| 2 | `futures_quotes` | 1 合约行情 | v1.2 新增 | 合约实时行情 |
| 3 | `futures_daily` | 1 合约行情 | 保留 | 日 K 线（含 atr / main_contract_code）|
| 4 | `futures_min` | 1 合约行情 | 保留 | 分 K 线（含 date 派生字段）|
| 5 | `strategies` | 2 策略 | v1.2 +version | 策略主表 |
| 6 | `strategy_param_history` | 2 策略 | v1.1 新增 | 参数迭代历史 |
| 7 | `strategy_signals` | 2 策略 | v1.0 +strategy_id | 信号流水（仅开仓）|
| 8 | ~~`strategy_signal_states`~~ | 2 策略 | **v1.3 删除** | 派生数据不持久化 |
| 9 | `strategy_event_log` | 2 策略 | **★ v1.4 新增** | 策略执行引擎事件流水 |
| 10 | `turtle_trade_process` | 2 策略 | **★ v1.5 新增** | 海龟交易过程流水（10 event_type）|
| 11 | `trade_sessions` | 3 交易账户 | v1.2 +account_id +price_overrides_json | 一次完整交易主表 |
| 12 | `sim_account` | 3 交易账户 | v1.0 +user_id +display_name | 模拟账户 |
| 13 | `sim_orders` | 3 交易账户 | v1.0 +account_id +platform_name | 模拟委托 |
| 14 | `sim_trades` | 3 交易账户 | v1.0 +account_id +platform_name | 模拟成交 |
| 15 | `sim_positions` | 3 交易账户 | v1.0 +account_id | 模拟持仓汇总 |
| 16 | `position_units` | 3 交易账户 | v1.0 +account_id | 4 Unit 详情 |
| 17 | `turtle_session_data` | 3 交易账户 | **★ v1.4 新增** | 海龟子策略 session 特有事实（7 字段）|
| 18 | `session_event_log` | 3 交易账户 | **★ v1.4 新增** | session 生命周期事件流水（8 event_type）|
| 19 | `live_orders` | 3 交易账户 | 预留 +account_id | 真实委托（CTP）|
| 20 | `live_trades` | 3 交易账户 | 预留 +account_id | 真实成交（CTP）|
| 21 | `live_positions` | 3 交易账户 | 预留 +account_id | 真实持仓（CTP）|
| 22 | `backtest_runs` | 跨领域 | v1.0 保留 | 回测任务 |

**总表数**：22 张（领域 1: 4 / 领域 2: 6 / 领域 3: 10 / 跨领域: 1 / 预留 live_*: 3 + 0 净增 + 0 占位）

**v1.3 → v1.4 → v1.5 表数变化**：
- v1.3: 18 张 → v1.4: 21 张（+3：turtle_session_data / session_event_log / strategy_event_log）
- v1.4: 21 张 → v1.5: 22 张（+1 turtle_trade_process）
- 领域 2：4 → 5 → 6（v1.4 +strategy_event_log / v1.5 +turtle_trade_process）
- 领域 3：8 → 10 → 10（v1.4 +turtle_session_data +session_event_log）

**子策略扩展规则**（v1.4 决策点 1）：
- 通用表只放"所有子策略共用"字段
- 子策略特有事实 → 专属子表（如 `turtle_session_data` / `turtle_trade_process`）
- 未来加 `dual_ma` / `breakout` 时，建对应子表不污染通用表

**`dual_ma_session_data` 不预留**（v1.4 决策点 2：避免空表占位维护成本）
**`dual_ma_trade_process` v1.5 不做**（决策点 4：等加 dual_ma 时再设计）

---

## 五、范围与不在范围

### 5.1 在范围（本次需求）

- 数据模型重构（22 张表）
- 6 个核心新 API + 22 个原有/改造 API
- 5 个 Tab + 4 个模态框
- 撮合引擎 + Session 生命周期 + 策略执行器
- 海龟策略过程数据子表

### 5.2 不在范围（后续阶段）

- CTP 实盘接入（Phase 7 可选）
- 真实订单路由
- 多账户资金划转
- 完整风控系统（止盈 / 仓位管理）

---

## 六、参考文档

- **主设计文档**（完整版）：`../../0006_数据模型与界面重构设计.md`（v1.5 / 2376 行 / 14 ## / 57 ###）
- **主技术文档**：`../../0002_技术设计.md`
- **主变更日志**：`../../0003_变更日志.md`
- **通达信海龟详解**：`../../0016_通达信海龟策略详解.md`

---

## 七、现状分析（提炼自 0006 §二）

### 7.1 当前数据表（4 张）

| 表 | 主键 | 关键字段 | 数据量级 | 备注 |
|----|------|---------|---------|------|
| `futures_daily` | (symbol, date) | OHLC, volume, hold, settle, **atr** (v1.3 新增), cached_at | ~1万行/品种 | **3 年滚动**（v1.3 调整）|
| `futures_min` | (symbol, datetime) | OHLC, volume, period, contract_code, name, **date** (v1.3 新增), cached_at | ~1万行/品种/周期 | **半年滚动**（v1.3 调整）|
| `turtle_signals` | id (自增) | symbol, signal_type, trigger_price, ... | 通常 0-数百 | v1.3 升级为 strategy_signals |
| `futures_atr` | (symbol, date) | atr, n_value | 极小 | **★ v1.3 合并到 futures_daily，删除此表** |

### 7.2 数据表与界面对应关系矩阵（现状）

| 界面功能 | 当前数据源 | 数据流 | 现状问题 |
|---------|-----------|--------|---------|
| 品种网格（价格/涨跌）| `futures_daily` 最后一条 | `GET /signals/all` 返回 | 实时价用日线收盘 |
| 品种网格（信号指示点）| `turtle_signals` 最新 | `GET /turtle/signals/active` | 只有海龟，多策略无法区分 |
| K 线图 | `futures_min` / `futures_daily` | `GET /minute/{sym}` / `GET /daily/{sym}` | 没有"按合约切换"，没有"价格线" |
| 信号时间线 | `turtle_signals` | `GET /turtle/signals/{sym}` | 写死 turtle |
| 持仓卡片 | 内存 `PositionManager` | `GET /position/{sym}` | 进程重启即丢 |
| 回测结果 | 内存 job | `POST /backtest/run` | 不落盘 |

**核心矛盾**：界面已经在展示"策略信号 + 持仓 + 回测"三件套，但数据层只有"行情 + 单一策略信号"两张半表，缺一半。

---

## 八、领域总览（提炼自 0006 §三，含写入方/读出方）

### 8.1 三大基础领域总览

```
┌──────────────────────────────────────────────────────────────┐
│ 领域 1：合约行情（Contract Market）                          │
│ 基础事实：合约 + 价格走势                                    │
│ 写入方：数据同步服务（Sina / AkShare）                       │
│ 读出方：所有需要行情的领域                                   │
└──────────────────────────────────────────────────────────────┘
                              ▲
                              │ 提供走势数据
                              │
┌──────────────────────────────────────────────────────────────┐
│ 领域 2：策略（Strategy）                                     │
│ 本质：规则 + 参数，无状态                                    │
│ 输入：合约走势（领域 1）+ 持仓事实（领域 3）                 │
│ 输出：信号（待转化为委托）                                   │
│ 代码组织：strategies/<type>/V<版本>/strategy.py             │
└──────────────────────────────────────────────────────────────┘
                              ▲
                              │ 信号触发 / 持仓反查
                              │
┌──────────────────────────────────────────────────────────────┐
│ 领域 3：交易 / 账户（Trading & Account）                     │
│ 基础事实：账户 + 实际买了什么                                │
│ 写入方：撮合引擎 / CTP 回报                                 │
│ 读出方：策略（下一次决策）+ 账户中心 + 回测 + 价格线计算    │
│ v1.3 新增：account_id 关联 + price_overrides_json 用户调价  │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 关键设计原则（v1.2 保持）

- **策略是无状态的**——不存"当前 phase"、"锁定值"等中间状态
- **"锁定值"（基准价/锁定 ATR/跳空标志）**在建仓瞬间由撮合引擎写死到 `trade_sessions` / `position_units`
- 策略下次执行时直接**读这些事实**，不需要"中间状态表"

### 8.3 价格线是"实时计算"不是"持久化"（v1.3 关键决策）

**反例（v1.3 旧版提议）**：

```
存储 trade_session_lines 表：
  - entry_actual @ 18810
  - add_unit_1_predicted @ 18860
  - add_unit_2_predicted @ 18910
  - stop_loss_predicted @ 18710
```

**问题**：
- 价格线是**派生数据**，不是事实
- 派生数据持久化会导致"双写一致性问题"（基础事实变了，派生数据没更新）
- 加仓后 stop_loss 会重算，写库就过期了
- 浪费存储

**v1.3 修正**：

```
不存储价格线，每次需要时实时计算：
  inputs: trade_sessions 锁定值 + position_units 实际成交价
         + price_overrides_json 用户覆盖 + 策略参数
  output: 一组价格线 JSON
```

**收益**：
- **单一数据源**：所有价格线都从基础事实计算
- **用户调价即时生效**（改 JSON 后下次计算就用新值）
- **加仓后子线自动重算**（无过期问题）

### 8.4 跨领域协同关系（v1.3 强化）

| 协同方向 | 触发条件 | 数据流 | 关键字段 |
|---------|---------|--------|---------|
| 合约 → 策略 | K线更新 | 读 `futures_min` / `futures_daily` | OHLC |
| 合约 → 交易 | 行情刷新 | 读 `futures_quotes` 写 `sim_trades.price` | trade |
| 交易 → 策略 | 策略执行 | 读 `trade_sessions` / `position_units` | locked_atr, basis_price, current_units |
| 策略 → 交易 | 信号触发 | 写 `sim_orders` | signal_type, direction, hand_count |
| 撮合 → 交易 | 成交发生 | 写 `sim_trades` + `trade_sessions` + `position_units` + `sim_positions` | 价格/手续费 |
| 策略 → 信号表 | 信号触发（仅开仓）| 写 `strategy_signals` | signal_type |
| 交易 → 合约 | 价格线计算 | 读 `trade_sessions` + `position_units` 实时算 | entry_basis_price, locked_atr, current_units |
| 合约 → 价格线 | 价格线计算 | 读 `futures_daily` / `futures_min` | 20日高/低 |

---

## 九、风险与回退（提炼自 0006 §十一）

### 9.1 主要风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 撮合引擎性能不达标 | 中 | 高 | 提前性能测试，必要时降级到 5 秒撮合 |
| Session 并发 423 频繁 | 中 | 中 | 调优互斥锁粒度（按 (account_id, symbol) 而非全局）|
| 价格线计算慢 | 低 | 中 | 预计算 N 值缓存到内存 |
| 数据迁移失败 | 中 | 高 | 完整备份 + 回滚脚本 |
| 真实 Tab 误启用 | 低 | 中 | 强 Feature Flag（默认关闭）|
| 子策略扩展污染通用表 | 中 | 中 | 严格 v1.4 通用/子策略边界（详见 §二.2）|
| `turtle_trade_process` 数据膨胀 | 中 | 中 | C 方案：check 类事件触发时存前后 5 根 |

### 9.2 回退方案

| 场景 | 回退方案 |
|------|---------|
| Phase 3 上线后问题多 | 回滚到 Phase 2 状态（DB 迁移 down + 前端回滚）|
| 撮合引擎严重 bug | 切换到 5 秒轮询人工模式（半自动）|
| 价格线计算慢 | 临时回退到"持久化 trade_session_lines 表"（v1.3 旧版方案）|
| CTP 接入有问题 | 关闭真实 Tab（Feature Flag）|
| 字段污染回退 | 通用表保留旧字段（加注释），子策略表回退到 v1.3 字段集 |
| check 类事件存储过多 | 切到 A 方案（全量存）或 B 方案（完全不存）|

---

## 十、附录：界面与数据表对应关系（提炼自 0006 §6.6）

> 完整的 5 个 Tab + 4 个模态框组件设计见 `03-frontend.md`。本节仅做"界面区块 ↔ 数据表 ↔ API"映射。

| 界面区块 | 涉及数据表 | 领域 | 主要 API |
|---------|-----------|------|---------|
| 顶部账户切换 | `sim_account` | 3 交易 | `GET /accounts` |
| 顶部策略切换 | `strategies` | 2 策略 | `GET /strategies?account_id=...` |
| 品种网格（信号点）| `strategy_signals`（仅最新开仓事件）| 2 策略 | `GET /signals/all?strategy_id=...` |
| 合约抽屉 | `futures_contracts`, `futures_quotes` | 1 合约 | `GET /contracts/{symbol}`, `GET /quotes/{contract_code}` |
| 详情·信号 Tab（当前）| 实时 JOIN（`trade_sessions` + `strategy_signals`）| 2 策略 | `GET /strategy/signal/state/{sym}` |
| 详情·模拟 Tab | `sim_*`（带 account_id 过滤）| 3 交易 | `GET /sim/positions?account_id=...` |
| 详情·真实 Tab | `live_*` | 3 交易 | `GET /live/...`（预留，v1.5 占位）|
| 详情·回测 Tab | `backtest_runs` | 跨领域 | `POST /backtest/run` |
| K 线图 + 价格线 | 实时计算（trade_sessions + position_units + K线）| 跨领域 | `GET /session/{id}/lines` |
| 用户调价 | `trade_sessions.price_overrides_json` | 3 交易 | `PUT /session/{id}/line/{line_type}` |
| 账户中心 | 所有 sim_* | 3 交易 | `GET /account/overview?account_id=...` |
| 策略历史 | `strategies` + `strategy_param_history` | 2 策略 | `GET /strategies/{id}/history` |
| 回测中心 | `backtest_runs` + 关联 `sim_trades` | 跨领域 | `GET /backtest/runs` |
| 手动建仓模态框 | `trade_sessions` + `sim_orders` + `sim_trades` | 3 交易 | `POST /session` |
| 手动加仓/减仓模态框 | `sim_orders` + `sim_trades` + `position_units` | 3 交易 | `POST /session/{id}/orders` |
| 全部平仓模态框 | `sim_orders` + `sim_trades` + `trade_sessions` (close) | 3 交易 | `POST /session/{id}/close` |
| Session Tab（v1.4）| `trade_sessions` + `position_units` + `session_event_log` | 3 交易 | `GET /sessions?status=open` |
| 海龟过程流水（v1.5）| `turtle_trade_process` | 2 策略 | `GET /session/{id}/trade-process` |

---

## 十一、附录：9 个核心交互流（提炼自 0006 §七）

> 完整流程图见 `02-backend.md` §七（后端视角）和 `03-frontend.md` §五（前端视角）。本节为高层清单。

| # | 流程 | 触发方 | 触发源 | 关键表 | 引入版本 |
|---|------|--------|--------|--------|---------|
| 1 | 策略执行循环 | 自动（每根 K 线）| K 线 tick | `strategy_signals` + `strategy_event_log` | v1.3 |
| 2 | 价格线计算 | 用户/API | 切换 session 详情 | 实时算（不写库）| v1.3 |
| 3 | 用户调价流程 | 用户 | 拖动价格线 | `trade_sessions.price_overrides_json` | v1.3 |
| 4 | Session 生命周期 | 自动/手动 | 6 类触发源 | `trade_sessions` + `session_event_log` | v1.4 |
| 5 | 手动建仓流程 | 用户 | 模态框 | `trade_sessions` + `sim_orders` + `sim_trades` | v1.4 |
| 6 | 手动加仓流程 | 用户 | 模态框 | `position_units` + `sim_orders` | v1.4 |
| 7 | 手动减仓流程 | 用户 | 模态框 | `position_units` (close) + `sim_trades` | v1.4 |
| 8 | 全部平仓流程 | 用户 | 模态框 | `trade_sessions` (close) + 所有 `position_units` | v1.4 |
| 9 | 海龟交易过程 | 自动（每根 K 线）| 海龟策略执行 | `turtle_trade_process` | v1.5 |

---

*本文档是 _requirements/data-model-redesign/01-design/ 下的总体设计，与主设计文档（0006）保持一致。*
