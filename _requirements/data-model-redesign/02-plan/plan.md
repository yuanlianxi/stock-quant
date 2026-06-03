# 02-Plan：数据模型重构执行计划

> 文档版本：v0.1.0（待审核）
> 创建日期：2026-06-03
> 负责人：Alex + Blex
> 状态：⏳ **待审核**（用户拍板后进入执行阶段）
> 关联文档：
> - 设计事实源：`/home/yuan/.openclaw/workspace/projects/stock-quant/0006_数据模型与界面重构设计.md`（v1.5）
> - 设计拆分：`_requirements/data-model-redesign/01-design/01-overall.md ~ 05-project-structure.md`
> - 子计划参考：`01-design/04-integration.md` §四 Phase 1-7

---

## 一、计划目标

按 v1.5 设计把 stock-quant 数据模型从 v0.8.5 升级到 v1.5：

- **数据**：新增 22 张活跃表 + 3 张预留 + 1 张事件流水
- **API**：新增 6 个核心新 API + 22 个原有/改造 = **28 个 API**
- **界面**：5 个 Tab + 4 个模态框
- **执行**：分 6 个 Phase + 1 个可选 Phase，**23-27 工作日**

---

## 二、Phase 拆分（7 个 Phase，6 个必做 + 1 个可选）

### Phase 1：合约行情领域（3-4 天）

**目标**：把"品种 → 合约"维度展开

**数据层**：
- 创建 `futures_contracts` 表 + `init_db` 自动迁移
- 迁移 `futures_daily`：新增 `atr` 字段（合并 `futures_atr`），retention 14 天 → 3 年（1095 天），初始化全量回填近 3 年日线，索引 `(symbol, date)`
- 迁移 `futures_min`：新增 `date` 字段（从 `datetime` 派生），retention 7 天 → 半年（180 天），初始化全量回填近半年分时
- `futures_atr` 表数据迁移 + 删除
- 主力合约识别逻辑

**API 层**：`GET /contracts/{symbol}`、`GET /quotes/{contract_code}`

**前端**：品种网格加"📋 N 合约"角标 + 合约抽屉

**验收**：
- 点 AG 卡片能弹出 4 个合约的报价列表
- 日线 retention 3 年、分时 retention 半年
- 主力合约角标高亮

**风险**：retention 拉长后 SQLite 性能 → 索引必建
**回退**：删除新表 + 还原 `futures_atr`，回到 v0.8.5

---

### Phase 2：策略领域（3 天）

**目标**：策略可切换 + 多版本隔离 + 参数迭代可追溯

**代码组织**（v1.3 核心）：
- 建立 `strategies/turtle/V1/` 目录
- 现有 `strategies/turtle/position.py` 移到 `strategies/turtle/V1/`
- 实现 `strategies/loader.py`（动态加载器）
- 实现 `strategies/base.py`（BaseStrategy 抽象基类）

**数据层**：6 张表
- `strategies` + `version` 字段 + 种子数据
- `strategy_param_history`（参数迭代）
- `strategy_signal_states`（信号状态）
- `strategy_signals` 升级
- `strategy_event_log`（事件流水）
- `turtle_trade_process`（v1.5 海龟过程数据）

**API 层**：7 个 API
- `GET /strategies` / `POST /strategies` / `PUT /strategies/{id}` / `DELETE /strategies/{id}`
- `GET /strategies/{id}/signals` / `GET /strategies/{id}/states`
- `GET /strategies/{id}/trade-process`（v1.5 新增）

**前端**：顶部策略下拉 + 策略历史页

**验收**：
- 切换 turtle_v1 / turtle_v2 都能加载对应算法
- 修改 V1 代码不影响 V2
- 策略历史能查看参数迭代

**风险**：V1/V2 完全隔离导致代码重复 → 允许 `utils/` 共享目录

---

### Phase 3：交易 / 账户领域（10-12 天，v1.4 + v1.5 强化）

**目标**：模拟交易全程落盘 + 多账户 + 价格线 + 海龟过程数据

**数据层**：10 张活跃表 + 3 张预留
- 核心：`sim_account` / `trade_sessions` / `sim_orders` / `sim_trades` / `sim_positions` / `position_units`
- v1.4 新增：`turtle_session_data` / `dual_ma_session_data` / `breakout_session_data` / `session_event_log`
- 预留：`live_orders` / `live_trades` / `live_positions`（不实施，仅建表）
- v1.5 调整：`position_units` 海龟字段迁移 + `turtle_trade_process`（已在 Phase 2）

**服务层**：
- 撮合引擎 `api/services/sim_engine.py`
- Session 生命周期管理器 `api/services/session_lifecycle.py`
- 事件流写入服务 `api/services/event_logger.py`（v1.4 新增）
- 价格线计算服务 `api/services/line_calculator.py`

**API 层**：12 个 API（含 v1.4 新增 6 个）
- 价格线：`GET /session/{id}/lines`（v1.3 核心）
- 用户调价：`PUT /session/{id}/line/{line_type}`（v1.3 核心）
- v1.4 新增：信号建仓 / 加仓 / 全平 / 调价 / Session 列表
- v1.5 新增：`GET /session/{id}/trade-process`
- `/sim/*` 加 `account_id` 参数

**v1.5 海龟过程数据子任务**（4 个）：
- **3.15** ★ `turtle_trade_process` 表 + `init_db`
- **3.16** ★ 策略执行引擎 `on_bar` 流程改造（**退仓优先顺序：止损 > 加仓**）
- **3.17** ★ check 类事件按 **C 方案**实现（触发存前后 5 根 K 线）
- **3.18** ★ `GET /session/{id}/trade-process` API

**前端**：
- 4 个模态框：手动建仓 / 加减仓 / 全部平仓 / 用户调价
- 顶部操作组：账户切换器 + 策略下拉
- 详情"模拟"Tab + 模拟下单按钮
- K 线图集成价格线（红/蓝/紫三色）

**验收**：
- 多账户并存（sim_default / sim_user1 / sim_user2）
- 手动建仓 → 撮合 → 持仓更新 → 事件流 → 单元详情
- 加仓到 4 Unit（4 Unit 加仓模型 + 跳空事件）
- 调价生效（override + is_override 标记）
- 全部平仓 → session 从 open 列表消失
- 并发 423 处理（应用层互斥锁 `session_lock`）
- K 线图显示价格线 + 用户拖动水平线实时生效

**风险**：
- **数据迁移风险**：新表与旧表共存 → 旧表不动
- **API 兼容风险**：旧 `/turtle/signals/*` 保留重定向
- **撮合逻辑风险**：与实盘 CTP 有差异 → 撮合引擎封装在 `sim_engine.py`
- **价格线计算开销**：每次 K 线更新重算所有 session → 缓存（trade_sessions 变化时失效）
- **海龟过程数据量**：单 session 30-50 条 × 1000 session/年 ≈ 30-50k 条/年，可接受

---

### Phase 4：回测持久化（3 天）

**目标**：回测结果落盘 + 历史可查

**数据层**：1 张表
- `backtest_runs`

**API 层**：3 个 API
- `/backtest/runs` / `/backtest/{run_id}/trades` / `/backtest/{run_id}/overview`

**引擎改造**：`BacktestEngine` 每个成交写 `sim_trades`（带 `backtest_run_id` / `session_id` / `account_id`）

**前端**：详情"回测"Tab 改为"历史回测列表"

**验收**：
- 跑一次回测，重启后历史回测列表能列出
- 点击详情能看 K 线 + 买卖点标记 + 成交列表

---

### Phase 5：账户中心页（2 天）

**目标**：账户总览 + URL 参数全局贯通

**API 层**：`/account/overview`（聚合 sim_account + sim_positions + position_units + trade_sessions）

**前端**：`/account` 页面（总览 / 持仓列表 / Unit 明细 / 当前 Session / 价格线 / 成交记录）

**URL 参数**：`?account=&strategy=` 全局贯通

**验收**：
- 账户中心能看到完整的 4 Unit 明细
- 当前 Session 锁定值 + 价格线
- 模拟 Tab 顶部账户信息卡正确显示余额 / 可用 / 保证金 / 盈亏

---

### Phase 6：单元 + 集成测试（2-3 天）

**目标**：自动化测试覆盖核心流程

**单测**（覆盖率 > 80%）：
- 撮合引擎单测
- 价格线计算单测（含 override 优先级）
- trade_session 生命周期单测
- 多账户隔离单测
- 策略版本切换单测（V1 vs V2）

**集成测试**：
- 端到端：信号 → 模拟下单 → 成交 → 持仓 → 价格线更新
- 与 0016 通达信字段对齐测试

**性能测试**：
- locust 压测 API
- 16 张表下单次回测数千行 trades 性能

**验收**：
- 自动化测试全部通过
- 性能指标达标

---

### Phase 7（可选）：CTP 接入（后续）

**v1.5 状态**：未实施（不排期）

**预留工作**：
- CTP 接口对接
- `live_orders` / `live_trades` / `live_positions` 启用
- 真实 Tab 启用

---

## 三、时间线

| Phase | 名称 | 工作日 | 累计 | 依赖 |
|-------|------|--------|------|------|
| Phase 1 | 合约行情领域 | 3-4 | 3-4 | — |
| Phase 2 | 策略领域 | 3 | 6-7 | Phase 1 |
| Phase 3 | 交易 / 账户领域 | 10-12 | 16-19 | Phase 2 |
| Phase 4 | 回测持久化 | 3 | 19-22 | Phase 3 |
| Phase 5 | 账户中心页 | 2 | 21-24 | Phase 3 |
| Phase 6 | 单元 + 集成测试 | 2-3 | 23-27 | Phase 4 + 5 |
| Phase 7 | CTP 接入（可选）| — | — | 全部 |

**总计**：**23-27 工作日**（约 5-6 周），分 6 个必做交付里程碑

**关键路径**：Phase 1 → Phase 2 → Phase 3 → Phase 4/5（并行）→ Phase 6

---

## 四、风险与缓解（9 项）

| # | 风险 | 缓解措施 |
|---|------|---------|
| 1 | 数据迁移风险 | 新表与旧表共存，DB 备份 |
| 2 | API 兼容风险 | 旧 `/turtle/signals/*` 保留重定向 |
| 3 | 性能风险（16 张表 + 数千行 trades）| SQLite 索引 + 必要时迁移 PostgreSQL |
| 4 | 撮合逻辑风险（与 CTP 差异）| 撮合封装在 `sim_engine.py`，单测覆盖 |
| 5 | 领域边界风险（策略误写交易事实）| 交易领域写操作封装在 sim_engine.py / 撮合引擎内 |
| 6 | 价格线计算开销 | 缓存（仅 trade_sessions 变化时失效）|
| 7 | 策略代码组织（V1/V2 重复）| 允许 `utils/` 共享目录 |
| 8 | 海龟过程数据量 | 单 session 30-50 条 × 1000 session/年 ≈ 30-50k 条/年，可接受 |
| 9 | check 类事件 C 方案 | 触发前 5 根 + 触发 + 后 5 根 = 10 条，调试够用 |

---

## 五、回退方案（4 项）

- **数据库**：所有新表独立，旧表不动 → 任何阶段可丢弃新表回到 v0.8.5
- **API 兼容**：旧前端继续工作
- **DB 备份**：`futures_akshare.db` 每次 Phase 实施前 `cp` 备份
- **策略代码**：保留 v0.8.5 路径 `strategies/turtle/`，新代码放 `strategies/turtle/V1/`

---

## 六、待确认项（18 项 v1.4 + v1.5 新增）

| # | 问题 | 当前默认 | 备选 |
|---|------|---------|------|
| 1 | 策略切换是否影响历史数据？ | 不影响（只影响新数据查询）| 切换时清空前端状态 |
| 2 | 默认策略资金 / 默认品种范围 | 全品种 + 100 万 | 用户可配置 |
| 3 | 模拟撮合：市价单 / 限价单 | 全部市价单 | 按策略可配 |
| 4 | 模拟手续费率 | instruments.yaml 费率（待补）| 固定 2 元/手 |
| 5 | 是否废弃 `turtle_signals` 表 | 保留 + 视图兼容 | 迁移后删除 |
| 6 | 真实持仓表是否在本期实施 | 不实施，仅建表预留 | 直接接 CTP |
| 7 | 是否需要"多账户"概念 | 是，sim_default + sim_user1 + sim_user2 | 简化为单一 default |
| 8 | 持仓 Unit 超过 4 个 | 拒绝（对齐原版海龟）| 允许但报警 |
| 9 | 策略参数历史 | 全部保留（无上限）| 仅最近 N 版 |
| 10 | 信号主表刷新频率 | 每次新信号 UPSERT | 每 30s 批量刷新 |
| 11 | trade_session.status='closed' 保留多久 | 永久保留（审计）| 保留 N 天后归档 |
| 12 | 回测是否产生 trade_sessions | 是，用 account_type 区分 | 用 backtest_run_id 字段 |
| 13 | 用户调价是否仅 in_position | 是 | 全程可改 |
| 14 | 用户调价后子线是否级联重算 | 是 | 调哪个改哪个 |
| 15 | 策略 V1 / V2 是否完全隔离 | 是 | 允许部分共享（utils/）|
| **16** | **`turtle_trade_process` 数据量预估与归档策略** | **半年（180 天）后归档** | 1 年后归档 / 不归档 |
| **17** | **check 类事件 C 方案触发存 5 根是否够？** | **5 根够调试用** | 10 根上下文更全 |
| **18** | **`dual_ma_trade_process` 何时启动设计？** | **v1.5 暂不做，等加 dual_ma 时** | v1.6 一起做 |

**v1.5 新增 3 项（已采纳默认）**：
- 16：半年后归档
- 17：5 根够用
- 18：dual_ma 暂不做

---

## 七、22 张活跃表清单

| # | 表名 | 阶段 | 备注 |
|---|------|------|------|
| 1 | futures_contracts | Phase 1 | 新增 |
| 2 | futures_quotes | Phase 1 | 新增 |
| 3 | futures_daily | Phase 1 | 迁移 + 新增 atr |
| 4 | futures_min | Phase 1 | 迁移 + 新增 date |
| 5 | strategies | Phase 2 | 新增 |
| 6 | strategy_param_history | Phase 2 | 新增 |
| 7 | strategy_signal_states | Phase 2 | 新增 |
| 8 | strategy_signals | Phase 2 | 升级 |
| 9 | strategy_event_log | Phase 2 | 新增 |
| 10 | turtle_session_data | Phase 3 | v1.4 新增 |
| 11 | dual_ma_session_data | Phase 3 | v1.4 占位 |
| 12 | breakout_session_data | Phase 3 | v1.4 占位 |
| 13 | sim_account | Phase 3 | 新增 |
| 14 | trade_sessions | Phase 3 | 新增 |
| 15 | sim_orders | Phase 3 | 新增 |
| 16 | sim_trades | Phase 3 | 新增 |
| 17 | sim_positions | Phase 3 | 新增 |
| 18 | position_units | Phase 3 | 新增 + 海龟字段迁移 |
| 19 | session_event_log | Phase 3 | v1.4 新增 |
| 20 | turtle_trade_process | Phase 2/3 | v1.5 新增 |
| 21 | backtest_runs | Phase 4 | 新增 |
| 22 | backtest_results | Phase 4 | 新增 |

**预留 3 张**（不实施）：live_orders / live_trades / live_positions

---

## 八、资源分配

| 角色 | 职责 | 投入 |
|------|------|------|
| Alex | 需求决策 + 关键点拍板 + 验收 | 全程按需 |
| Blex（主 agent）| 派子任务 + 协调 + 文档维护 | 全程 |
| Blex（子 agent）| 实施编码 + 单测 + 集成 | 按 Phase 派 |

**工具**：
- 数据库：SQLite（主）/ PostgreSQL（备份）
- 后端：FastAPI + uvicorn
- 前端：原生 HTML + JS（v1.3 简化）+ 后续可换 Vue
- 测试：pytest + locust

**环境**：
- 开发：http://localhost:8000
- 测试：独立 test DB
- 生产：暂不部署（v0.8.5 当前已用）

---

## 九、验收标准（每 Phase 强制）

| Phase | 验收点 |
|-------|--------|
| Phase 1 | 4 张表 + 索引 + 5 个 API + 合约抽屉；retention 3 年/半年 |
| Phase 2 | 6 张表 + 7 个 API + 策略切换 + 策略历史 |
| Phase 3 | 10 张表 + 12 个 API + 4 模态框 + 调价 + 4 Unit + 跳空 |
| Phase 4 | backtest_runs + 3 API + 历史回测列表 |
| Phase 5 | /account 页面 + URL 参数 + 4 Unit 明细 |
| Phase 6 | 单测 > 80% + 集成测试 4 流程 + 端到端 + 性能达标 |

**每 Phase 完成后必须**：
- 提交代码 + 跑通验收
- 0003 变更日志新增小版本
- 0003 风险与回退表更新
- 飞书同步（如适用）

---

## 十、Phase 进入条件

- ✅ **Phase 1** 启动：v0.10.1 已发布（设计已审核）
- ✅ **Phase 2** 启动：Phase 1 验收通过
- ✅ **Phase 3** 启动：Phase 2 验收通过
- ✅ **Phase 4** 启动：Phase 3 验收通过
- ✅ **Phase 5** 启动：Phase 3 验收通过（与 Phase 4 并行）
- ✅ **Phase 6** 启动：Phase 4 + Phase 5 全部通过
- ⏸ **Phase 7**：v2.0 启动后再说

---

## 十一、计划状态

| 项 | 状态 |
|----|------|
| 设计依据 | ✅ v1.5 已发布（111KB / 14 章）|
| 4 文档填实 | ✅ 01/02/03/04 已完成 |
| 05-project-structure | ✅ 已完成 |
| Phase 拆分 | ✅ 7 个 Phase 明确 |
| 时间线 | ✅ 23-27 工作日 / 5-6 周 |
| 风险与回退 | ✅ 9 风险 + 4 回退 |
| 待确认项 | ⏳ 18 项（18 项已采纳默认）|
| 资源分配 | ✅ 已规划 |
| 验收标准 | ✅ 每 Phase 明确 |
| 用户审核 | ⏳ **本文档待用户拍板** |

---

> **下一步**：等用户审核 plan.md → 拍板"可以执行" → 派 Phase 1 子任务开始实施

---

*本文档是 _requirements/data-model-redesign/02-plan/ 下的执行计划，作为设计 → 执行的桥梁。*
