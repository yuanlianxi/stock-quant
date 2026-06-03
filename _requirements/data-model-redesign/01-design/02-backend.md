# 后端设计：数据模型 / API / 服务层 / 交互协议

> 文档版本：v1.5
> 创建日期：2026-06-01
> 修订日期：2026-06-02
> 负责人：Alex + Blex
> 状态：✅ 完成（v1.5 最新版）

> **本文档是 `0006_数据模型与界面重构设计.md` 的"后端视角"详细拆分**。总体设计看 `01-overall.md`，前端看 `03-frontend.md`，整合看 `04-integration.md`。

---

## 一、数据模型（22 张表 + 1 张归档占位）

### 1.1 表清单（22 张活跃 + 1 预留 + 1 子策略 + 1 事件流水）

#### 领域 1：合约行情（4 张）

| # | 表名 | 行数预估 | 主键 | 关键字段 | 索引 |
|---|------|---------|------|---------|------|
| 1 | `futures_contracts` | ~500 | `contract_code` | `symbol`, `exchange`, `list_date`, `delist_date`, `is_main` | `idx_fc_symbol`, `idx_fc_main` |
| 2 | `futures_quotes` | ~500 | `contract_code` | `last_price`, `bid_price1`, `ask_price1`, `volume`, `open_interest`, `update_time` | `idx_fq_update_time` |
| 3 | `futures_daily` | ~500 × 750 (3年) | `(contract_code, date)` | `open`/`high`/`low`/`close`/`volume`/`oi`, `atr`, `main_contract_code` | `idx_fd_main_contract`, `idx_fd_date` |
| 4 | `futures_min` | ~500 × 100k/天 × 180天 | `(contract_code, datetime)` | `open`/`high`/`low`/`close`/`volume`, `date` (派生) | `idx_fm_symbol_date` |

#### 领域 2：策略（6 张）

| # | 表名 | 行数预估 | 主键 | 关键字段 | 索引 |
|---|------|---------|------|---------|------|
| 5 | `strategies` | <50 | `strategy_id` | `name`, `type`, `version`, `code_path`, `is_active`, `param_json` | `idx_st_type_version` |
| 6 | `strategy_param_history` | <500 | `param_history_id` | `strategy_id`, `param_json`, `change_reason`, `change_at` | `idx_sph_strategy_at` |
| 7 | `strategy_signals` | ~1000/天 | `signal_id` | `strategy_id`, `symbol`, `signal_type` (entry_long/entry_short), `signal_time`, `price` | `idx_ss_strategy_time` |
| 8 | `strategy_event_log` (v1.4) | ~5000/天 | `event_id` | `strategy_id`, `event_type`, `event_at`, `context_json` | `idx_sel_strategy_at` |
| 9 | `turtle_trade_process` (v1.5) | ~200/天 | `event_id` | `session_id`, `event_type` (10 枚举), `kline_time`, `price`, `context_json` | `idx_ttp_session_time` |

> ⚠️ `strategy_signal_states` 表在 v1.3 已**删除**（派生数据不持久化，实时 JOIN 算）。

#### 领域 3：交易 / 账户（10 张）

| # | 表名 | 行数预估 | 主键 | 关键字段 | 索引 |
|---|------|---------|------|---------|------|
| 10 | `trade_sessions` | ~10/天 (活跃) | `session_id` (UUID) | `account_id`, `strategy_id`, `symbol`, `direction`, `status`, `entry_time`, `exit_time`, `current_units`, `entry_basis_price` (通用), `entry_locked_atr` (通用), `price_overrides_json` | **UNIQUE (account_id, strategy_id, direction, entry_time)**, `idx_ts_status_open` (部分索引) |
| 11 | `sim_account` | <10 | `account_id` | `name`, `balance`, `available`, `margin_used`, `platform_name` | — |
| 12 | `sim_orders` | ~100/天 | `order_id` (UUID) | `account_id`, `session_id`, `symbol`, `direction`, `order_type` (market/limit), `quantity`, `price`, `status`, `platform_name`, `external_order_id` | `idx_so_account_time` |
| 13 | `sim_trades` | ~100/天 | `trade_id` (UUID) | `account_id`, `order_id`, `session_id`, `symbol`, `direction`, `filled_price`, `filled_quantity`, `commission`, `platform_name`, `external_trade_id` | `idx_st_account_time` |
| 14 | `sim_positions` | ~50 (活跃) | `(account_id, symbol)` | `quantity`, `avg_cost`, `realized_pnl`, `unrealized_pnl` | — |
| 15 | `position_units` | ~50/天 | `unit_id` (UUID) | `session_id`, `account_id`, `unit_index` (1-4), `open_price`, `current_price`, `stop_price`, `status`, + 海龟字段（`entry_basis_price`/`entry_atr`）| `idx_pu_session` |
| 16 | `turtle_session_data` (v1.4) | 1:1 trade_sessions | `session_id` (PK+FK) | `N_value`, `entry_N`, `max_units_reached`, `last_add_unit_at`, `last_stop_check_at`, `add_count`, `is_gap_risk` | — |
| 17 | `session_event_log` (v1.4) | ~500/天 | `event_id` | `session_id`, `event_type` (8 枚举), `event_at`, `context_json` | `idx_sesl_session_at` |
| 18 | `live_orders` (预留) | 0 | `order_id` | 同 sim_orders + `ctp_order_ref`/`ctp_front_id`/`ctp_session_id` | — |
| 19 | `live_trades` (预留) | 0 | `trade_id` | 同 sim_trades + `external_trade_id` | — |
| 20 | `live_positions` (预留) | 0 | `(account_id, symbol)` | 同 sim_positions | — |

#### 跨领域（2 张）

| # | 表名 | 行数预估 | 主键 | 关键字段 | 索引 |
|---|------|---------|------|---------|------|
| 21 | `backtest_runs` | ~10/月 | `run_id` | `strategy_id`, `symbol`, `start_date`, `end_date`, `params_json`, `result_metrics_json`, `status` | `idx_br_strategy_at` |
| 22 | `~~dual_ma_session_data~~` | — | — | **v1.4 决策：不预留**（未来加 dual_ma 时再建）| — |

> 实际表数：22 张活跃 + 3 张预留（live_*）+ 1 张占位（dual_ma，不预留删除）。

### 1.2 表关系图（外键 + 业务关联）

```
┌─────────────────────────────────────────────────────────────────────┐
│                       领域 1：合约行情                              │
│ futures_contracts ───< futures_daily (1:N)                          │
│                  ───< futures_min (1:N)                             │
│                  ───< futures_quotes (1:1)                          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ symbol
┌─────────────────────────────────────────────────────────────────────┐
│                       领域 2：策略                                    │
│ strategies ───< strategy_param_history (1:N)                        │
│            ───< strategy_signals (1:N)                              │
│            ───< strategy_event_log (1:N)                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ strategy_id
┌─────────────────────────────────────────────────────────────────────┐
│                       领域 3：交易 / 账户                           │
│ sim_account ───< sim_orders ───< sim_trades                          │
│             ───< sim_positions                                      │
│             ───< trade_sessions ───< position_units (1:N)           │
│                                  ───< sim_orders (session_id)       │
│                                  ───< turtle_session_data (1:1)     │
│                                  ───< session_event_log (1:N)       │
│                                  ───< turtle_trade_process (1:N)    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ backtest_runs (独立，通过 strategy_id + symbol 关联)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 子策略特有事实（v1.4 + v1.5 核心设计）

**通用表 vs 子策略表**：

| 通用表 | 子策略特有表（v1.4+） |
|--------|---------------------|
| `trade_sessions` | `turtle_session_data`（1:1，海龟 7 字段）|
| （无）| `turtle_trade_process`（v1.5，1:N，海龟逐根 K 线决策）|

**未来扩展**：加 `dual_ma` 时建 `dual_ma_session_data` + `dual_ma_trade_process`，不污染通用表。

---

## 二、API 层（6 个核心新 API + 22 个原有/改造）

### 2.1 v1.4 + v1.5 核心新 API（★ 重点）

| 方法 | 路径 | 用途 | 涉及表 | 引入版本 |
|------|------|------|--------|---------|
| POST | `/session` | 手动建仓（新建 session）| `trade_sessions` + `sim_orders` + `sim_trades` | v1.4 |
| POST | `/session/{id}/orders` | 手动加仓/减仓 | `sim_orders` + `sim_trades` + `position_units` | v1.4 |
| POST | `/session/{id}/close` | 全部平仓 | `sim_orders` + `sim_trades` + `trade_sessions` (close) | v1.4 |
| GET | `/session/{id}/events` | session 事件流 | `session_event_log` | v1.4 |
| GET | `/sessions?status=open` | open session 列表 | `trade_sessions` | v1.4 |
| GET | `/session/{id}/trade-process` | 海龟交易过程流水 | `turtle_trade_process` | v1.5 |

### 2.2 全部 API 清单（28 个）

#### 账户（4 个）

```
GET    /accounts                          # 列出所有账户
POST   /accounts                          # 创建新账户
GET    /sim/account/{account_id}          # 模拟账户详情
GET    /account/overview?account_id=...&strategy_id=...  # 账户总览
```

#### 策略（6 个）

```
GET    /strategies?account_id=...         # 列出策略
GET    /strategies/{id}/history           # 策略参数历史
POST   /strategies                        # 注册新策略
PUT    /strategies/{id}/params            # 更新参数（自动写 history）
GET    /strategy/signal/state/{sym}?strategy_id=...   # 当前信号状态（实时 JOIN 算）
GET    /strategy/signals/{sym}?strategy_id=...        # 历史信号
```

#### 合约（3 个）

```
GET    /contracts/{symbol}                # 品种下所有合约
GET    /quotes/{contract_code}            # 合约实时行情
GET    /futures/daily?contract_code=...&start_date=...&end_date=...  # 日线
GET    /futures/min?contract_code=...&date=...                       # 分时
```

#### 交易 / 持仓（6 个 + 6 个 v1.4 新增）

```
GET    /sim/positions?account_id=...      # 模拟持仓
GET    /sim/orders?account_id=...         # 模拟委托
GET    /sim/trades?account_id=...         # 模拟成交
POST   /sim/order                          # 手动模拟下单（保留，v1.4 后用于内部调用）
GET    /sim/sessions?account_id=...&strategy_id=...   # 模拟 session

# v1.4 新增 ★
POST   /session                            # 手动建仓
POST   /session/{id}/orders                # 手动加仓/减仓
POST   /session/{id}/close                 # 全部平仓
GET    /session/{id}/events                # session 事件流
GET    /sessions?status=open               # open session 列表
GET    /session/{id}/trade-process         # v1.5 海龟交易过程
```

#### 价格线（2 个 v1.3 核心）

```
GET    /session/{id}/lines?account_id=...  # ★ 实时计算价格线（不持久化）
PUT    /session/{id}/line/{line_type}?account_id=...  # ★ 用户调价
```

#### 回测（3 个）

```
GET    /backtest/runs                      # 回测列表
GET    /backtest/{run_id}                  # 回测详情
GET    /backtest/{run_id}/trades           # 回测成交
```

### 2.3 API 请求/响应示例（v1.4 新增 6 个）

#### POST /session（手动建仓）

**请求**：
```json
{
  "account_id": "sim_001",
  "strategy_id": "turtle_v1",
  "symbol": "AG",
  "contract_code": "ag2607",
  "direction": "long",
  "quantity": 1,
  "order_type": "market",
  "price": null,
  "user_note": "用户手动建仓"
}
```

**响应 200**：
```json
{
  "session_id": "uuid",
  "status": "open",
  "entry_time": "2026-06-02T10:30:00+08:00",
  "entry_basis_price": 7850.0,
  "entry_locked_atr": 120.5,
  "current_units": 1,
  "first_unit_id": "uuid"
}
```

**响应 423**（冲突）：
```json
{
  "error": "session_lock_held",
  "message": "已有信号建仓进行中，请稍后再试",
  "retry_after_ms": 500
}
```

#### POST /session/{id}/orders（加仓/减仓）

**请求**：
```json
{
  "account_id": "sim_001",
  "action": "add",                  // or "reduce"
  "quantity": 1,
  "order_type": "market",
  "price": null,
  "user_note": "加仓到第 2 Unit"
}
```

**响应 200**：
```json
{
  "order_id": "uuid",
  "trade_id": "uuid",
  "unit_id": "uuid",
  "unit_index": 2,
  "filled_price": 7860.0,
  "current_units": 2
}
```

#### GET /session/{id}/lines（实时计算价格线）

**请求**：`GET /session/abc-123/lines?account_id=sim_001`

**响应 200**：
```json
{
  "session_id": "abc-123",
  "kline_range": ["2026-05-15", "2026-06-02"],
  "lines": [
    {
      "line_type": "entry",
      "price": 7850.0,
      "is_override": false,
      "color": "#2196F3"
    },
    {
      "line_type": "stop",
      "price": 7730.0,
      "is_override": false,
      "color": "#F44336"
    },
    {
      "line_type": "add_1",
      "price": 7862.5,
      "is_override": true,             // 用户调整过
      "override_at": "2026-06-01T14:23:00+08:00"
    }
  ]
}
```

---

## 三、服务层（3 大引擎）

### 3.1 撮合引擎（`api/services/sim_engine.py`）

**职责**：
- 接收市价单 / 限价单
- 按 K 线 tick 撮合（最小延迟 = 1 根 K 线 = 1 分钟）
- 返回成交价 / 成交量 / 手续费
- 写 `sim_orders` + `sim_trades`

**核心流程**：
```
1. 接收 OrderRequest
2. 写 sim_orders（status=pending）
3. 等下一根 K 线 tick
4. 市价单：取 K 线 open 价撮合
   限价单：K 线 high/low 是否触及 limit，触及则 limit 价撮合
5. 写 sim_trades
6. 更新 sim_orders（status=filled）
7. 触发 sim_positions 更新
8. 触发 position_units 创建/更新（如果是 session_id 不为空的加仓）
9. 触发 session_event_log 写入
10. 触发 turtle_trade_process 写入（如果是海龟策略）
```

**关键接口**：
```python
async def match_order(order: OrderRequest) -> TradeResult: ...
async def match_market_order(symbol: str, direction: str, quantity: int) -> float: ...
async def match_limit_order(symbol: str, direction: str, quantity: int, limit_price: float) -> Optional[float]: ...
```

### 3.2 Session 生命周期管理器（`api/services/session_lifecycle.py`）

**职责**（v1.4 核心新增）：
- 处理 6 类触发源（信号建仓 / 手动建仓 / 信号加仓 / 手动加仓 / 信号退出 / 手动平仓）
- 维护 `asyncio.Lock`（应用层互斥锁）
- DB 层 UNIQUE 约束兜底
- 触发 session_event_log 写入

**核心流程**：

```
┌─────────────────────────────────────────────────────────────┐
│ 触发源判断（来自 API 路由层）                                │
├─────────────────────────────────────────────────────────────┤
│ 信号触发 → SessionLifecycle.on_signal_xxx()                  │
│ 手动触发 → SessionLifecycle.on_manual_xxx()                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 互斥锁（asyncio.Lock）                                       │
│ session_lock = asyncio.Lock()                                │
│   1. acquire() → DB SELECT (account_id, strategy_id,         │
│                            direction, entry_time) 看是否已 open│
│   2. INSERT trade_sessions（UNIQUE 约束兜底）                │
│   3. release()                                                │
│ 失败 → HTTP 423 + Retry-After 头                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 业务逻辑：                                                    │
│   - 首仓：建 session + 建 unit 1 + 写 entry_basis_price      │
│   - 加仓：复用 session + 建 unit N + 写 entry_basis_price    │
│   - 减仓：复用 session + 关闭 unit N + 算 realized_pnl       │
│   - 全平：关闭 session + 关闭所有 unit + 算 session 总结     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 事件流水：                                                    │
│   session_event_log：entry / add / reduce / close / stop     │
│   turtle_trade_process：海龟专用 10 event_type               │
│   strategy_event_log：策略引擎级事件（信号生成/参数更新）     │
└─────────────────────────────────────────────────────────────┘
```

**关键接口**：
```python
class SessionLifecycle:
    async def on_signal_entry(self, signal: SignalEvent) -> Session: ...
    async def on_signal_add(self, signal: SignalEvent, session: Session) -> Unit: ...
    async def on_manual_entry(self, request: ManualEntryRequest) -> Session: ...
    async def on_manual_add(self, request: ManualAddRequest, session_id: str) -> Unit: ...
    async def on_manual_reduce(self, request: ManualReduceRequest, session_id: str) -> Unit: ...
    async def on_close_all(self, session_id: str) -> Session: ...
```

### 3.3 策略执行器（`strategies/loader.py`）

**职责**（v1.3 核心强化）：
- 动态加载 `strategies/<type>/V<N>/strategy.py`
- 执行策略主循环（每根 K 线触发）
- 写 `strategy_signals`（只 entry_long/entry_short）
- 触发 `strategy_event_log` 写入（v1.4 新增）

**代码组织**：
```
strategies/
├── turtle/
│   ├── V1/strategy.py        # 海龟 V1
│   └── V2/strategy.py        # 海龟 V2（实验性）
├── dual_ma/                  # 未来扩展
│   └── V1/strategy.py
└── loader.py                 # 动态加载器
```

**关键接口**：
```python
class StrategyLoader:
    def load(self, strategy_id: str) -> Strategy: ...  # strategy_id = "turtle_v1"
    def list_versions(self, strategy_type: str) -> List[int]: ...

class Strategy(ABC):
    def on_kline(self, kline: KLine) -> Optional[SignalEvent]: ...
    def on_session_update(self, session: Session) -> None: ...
```

### 3.4 价格线计算服务（`api/services/line_calculator.py`）

**职责**（v1.3 核心新增）：
- 实时计算价格线（不持久化）
- 合并 K 线 + trade_sessions 锁定值 + position_units + price_overrides_json
- 处理 override 优先级

**计算算法**（详见 `0006 §5.3`）：
```
1. 算法基础值
   entry_basis_price ← trade_sessions.entry_basis_price
   stop_price ← 通用：entry_basis_price - 2N
   add_1_price ← entry_basis_price + 0.5N
   add_2_price ← entry_basis_price + 1.0N
   add_3_price ← entry_basis_price + 1.5N
2. 应用 override
   for each (line_type, price) in price_overrides_json:
       lines[line_type].price = price
       lines[line_type].is_override = True
3. 返回
```

### 3.5 事件流写入服务（`api/services/event_logger.py`，v1.4 新增）

**职责**：
- 集中管理 `session_event_log` / `strategy_event_log` / `turtle_trade_process` 三张事件流水表
- 提供统一写入接口
- 异步批量写入（避免阻塞主流程）

**关键接口**：
```python
class EventLogger:
    async def log_session_event(self, session_id: str, event_type: str, context: dict): ...
    async def log_strategy_event(self, strategy_id: str, event_type: str, context: dict): ...
    async def log_turtle_process(self, session_id: str, event_type: str, kline_time: datetime, price: float, context: dict): ...
```

---

## 四、错误码清单

| HTTP | 错误码 | 含义 | 触发场景 | 客户端处理 |
|------|--------|------|---------|-----------|
| 400 | `invalid_request` | 请求参数错误 | 缺少必填字段、字段类型错误 | 弹 Toast 提示 |
| 401 | `unauthorized` | 未登录 / token 过期 | 任何需要鉴权的 API | 跳转登录 |
| 403 | `forbidden` | 无权限 | 跨账户操作非自己的资源 | 弹 Toast 提示 |
| 404 | `not_found` | 资源不存在 | session_id / order_id 不存在 | 弹 Toast 提示 |
| 409 | `conflict` | 状态冲突 | session 已 close 时再次 close | 弹 Toast 提示 |
| **423** | **`session_lock_held`** | **Session 互斥锁被占** | **手动 vs 信号并发** | **Toast 提示 + 自动重试 1 次** |
| 422 | `insufficient_funds` | 资金不足 | 模拟账户余额不够 | 弹 Toast 提示 |
| 422 | `invalid_session_state` | session 状态不允许操作 | close 的 session 上加仓 | 弹 Toast 提示 |
| 429 | `rate_limit_exceeded` | 限流 | 单账户每秒 > 10 次下单 | 自动重试 + 退避 |
| 500 | `internal_error` | 服务内部错误 | DB 异常 / 未捕获异常 | 弹 Toast + 上报 |
| 502 | `bad_gateway` | 撮合引擎无响应 | 撮合服务挂了 | 弹 Toast + 重连 |
| 503 | `service_unavailable` | 服务不可用 | 维护中 / 重启中 | 弹 Toast + 提示稍后重试 |

---

## 五、后端视角的交互（提供什么给前端）

### 5.1 前端需要的核心能力清单

| 能力 | 提供 API | 实时性 |
|------|---------|--------|
| 列出账户 | `GET /accounts` | 启动时 1 次 |
| 列出策略 | `GET /strategies?account_id=...` | 启动时 1 次 |
| 列出 open sessions | `GET /sessions?status=open` | 启动时 1 次 + 手动刷新 |
| 列出合约（品种下）| `GET /contracts/{symbol}` | 启动时 1 次 |
| 实时行情 | `GET /quotes/{contract_code}` | **每 3 秒轮询** |
| 日 K 线 | `GET /futures/daily?contract_code=...&start_date=...&end_date=...` | 进入品种时 1 次 |
| 分 K 线 | `GET /futures/min?contract_code=...&date=...` | 进入品种时 1 次 |
| 当前信号 | `GET /strategy/signal/state/{sym}?strategy_id=...` | **每 5 秒轮询** |
| Session 详情 | `GET /sim/sessions?account_id=...&strategy_id=...` | 手动刷新 |
| 持仓列表 | `GET /sim/positions?account_id=...` | **每 5 秒轮询** |
| 委托 / 成交 | `GET /sim/orders?account_id=...&sim/trades?account_id=...` | 手动刷新 |
| 价格线 | `GET /session/{id}/lines?account_id=...` | 进入 session 详情时 1 次 |
| 调价 | `PUT /session/{id}/line/{line_type}?account_id=...` | 用户拖动价格线时 |
| 建仓 | `POST /session` | 用户点击"建仓"按钮 |
| 加仓 / 减仓 | `POST /session/{id}/orders` | 用户点击"加仓/减仓"按钮 |
| 全部平仓 | `POST /session/{id}/close` | 用户点击"全部平仓"按钮 |
| Session 事件流 | `GET /session/{id}/events` | 进入 session 详情时 1 次 |
| 海龟交易过程 | `GET /session/{id}/trade-process` | 进入 session 详情时 1 次（v1.5）|

### 5.2 推送 vs 轮询决策

| 数据 | 决策 | 原因 |
|------|------|------|
| 行情（`/quotes`）| **轮询 3 秒** | 简单可控，WebSocket 复杂度高 |
| 信号（`/signal/state`）| **轮询 5 秒** | 同上 |
| 持仓（`/sim/positions`）| **轮询 5 秒** | 同上 |
| 事件流（`/session/{id}/events`）| **轮询 10 秒** | 事件流变化频率不高 |
| 海龟过程（`/session/{id}/trade-process`）| **轮询 10 秒** | 同上 |

> **未来优化**：Phase 6+ 可考虑 WebSocket 推送，本次需求先用轮询。

### 5.3 后端 → 前端数据格式约定

**所有列表 API**：
```json
{
  "data": [...],
  "total": 123,
  "page": 1,
  "page_size": 50,
  "has_more": true
}
```

**所有详情 API**：
```json
{
  "data": {...}
}
```

**错误响应**：
```json
{
  "error": "error_code",
  "message": "人类可读消息",
  "details": {...}  // 可选
}
```

**时间格式**：ISO 8601 + 时区（`2026-06-02T10:30:00+08:00`）
**金额格式**：浮点数，2 位小数（`7850.00`）
**数量格式**：整数（`1`）
**UUID 格式**：标准 UUID v4（`abc-123-def-456`）

---

## 六、性能与可扩展性

### 6.1 性能目标

| 指标 | 目标 |
|------|------|
| API P99 延迟 | < 200ms |
| 行情轮询响应 | < 50ms |
| Session 详情加载 | < 500ms |
| 价格线计算 | < 100ms |
| 海龟过程流水查询（1000 行）| < 300ms |

### 6.2 数据保留与清理

| 表 | 保留期 | 清理策略 |
|----|--------|---------|
| `futures_daily` | 3 年（1095 天）| 定时任务每周清理 |
| `futures_min` | 半年（180 天）| 定时任务每天清理 |
| `strategy_signals` | 1 年 | 定时任务每周清理 |
| `strategy_event_log` | 1 年 | 定时任务每周清理 |
| `session_event_log` | 1 年 | 定时任务每周清理 |
| `turtle_trade_process` | 1 年 | 定时任务每周清理 |
| `sim_orders` / `sim_trades` | 永久 | 不清理（核心数据）|
| `trade_sessions` | 永久 | 不清理 |
| `position_units` | 永久 | 不清理 |
| `backtest_runs` | 永久 | 不清理 |

### 6.3 索引策略（已建 + 待建）

**已建**（见 §1.1 表清单）：
- 主键索引（自动）
- 外键索引
- 业务唯一索引（trade_sessions UNIQUE）
- 部分索引（trade_sessions idx_ts_status_open）

**待建**（Phase 1-3 实施时确认）：
- `idx_ttp_session_time`（turtle_trade_process）
- `idx_sesl_session_at`（session_event_log）
- `idx_sel_strategy_at`（strategy_event_log）

---

## 七、与前端 / 整合的衔接

- **前端**：详见 `03-frontend.md`
- **联调 / 错误 / 性能 / 部署**：详见 `04-integration.md`
- **总体设计**：详见 `01-overall.md`
- **主设计文档**（最详细）：`../../0006_数据模型与界面重构设计.md`

---

## 八、建表 SQL（提炼自 0006 §4，节选核心字段）

> 完整建表脚本与 0006 §4 同步，本节为 22 张表的精简 SQL（保留约束 + 索引 + 注释）。

### 8.1 领域 1：合约行情（4 张）

**`futures_contracts`** — 合约静态信息

```sql
-- 表用途：每个品种下所有合约的静态信息（代码/交易所/到期日/主力标记）
-- 写入方：data_loader.sync_all_minute_data 时通过 Sina 接口刷新
CREATE TABLE futures_contracts (
    contract_code TEXT PRIMARY KEY,
    symbol        TEXT NOT NULL,
    name          TEXT,
    exchange      TEXT NOT NULL,
    list_date     TEXT,
    expire_date   TEXT,
    is_main       INTEGER DEFAULT 0,
    main_rank     INTEGER DEFAULT 99,
    contract_size REAL,
    point_value   REAL,
    tick          REAL,
    margin_ratio  REAL,
    last_volume   REAL,
    last_oi       REAL,
    updated_at    TEXT,
    status        TEXT DEFAULT 'active'
);
CREATE INDEX idx_fc_symbol ON futures_contracts(symbol);
CREATE INDEX idx_fc_main ON futures_contracts(symbol, is_main);
```

**`futures_quotes`** — 合约实时行情（30s 刷新一次）

```sql
CREATE TABLE futures_quotes (
    contract_code TEXT PRIMARY KEY,
    symbol        TEXT NOT NULL,
    trade         REAL, change_abs REAL, change_pct REAL,
    open          REAL, high REAL, low REAL,
    preclose      REAL, presettlement REAL, settlement REAL,
    volume        REAL, position REAL,
    bidprice1     REAL, askprice1 REAL,
    bidvol1       REAL, askvol1 REAL,
    ticktime      TEXT, updated_at TEXT
);
```

**`futures_daily`** — 日 K 线（★ v1.3 调整）

```sql
-- v1.3 关键调整：
--   1. 保留期：14 天 → 3 年（策略回测需长期历史）
--   2. 新增字段：atr（合并 futures_atr，吸纳后删除该表）
--   3. 新增字段：main_contract_code（主力合约动态识别）
-- 性能估算：3 年 × 33 品种 × 250 交易日/年 ≈ 24,750 行
CREATE TABLE futures_daily (
    symbol             TEXT NOT NULL,
    date               TEXT NOT NULL,
    open               REAL, high REAL, low REAL, close REAL,
    volume             REAL, hold REAL, settle REAL,
    atr                REAL,                    -- ★ v1.3 新增
    main_contract_code TEXT,                    -- ★ v1.3 新增
    cached_at          TEXT,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX idx_fd_symbol ON futures_daily(symbol, date);
CREATE INDEX idx_fd_main_contract ON futures_daily(main_contract_code);
```

**`futures_min`** — 分钟 K 线（★ v1.3 调整）

```sql
-- v1.3 关键调整：
--   1. 保留期：7 天 → 半年（180 天）
--   2. 新增字段：date（从 datetime 派生，便于与 futures_daily 关联）
-- 性能估算：半年 × 33 品种 × 240 根/天 = 1,425,600 行
CREATE TABLE futures_min (
    symbol        TEXT NOT NULL,
    datetime      TEXT NOT NULL,
    date          TEXT NOT NULL,        -- ★ v1.3 新增派生字段
    open          REAL, high REAL, low REAL, close REAL,
    volume        REAL,
    period        TEXT DEFAULT '5min',
    contract_code TEXT DEFAULT '',
    name          TEXT DEFAULT '',
    cached_at     TEXT,
    PRIMARY KEY (symbol, datetime)
);
CREATE INDEX idx_fm_symbol_date ON futures_min(symbol, date);
CREATE INDEX idx_fm_symbol ON futures_min(symbol, datetime);
```

### 8.2 领域 2：策略（4 张核心 + 2 张 v1.4+ 新增）

**`strategies`** — 策略主表（v1.3 +version +type）

```sql
-- 主键 = name_vN 形式（如 turtle_v1）
-- v1.3 新增：type 字段对应代码目录 strategies/<type>/V<version>/
CREATE TABLE strategies (
    strategy_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    version      INTEGER NOT NULL DEFAULT 1,
    type         TEXT NOT NULL,
    description  TEXT,
    params_json  TEXT,
    is_active    INTEGER DEFAULT 1,
    is_paper     INTEGER DEFAULT 1,
    created_at   TEXT,
    updated_at   TEXT,
    UNIQUE (name, version)
);
-- 预置种子数据
INSERT INTO strategies VALUES
    ('turtle_v1', '海龟T1', 1, 'turtle',
     '经典海龟系统二，55日突破/20日反向/0.5N加仓/2N止损',
     '{"entry_n":55,"exit_n":20,"add_interval":0.5,"stop_loss":2,"atr_n":20,"max_units":4,"risk_per_trade":2000}',
     1, 1, datetime('now'), datetime('now')),
    ('dual_ma_v1', '双均线', 1, 'dual_ma',
     '快慢均线交叉信号',
     '{"fast":10,"slow":20}', 0, 1, datetime('now'), datetime('now'));
```

**`strategy_param_history`** — 参数迭代历史

```sql
CREATE TABLE strategy_param_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id   TEXT NOT NULL,
    name          TEXT NOT NULL,
    version       INTEGER NOT NULL,
    params_json   TEXT NOT NULL,
    changed_at    TEXT NOT NULL,
    changed_by    TEXT,
    change_reason TEXT,
    notes         TEXT
);
CREATE INDEX idx_sph_strategy ON strategy_param_history(strategy_id, version);
```

**`strategy_signals`** — 开仓信号流水（★ v1.3 精简）

```sql
-- v1.3 重要调整：
--   1. 删除 signal_session_id（信号与会话是 1 对多）
--   2. signal_type 限制为只 2 个枚举：entry_long / entry_short
--   3. 不需要 phase 字段（phase 属于 session 不是 signal）
CREATE TABLE strategy_signals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id       TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    name              TEXT,
    contract_code     TEXT,
    signal_type       TEXT NOT NULL,         -- entry_long / entry_short
    direction         TEXT NOT NULL,
    trigger_price     REAL NOT NULL,
    reference_price   REAL NOT NULL,
    reference_n       REAL,
    bar_time          TEXT NOT NULL,
    period            TEXT DEFAULT '5min',
    alert_level       TEXT DEFAULT 'normal',
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(strategy_id, symbol, signal_type, bar_time)
);
CREATE INDEX idx_ss_strategy ON strategy_signals(strategy_id, bar_time);
CREATE INDEX idx_ss_active ON strategy_signals(strategy_id, symbol, direction, alert_level);
```

**`strategy_event_log`**（v1.4 新增）— 策略执行引擎事件流水

```sql
CREATE TABLE strategy_event_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id   TEXT NOT NULL,
    event_type    TEXT NOT NULL,            -- signal_detected / signal_skipped / param_updated / engine_started / engine_stopped
    event_at      TEXT NOT NULL,
    symbol        TEXT,
    context_json  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_sel_strategy_at ON strategy_event_log(strategy_id, event_at);
```

**`turtle_trade_process`**（v1.5 新增）— 海龟逐根 K 线决策流水

```sql
-- 10 个 event_type：entry_signal / entry_filled / add_signal / add_filled / add_skipped_gap
--                  / stop_loss_check / stop_loss_triggered / check_exit / exit_20_triggered / unit_closed
-- check 类事件优化存储（C 方案）：触发时存前后 5 根 K 线
CREATE TABLE turtle_trade_process (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    account_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    bar_time        TEXT NOT NULL,
    bar_open        REAL, bar_high REAL, bar_low REAL, bar_close REAL,
    signal_type     TEXT,
    signal_price    REAL,
    reference_price REAL,
    n_value         REAL,
    unit_id         INTEGER,
    exec_status     TEXT,                    -- pending / filled / skipped / failed
    exec_price      REAL,
    exec_hand_count INTEGER,
    exec_time       TEXT,
    slippage        REAL,
    is_gap          INTEGER DEFAULT 0,
    gap_size        REAL,
    decision_reason TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES trade_sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX idx_ttp_session ON turtle_trade_process(session_id, bar_time);
CREATE INDEX idx_ttp_type ON turtle_trade_process(event_type, bar_time);
CREATE INDEX idx_ttp_bar ON turtle_trade_process(bar_time);
```

### 8.3 领域 3：交易 / 账户（核心 4 张 + 子策略 1 + 事件 1 + 预留 3 + 补 1）

**`sim_account`** — 模拟账户（v1.3 新增 user_id / display_name）

```sql
CREATE TABLE sim_account (
    account_id     TEXT PRIMARY KEY,
    user_id        TEXT,
    display_name   TEXT,
    name           TEXT,
    balance        REAL DEFAULT 1000000.0,
    available      REAL DEFAULT 1000000.0,
    margin_used    REAL DEFAULT 0.0,
    realized_pnl   REAL DEFAULT 0.0,
    unrealized_pnl REAL DEFAULT 0.0,
    platform_name  TEXT DEFAULT 'sim',
    created_at     TEXT,
    updated_at     TEXT
);
```

**`trade_sessions`** — 交易主表（v1.3 +account_id +price_overrides_json +UNIQUE）

```sql
-- v1.3 新增：account_id / first_entry_price / price_overrides_json
-- v1.3 新增：UNIQUE (account_id, strategy_id, direction, entry_time)
CREATE TABLE trade_sessions (
    session_id          TEXT PRIMARY KEY,             -- UUID
    account_id          TEXT NOT NULL,
    strategy_id         TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    contract_code       TEXT,
    direction           TEXT NOT NULL,                -- long / short
    status              TEXT NOT NULL,                -- pending / open / closed
    entry_time          TEXT NOT NULL,
    exit_time           TEXT,
    first_entry_price   REAL,
    current_units       INTEGER DEFAULT 0,
    total_units         INTEGER DEFAULT 0,
    entry_basis_price   REAL,                         -- 通用语义（建仓参考价）
    entry_locked_atr    REAL,                         -- 通用语义（锁定 N 值）
    price_overrides_json TEXT DEFAULT '{}',           -- 用户调价
    exit_reason         TEXT,
    realized_pnl        REAL,
    user_note           TEXT,
    created_at          TEXT,
    updated_at          TEXT,
    UNIQUE (account_id, strategy_id, direction, entry_time)
);
CREATE INDEX idx_ts_account_status ON trade_sessions(account_id, status);
CREATE INDEX idx_ts_status_open ON trade_sessions(status) WHERE status = 'open';  -- 部分索引
```

**`sim_orders` / `sim_trades` / `sim_positions` / `position_units`** — 委托/成交/持仓

```sql
-- sim_orders：手动/自动委托
CREATE TABLE sim_orders (
    order_id          TEXT PRIMARY KEY,               -- UUID
    account_id        TEXT NOT NULL,
    session_id        TEXT,                           -- 可空（手动建仓前为 NULL）
    symbol            TEXT NOT NULL,
    contract_code     TEXT,
    direction         TEXT NOT NULL,                  -- buy / sell
    order_type        TEXT NOT NULL,                  -- market / limit
    quantity          INTEGER NOT NULL,
    price             REAL,                           -- 限价单必填
    status            TEXT NOT NULL,                  -- pending / filled / cancelled / rejected
    filled_quantity   INTEGER DEFAULT 0,
    avg_filled_price  REAL,
    platform_name     TEXT DEFAULT 'sim',
    external_order_id TEXT,
    created_at        TEXT,
    updated_at        TEXT
);
CREATE INDEX idx_so_account_time ON sim_orders(account_id, created_at);

-- sim_trades：成交明细
CREATE TABLE sim_trades (
    trade_id          TEXT PRIMARY KEY,               -- UUID
    order_id          TEXT NOT NULL,
    account_id        TEXT NOT NULL,
    session_id        TEXT,
    symbol            TEXT NOT NULL,
    contract_code     TEXT,
    direction         TEXT NOT NULL,
    filled_price      REAL NOT NULL,
    filled_quantity   INTEGER NOT NULL,
    commission        REAL DEFAULT 0.0,
    platform_name     TEXT DEFAULT 'sim',
    external_trade_id TEXT,
    filled_at         TEXT
);
CREATE INDEX idx_st_account_time ON sim_trades(account_id, filled_at);

-- sim_positions：品种维度持仓汇总
CREATE TABLE sim_positions (
    account_id      TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    contract_code   TEXT,
    quantity        INTEGER DEFAULT 0,
    avg_cost        REAL DEFAULT 0.0,
    realized_pnl    REAL DEFAULT 0.0,
    unrealized_pnl  REAL DEFAULT 0.0,
    last_price      REAL,
    updated_at      TEXT,
    PRIMARY KEY (account_id, symbol)
);

-- position_units：4 Unit 详情（★ v1.3 +account_id +海龟字段）
-- 海龟字段加注释：entry_basis_price / entry_atr / stop_price 目前主要是海龟使用，其他策略可忽略
CREATE TABLE position_units (
    unit_id           TEXT PRIMARY KEY,               -- UUID
    session_id        TEXT NOT NULL,
    account_id        TEXT NOT NULL,
    unit_index        INTEGER NOT NULL,               -- 1-4
    open_price        REAL NOT NULL,
    current_price     REAL,
    stop_price        REAL,                           -- 海龟字段（加注释）
    entry_basis_price REAL,                           -- 海龟字段
    entry_atr         REAL,                           -- 海龟字段
    open_hand_count   INTEGER NOT NULL,
    close_price       REAL,
    close_time        TEXT,
    close_hand_count  INTEGER,
    status            TEXT NOT NULL,                  -- open / closed / stopped
    is_gap            INTEGER DEFAULT 0,              -- 跳空标志
    created_at        TEXT,
    updated_at        TEXT
);
CREATE INDEX idx_pu_session ON position_units(session_id);
CREATE INDEX idx_pu_account ON position_units(account_id);
```

**`turtle_session_data`**（v1.4 新增）— 海龟 session 特有事实（7 字段）

```sql
-- 1:1 关联 trade_sessions.session_id
-- 7 字段：3 锁定值 + 2 计数器 + 2 事件标志
-- v1.4 决策：去 max_units_reached（由 trade_sessions.current_units 实时算）
CREATE TABLE turtle_session_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL UNIQUE,
    -- 3 个锁定值（建仓瞬间写死）
    entry_55d_high      REAL,
    entry_55d_low       REAL,
    entry_atr_20        REAL,
    -- 2 个计数器（实时 UPDATE）
    add_count           INTEGER DEFAULT 0,
    skip_add_count      INTEGER DEFAULT 0,
    -- 2 个事件标志
    is_gap_entry        INTEGER DEFAULT 0,
    is_breakout_confirm INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_tsd_session ON turtle_session_data(session_id);
```

**`session_event_log`**（v1.4 新增）— session 生命周期事件流水（8 event_type）

```sql
-- 8 个 event_type：created / opened / added / reduced / closed / stop_loss_triggered / exit_20_triggered / unit_closed
CREATE TABLE session_event_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    account_id    TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    event_at      TEXT NOT NULL,
    unit_id       TEXT,
    trade_id      TEXT,
    context_json  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_sesl_session_at ON session_event_log(session_id, event_at);
```

**`live_orders` / `live_trades` / `live_positions`** — 真实交易预留（v1.3 强化）

```sql
-- live_* 三表与 sim_* 同构，预留字段：ctp_order_ref / ctp_front_id / ctp_session_id / external_trade_id
-- v1.5 状态：未启用（Phase 7 可选 CTP 接入）
```

### 8.4 跨领域（1 张）

```sql
-- backtest_runs：回测任务
CREATE TABLE backtest_runs (
    run_id               TEXT PRIMARY KEY,
    strategy_id          TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    start_date           TEXT NOT NULL,
    end_date             TEXT NOT NULL,
    params_json          TEXT,
    result_metrics_json  TEXT,
    status               TEXT NOT NULL,               -- running / completed / failed
    created_at           TEXT,
    completed_at         TEXT
);
CREATE INDEX idx_br_strategy_at ON backtest_runs(strategy_id, created_at);
```

---

## 九、价格线计算算法（提炼自 0006 §5.3）

> 完整 Python 实现见主设计文档 0006 §5.3，本节为后端视角的算法分解。

### 9.1 输入

```python
def compute_session_lines(account_id: str, session_id: str) -> dict:
    session = get_trade_session(account_id, session_id)
    strategy = get_strategy(session.strategy_id)
    params = parse_json(strategy.params_json)
    overrides = parse_json(session.price_overrides_json) or {}
    
    direction = session.direction
    locked_atr = session.entry_locked_atr
    max_units = params.get('max_units', 4)
    add_step = params.get('add_interval', 0.5) * locked_atr
    open_units = get_open_position_units(account_id, session_id)
    last_unit = open_units[-1] if open_units else None
```

### 9.2 计算步骤（6 步）

```
1. 读基础事实（trade_sessions + position_units + strategy.params + K 线）
2. 已成交 entry：使用 actual_fill（actual first_entry_price）
   未成交 entry：使用 signal 价（session.entry_basis_price） + override
3. 加仓线（4 个）：
   - 已成交：用 actual_fill
   - 未成交：基于 last_unit 计算（base_price + direction × n × add_step）+ override
4. 止损线（每个 unit 一条，动态阶梯）：
   - 算法：unit_n.stop = unit_n.entry_price - direction × (2 × locked_atr - n × add_step)
   - 简化版：每个加仓后止损上调 0.5N
   - 已关闭 unit：is_active=0（前端的"激活"过滤）
5. exit_20 线：
   - 多头：get_20_day_low(symbol)
   - 空头：get_20_day_high(symbol)
6. 合并 override（仅对未成交的信号线生效）
```

### 9.3 override 优先级规则

| 状态 | 应用 override？ | 来源 |
|------|----------------|------|
| 已成交（actual_fill）| ❌ 不应用 | `position_units.entry_price` |
| 未成交（信号线）| ✅ 应用 | `price_overrides_json[line_type]` |

**示例**：
- `add_unit_2` 还没成交，用户拖到 18880 → override 生效，K 线图显示 18880
- `add_unit_2` 实际成交 @ 18860 → 用 18860（actual_fill），忽略之前的 override
- 子线（add_unit_3, 4）重新计算：基于 last_unit=add_unit_2 实际成交价

### 9.4 价格线生命周期

| 阶段 | 状态 | 显示线 |
|------|------|--------|
| 信号触发 entry_long（pending）| pending | entry（signal，虚线）+ 其他隐藏 |
| 实际成交（open）| open | entry（actual_fill，实线）+ add_unit_1..4 + stop_loss + exit_20 |
| 用户拖动 add_unit_1 → 18830 | open | override 生效，K 线图重算 |
| 加仓 1 成交 @ 18870 | open | add_unit_1=18870（actual）+ 子线重算 |
| 止损触发 | closed | 所有 is_active=0，仅 stop_loss 实线 + is_triggered |
| 全部平仓 | closed | 不显示价格线 |

---

## 十、用户调价 API（提炼自 0006 §5.4）

### 10.1 请求与响应

```
PUT /session/{session_id}/line/{line_type}?account_id=...
Content-Type: application/json

{
  "new_price": 18830
}
```

**响应 200**：
```json
{
  "success": true,
  "line_type": "add_unit_1",
  "new_price": 18830,
  "override_at": "2026-06-02T15:23:00+08:00"
}
```

**响应 422（状态不允许）**：
```json
{
  "error": "invalid_session_state",
  "message": "Cannot override line in status closed"
}
```

### 10.2 校验逻辑

```python
def override_line_price(account_id, session_id, line_type, new_price):
    # 1. 校验 line_type
    VALID_LINE_TYPES = {'entry', 'add_unit_1', 'add_unit_2', 'add_unit_3', 'add_unit_4',
                        'stop_loss_unit_1', 'stop_loss_unit_2', 'stop_loss_unit_3', 'stop_loss_unit_4',
                        'exit_20'}
    if line_type not in VALID_LINE_TYPES:
        raise ValueError(f"Invalid line_type: {line_type}")
    
    # 2. 校验 session 存在
    session = get_trade_session(account_id, session_id)
    if session is None:
        raise ValueError("Session not found")
    
    # 3. 校验 session 状态
    if session.status not in ('open', 'pending'):
        raise ValueError(f"Cannot override line in status {session.status}")
    
    # 4. 更新 price_overrides_json
    overrides = parse_json(session.price_overrides_json) or {}
    overrides[line_type] = new_price
    
    UPDATE trade_sessions
    SET price_overrides_json = json.dumps(overrides),
        updated_at = datetime('now')
    WHERE account_id=? AND session_id=?
    
    return {"success": True, "line_type": line_type, "new_price": new_price}
```

---

## 十一、Session 生命周期状态机（提炼自 0006 §7.5）

### 11.1 触发源矩阵（6 类）

| # | 触发源 | session 来源 | 实现位置 | 互斥锁 | HTTP 状态 |
|---|--------|-------------|---------|--------|----------|
| 1 | 信号触发开仓（entry_long/entry_short）| 新建 | 策略执行器 → on_signal_entry | session_lock | 200 |
| 2 | 手动建仓（POST /session）| 新建 | API 路由 → on_manual_entry | session_lock | 200 / 423 |
| 3 | 信号触发加仓（add_unit_N）| 复用 open | 策略执行器 → on_signal_add | session_lock | 200 |
| 4 | 手动加仓/减仓（POST /session/{id}/orders）| 复用指定 session | API 路由 → on_manual_add/reduce | session_lock | 200 / 423 |
| 5 | 信号触发止损/退出（stop_loss/exit_20）| 复用 open | 策略执行器 → on_signal_close | session_lock | 200 |
| 6 | 全部平仓（POST /session/{id}/close）| 复用指定 session | API 路由 → on_close_all | session_lock | 200 / 409 |

### 11.2 状态机图

```
[无 session]
    ↓ (触发源 1/2：信号建仓 / 手动建仓)
[pending]
    ↓ (撮合成交 first_entry_price)
[open] ←─────┐
    ↓        │ (触发源 3/4：加仓/减仓)
    │  current_units: 1 → 2 → 3 → 4
    ↓
[closed] (触发源 5/6：止损/退出/全平)
    ↓ exit_reason: stop_loss / exit_20 / manual
[closed] (终态)
```

### 11.3 唯一性约束（双层）

**DB 层**：
```sql
UNIQUE (account_id, strategy_id, direction, entry_time)
```

**应用层**：
```python
session_lock = asyncio.Lock()

async def on_signal_entry(signal):
    async with session_lock:
        # 1. DB SELECT 看是否已 open
        existing = SELECT * FROM trade_sessions
                    WHERE account_id=? AND strategy_id=? AND direction=? AND status='open'
        if existing:
            raise SessionLockHeld()  # 实际是 OK（继续加仓）还是拒绝？
        # 2. INSERT trade_sessions（UNIQUE 约束兜底）
        INSERT INTO trade_sessions ...
```

**互斥失败处理**：
- HTTP 423 + Retry-After 头
- 前端自动重试 1 次（500ms 后）

---

## 十二、跨领域协同实现（提炼自 0006 §4.6）

### 12.1 协同矩阵

| 协同方向 | 触发条件 | 读 | 写 | 关键字段 |
|---------|---------|----|----|---------|
| 合约 → 策略 | K线更新 | `futures_min` / `futures_daily` | — | OHLC |
| 合约 → 交易 | 行情刷新 | `futures_quotes` | `sim_trades.price` | trade |
| 交易 → 策略 | 策略执行 | `trade_sessions` / `position_units` | — | locked_atr, basis_price, current_units |
| 策略 → 交易 | 信号触发 | — | `sim_orders` | signal_type, direction, hand_count |
| 撮合 → 交易 | 成交发生 | — | `sim_trades` + `trade_sessions` + `position_units` + `sim_positions` | 价格/手续费 |
| 策略 → 信号表 | 信号触发（仅开仓）| — | `strategy_signals` | signal_type |
| 交易 → 合约 | 价格线计算 | `trade_sessions` + `position_units` | 实时算（不写库）| entry_basis_price, locked_atr, current_units |
| 合约 → 价格线 | 价格线计算 | `futures_daily` / `futures_min` | 实时算 | 20日高/低 |

### 12.2 关键 JOIN 查询

```sql
-- 1. 信号状态（实时 JOIN 算）
SELECT
    ts.session_id, ts.symbol, ts.direction, ts.status,
    ss.signal_type, ss.trigger_price, ss.bar_time
FROM trade_sessions ts
LEFT JOIN strategy_signals ss
    ON ss.strategy_id = ts.strategy_id
    AND ss.symbol = ts.symbol
    AND ss.bar_time >= ts.entry_time
WHERE ts.account_id = ? AND ts.status = 'open'
ORDER BY ss.bar_time DESC LIMIT 1;

-- 2. 价格线计算（实时 JOIN）
SELECT
    ts.entry_basis_price, ts.entry_locked_atr, ts.direction,
    pu.unit_id, pu.unit_index, pu.open_price, pu.stop_price
FROM trade_sessions ts
LEFT JOIN position_units pu
    ON pu.session_id = ts.session_id AND pu.status = 'open'
WHERE ts.session_id = ? AND ts.account_id = ?
ORDER BY pu.unit_index;

-- 3. K 线 JOIN
SELECT d.*, m.datetime, m.open AS m_open
FROM futures_daily d
LEFT JOIN futures_min m ON m.symbol = d.symbol AND m.date = d.date
WHERE d.symbol = ? AND d.date BETWEEN ? AND ?
ORDER BY d.date DESC, m.datetime ASC;
```

---

*本文档是 _requirements/data-model-redesign/01-design/ 下的后端设计（v1.5），与主设计文档（0006）保持一致。*
