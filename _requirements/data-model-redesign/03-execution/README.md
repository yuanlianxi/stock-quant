# 阶段 3：执行

> 当前状态：🔄 **Phase 1 已实质完成**（2026-06-07 实施，非走本 plan 流程）；Phase 2-6 待派
> 进入条件：02-plan/plan.md 审核通过 ✅
> 文档版本：v0.1.0（2026-06-14 补 Phase 1 实际记录）

---

## Phase 1：合约行情领域（**2026-06-07 已实质完成**）

### ⚠️ 重要说明

**Phase 1 实施时间：2026-06-07**，早于 plan 工具栈对齐 v0.18.13（2026-06-14）。
实施时走的是 **sq-0009 缓存层优化流程**（缓存层 sq-0009 涉及 contracts/quotes/daily/min 数据层），不是走本 data-model plan 流程——所以本 README 没及时回写。

**实际进度 100%**（15 项验收点全过）：

### 数据层

- ✅ `futures_contracts` 新增表（`data/data_loader.py` CREATE TABLE + 索引 `idx_fc_symbol` / `idx_fc_main`）
- ✅ `futures_quotes` 新增表
- ✅ `futures_daily` 加 `atr` + `main_contract_code`（`_add_column_if_not_exists` + 索引 `idx_fd_main_contract`）
- ✅ `futures_min` 加 `date` 字段
- ✅ `futures_atr` 表删除（ATR 数据已迁移到 `futures_daily.atr`）
- ✅ **retention 拉长**：`DAILY_RETENTION_DAYS = 1095`（3 年）/ `MIN_RETENTION_DAYS = 180`（半年）
  - 注释明确：`v1.5 从 62 调至 1095` / `v1.5 从 7 调至 180`
- ✅ `backfill_min_history(180 天)` + 3 年日线回填（"缓存不足 60 条时自动回填 3 年历史"）

### API 层

- ✅ `GET /contracts/{symbol}`（`api/routers/market.py:55`，注释"Phase 1.3"）
- ✅ `GET /quotes/{contract_code}`（`market.py:100`）
- ✅ `GET /main-contract/{symbol}`（`market.py:135`，plan 未列，bonus）
- ✅ `GET /daily/{symbol}` + `POST /daily/sync`（`market.py:209/224`）
- ✅ `GET /minute/{symbol}` + `POST /minute/sync`（`market.py:178/192`）

### 前端

- ✅ **ContractDrawer.vue 组件**（`webapp/src/views/ContractDrawer.vue`）
- ✅ **品种网格"📋 N 合约"角标**（`webapp/src/views/MarketGrid.vue:180` 注释 + `contractMap` 拉取逻辑）
- ✅ `contractsApi` service 封装

### 主力合约识别

- ✅ 主力识别函数（`data/data_loader.py` 主力合约识别逻辑）
- ✅ `strategies/executor.py` 引用 `main_contract` 字段

### 验收（端到端可跑）

- ✅ AG 卡片 → 弹 4 个合约报价（`/contracts/AG` 返 4 个 + main_contract 高亮）
- ✅ 日线 retention 3 年（DAILY_RETENTION_DAYS = 1095）
- ✅ 分时 retention 半年（MIN_RETENTION_DAYS = 180）
- ✅ 主力合约高亮（is_main + main_rank）
- ✅ MarketGrid 角标 + ContractDrawer 链路打通

### 实施时间线

| 时间 | 动作 |
|------|------|
| 2026-06-07 实施前 | `data/data_loader.py.bak.20260607-pre-p1` 备份（实施前快照）|
| 2026-06-07 | 实施 Phase 1（4 张表 + 索引 + 迁移 + retention 调整）|
| 2026-06-14 | 0007 v1.6 完工，新增 `webapp/src/views/ContractDrawer.vue`（前端组件）|

### 备注

- Phase 1 实施时 data-model 02-plan 还没审核通过——属于"计划前的实施"
- 这是 **sq-0009 缓存层优化**的副产物（缓存层需要 contracts/daily/min 表）
- 走 data-model plan 流程时，Phase 2-6 仍按 plan 执行

---

## Phase 2-6：⏳ 待派发

| Phase | 名称 | 工作日 | 派发状态 |
|------|------|--------|---------|
| **2** | **策略领域** | 🔄 **部分完成** | **v0.18.14 收尾** |
| 3 | 交易 / 账户领域 | 10-12 | ⏳ 待派 |
| 4 | 回测持久化 | 3 | ⏳ 待派 |
| 5 | 账户中心页 | 2 | ⏳ 待派 |
| 6 | 单元 + 集成测试 | 2-3 | ⏳ 待派 |

**合计**：20-23 工作日（Phase 2-6，Phase 1 已实施省 3-4 天）

---

## Phase 2 收尾（v0.18.14，2026-06-14）

### 实施内容

| 任务 | 实际 |
|------|------|
| 后端 1 端点 | ✅ `GET /strategies/{strategy_id}/trade-process`（strategy.py 8→9 端点）|
| 前端 TopBar.vue | ✅ 新建 157 行（5 Tab + 策略/账户下拉 + 4 操作 + 2 入口）|
| 前端 App.vue 集成 | ✅ 5 Tab 切换 + 模拟 Tab = MarketGrid + SymbolDetail + 4 placeholder Tab |
| 6 项 curl 验证 | ✅ 全过 |

### 与 plan §二 Phase 2 范围对比

| Plan 项 | 实际 |
|------|------|
| 6 张表 | ✅ 5 张实表（strategy_signal_states v1.3 已删）+ 1 张已删 |
| 7 个 API | ⚠️ 9 个端点（plan 列 7 个 + bonus `param-history` + `events`），含新 `trade-process` |
| 顶部策略下拉 | ✅ TopBar.vue 实现（连 useStrategyStore）|
| 策略历史页 | ⚠️ 占位（Phase 3 trade_sessions 没建，StrategyHistoryPanel 需 strategyId prop）|
| V1/V2 隔离 | ⚠️ V1 就绪（V1/strategy.py + loader.py）/ V2 未实现 |
| V1 position.py 迁移 | ❌ 不做（4 个 active 文件引用 PositionManager，需保留兼容）|

### 缺口（留待 Phase 3 或单独 hotfix）

- ❌ V2 策略实现（`strategies/turtle/V2/strategy.py`）
- ❌ 4 placeholder Tab 替换为真实 view
- ❌ `StrategyHistoryPanel` / `TradeProcessTimeline` 真实数据接入（需 Phase 3 trade_sessions）
- ❌ trade-process 端点切换为 JOIN strategy_id 严格过滤（需 Phase 3）

### 负责人

- **Phase 1 实施**：Blex（走 sq-0009 流程，2026-06-07）
- **Phase 2 收尾**：Blex（v0.18.14，2026-06-14）
- **Phase 2-6 派发**：（待用户拍板）

---

*本文档 2026-06-14 补充 Phase 1 + Phase 2 收尾实际执行记录。Phase 3-6 仍按 02-plan/plan.md 执行。*
