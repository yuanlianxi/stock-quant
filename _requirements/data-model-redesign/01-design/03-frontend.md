# 前端设计：页面 / 组件 / 状态 / 操作流 / 交互协议

> 文档版本：v1.5
> 创建日期：2026-06-01
> 修订日期：2026-06-02
> 负责人：Alex + Blex
> 状态：✅ 完成（v1.5 最新版）

> **本文档是 `0006_数据模型与界面重构设计.md` 的"前端视角"详细拆分**。总体设计看 `01-overall.md`，后端看 `02-backend.md`，整合看 `04-integration.md`。

---

## 一、页面整体布局

### 1.1 顶部栏（v1.3 起 + v1.4 强化）

```
┌────────────────────────────────────────────────────────────────────┐
│  [Logo]  数据模型与界面重构 - 演示系统            [👤 用户] [⚙️ 设置]  │
├────────────────────────────────────────────────────────────────────┤
│  策略: [海龟 V1 ▾]  账户: [sim_001 ▾]  操作: [➕建仓][➕加仓][➖减仓][🔒全平]  │
├────────────────────────────────────────────────────────────────────┤
│                       5 个 Tab                                    │
│  [信号] [模拟] [真实] [回测] [Session]                              │
└────────────────────────────────────────────────────────────────────┘
```

**元素说明**：

| 元素 | 控件 | 行为 | 数据源 |
|------|------|------|--------|
| 策略切换器 | `<select>` | 切换后刷新所有 Tab 数据 | `GET /strategies?account_id=...` |
| 账户切换器 | `<select>` | 切换后刷新所有 Tab 数据 | `GET /accounts` |
| 操作组（4 按钮）| `<button>` ×4 | 点击弹出对应模态框 | 触发模态框 |
| 5 个 Tab | `<tab>` | 切换 Tab 内容 | 各自数据源 |

### 1.2 5 个 Tab 详情

#### Tab 1：信号

**布局**（v1.3 起为"详情·信号"）：
```
┌─────────────────────────────────────────────────────────────┐
│  品种网格（左 30%）    │    信号详情面板（右 70%）           │
│  ─────────────         │    ────────────                   │
│  AG  [ag2607 ⭐]       │    AG  当前信号状态：              │
│      ag2609            │      状态: 🟢 IN_LONG              │
│      ag2612            │      入场价: 7850.0                │
│      ag2703            │      当前价: 7860.0                │
│  CU  [cu2607 ⭐]       │      N 值:    120.5                │
│      cu2609            │      锁定 ATR: 120.5               │
│  ...                   │    [K 线图 + 价格线]                │
│                        │    ────────────                   │
│                        │    历史信号（最近 30 天）：          │
│                        │    2026-06-01  14:23  ENTRY_LONG   │
│                        │    2026-05-28  10:15  ENTRY_LONG   │
└─────────────────────────────────────────────────────────────┘
```

**数据源**：
- 品种网格：`GET /contracts/{symbol}` + 高亮主力
- 当前信号状态：`GET /strategy/signal/state/{sym}?strategy_id=...`（**实时 JOIN 算，不持久化**）
- 历史信号：`GET /strategy/signals/{sym}?strategy_id=...`
- K 线：`GET /futures/daily?contract_code=...&start_date=...&end_date=...` + `GET /futures/min?contract_code=...&date=...`
- 价格线：`GET /session/{id}/lines?account_id=...`（如果有 open session）

#### Tab 2：模拟

**布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  账户信息卡（顶部）                                           │
│  余额: 1,000,000   可用: 850,000   保证金: 150,000            │
│  今日盈亏: +5,230  (+0.52%)                                  │
├─────────────────────────────────────────────────────────────┤
│  持仓列表（中部）                                              │
│  品种    方向   数量   开仓均价   当前价   浮动盈亏   持仓时长  │
│  AG      多     2      7850      7860     +200      2h 15m   │
│  CU      空     1      72500     72450    +50       30m      │
├─────────────────────────────────────────────────────────────┤
│  委托 + 成交（底部，可切换）                                   │
│  [委托列表] [成交列表]                                         │
└─────────────────────────────────────────────────────────────┘
```

**数据源**：
- 账户信息：`GET /sim/account/{account_id}` + `GET /account/overview?account_id=...&strategy_id=...`
- 持仓列表：`GET /sim/positions?account_id=...`（**每 5 秒轮询**）
- 委托列表：`GET /sim/orders?account_id=...`
- 成交列表：`GET /sim/trades?account_id=...`

#### Tab 3：真实

**布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ CTP 接入未启用（v1.5 预留）                               │
│  ────────────                                                │
│  live_orders / live_trades / live_positions 表为空           │
│  [🔌 启用 CTP]（Phase 7 可选）                                │
└─────────────────────────────────────────────────────────────┘
```

**v1.5 状态**：占位，Phase 7 可选启用 CTP。

#### Tab 4：回测

**布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  回测列表（左侧 30%）                                          │
│  ────────────                                                │
│  #001  turtle_v1  AG  2025-01~2025-12  收益 +15.2%   [详情]   │
│  #002  turtle_v2  AG  2025-01~2025-12  收益 +18.5%   [详情]   │
│  ...                                                          │
├─────────────────────────────────────────────────────────────┤
│  回测详情（右侧 70%，点击列表项加载）                           │
│  指标: 收益 / 最大回撤 / 夏普 / 胜率 / 盈亏比                  │
│  K 线图 + 买卖点标记                                          │
│  成交列表                                                     │
└─────────────────────────────────────────────────────────────┘
```

**数据源**：
- 回测列表：`GET /backtest/runs`
- 回测详情：`GET /backtest/{run_id}`
- 回测成交：`GET /backtest/{run_id}/trades`

#### Tab 5：Session（v1.4 新增 ★）

**布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  open session 列表（左侧 30%）                                │
│  ────────────                                                │
│  AG  多  2 Unit  +200  2h  [详情]                            │
│  CU  空  1 Unit  +50   30m [详情]                            │
├─────────────────────────────────────────────────────────────┤
│  session 详情（右侧 70%，点击列表项加载）                      │
│  ────────────                                                │
│  会话信息:                                                    │
│    session_id: abc-123                                       │
│    建仓时间: 2026-06-02 10:30                                 │
│    方向: 多                                                   │
│    状态: open                                                 │
│    当前 Unit 数: 2                                            │
│    锁定入场价: 7850.0                                         │
│    锁定 ATR: 120.5                                            │
│                                                            │
│  Unit 详情（4 个 Unit 卡片）:                                │
│  ┌──────┬──────┬──────┬──────┐                              │
│  │ #1   │ #2   │ #3   │ #4   │                              │
│  │ 开:7850 │ 开:7860 │ -    │ -    │                          │
│  │ 停:7730 │ 停:7740 │ -    │ -    │                          │
│  │ 状态:open │ 状态:open │ -    │ -    │                      │
│  │ +200  │ +100  │ -    │ -    │                            │
│  └──────┴──────┴──────┴──────┘                              │
│                                                            │
│  [K 线图 + 价格线]                                            │
│                                                            │
│  事件流（折叠面板）:                                          │
│    10:30  ENTRY            price=7850  source=manual        │
│    10:45  ADD_UNIT_2       price=7860  source=manual        │
│                                                            │
│  海龟过程流水（折叠面板，v1.5）:                                │
│    10:30  entry_signal     price=7850  kline=10:30          │
│    10:30  entry_filled     price=7850  kline=10:30          │
│    10:45  add_signal       price=7860  kline=10:45          │
│    10:45  add_filled       price=7860  kline=10:45          │
│    ...                                                       │
└─────────────────────────────────────────────────────────────┘
```

**数据源**：
- open session 列表：`GET /sessions?status=open`（**每 5 秒轮询**）
- session 详情：`GET /sim/sessions?account_id=...&strategy_id=...`
- Unit 详情：`GET /position/units?session_id=...`（前端从 sim_positions JOIN 算）
- 价格线：`GET /session/{id}/lines?account_id=...`
- 事件流：`GET /session/{id}/events`
- 海龟过程流水：`GET /session/{id}/trade-process`（**v1.5**）

---

## 二、4 个模态框（v1.4 新增）

### 2.1 手动建仓模态框

**触发**：点击顶部"➕建仓"按钮

**布局**：
```
┌──────────────────────────────────────┐
│  手动建仓                        [×] │
├──────────────────────────────────────┤
│  账户:    [sim_001 ▾]                │
│  策略:    [turtle_v1 ▾]              │
│  品种:    [AG ▾]                     │
│  合约:    [ag2607 ▾]                 │
│  方向:    ( ) 多  (•) 空             │
│  数量:    [1]                         │
│  委托类型: (•) 市价  ( ) 限价          │
│  限价:    [______] (限价时填)          │
│  备注:    [_________________]         │
├──────────────────────────────────────┤
│           [取消]  [确认建仓]          │
└──────────────────────────────────────┘
```

**提交 API**：`POST /session`

**响应处理**：
- 200：关闭模态框，Toast 成功，刷新 Session Tab
- 423：Toast 提示"已有建仓进行中，请稍后"
- 422 资金不足：Toast 提示

### 2.2 手动加仓/减仓模态框

**触发**：点击顶部"➕加仓"或"➖减仓"按钮（先选中 session）

**布局**：
```
┌──────────────────────────────────────┐
│  手动加仓                        [×] │
├──────────────────────────────────────┤
│  Session: AG 多 2 Unit (2h)          │
│  当前 Unit 数: 2                      │
│  操作:    (•) 加仓  ( ) 减仓          │
│  数量:    [1]                         │
│  委托类型: (•) 市价  ( ) 限价          │
│  限价:    [______]                    │
│  备注:    [_________________]         │
├──────────────────────────────────────┤
│           [取消]  [确认]              │
└──────────────────────────────────────┘
```

**提交 API**：`POST /session/{id}/orders`

**响应处理**：同 2.1

### 2.3 全部平仓模态框

**触发**：点击顶部"🔒全平"按钮（先选中 session）

**布局**：
```
┌──────────────────────────────────────┐
│  全部平仓                        [×] │
├──────────────────────────────────────┤
│  ⚠️ 确认平仓以下 Session？            │
│  ────────────                        │
│  Session: AG 多 2 Unit               │
│  浮动盈亏: +200                       │
│  ────────────                        │
│  平仓后无法撤销，请确认！              │
├──────────────────────────────────────┤
│       [取消]  [⚠️ 确认全平]          │
└──────────────────────────────────────┘
```

**提交 API**：`POST /session/{id}/close`

**响应处理**：
- 200：关闭模态框，Toast 成功，刷新 Session Tab（session 从 open 列表消失）
- 409：Toast 提示"session 已关闭"

### 2.4 用户调价模态框（v1.3 核心）

**触发**：在 K 线图上**拖动**价格线（水平虚线）

**布局**（嵌入式，非弹窗）：
```
K 线图上：
   7900 ┤
        │  ←─── 拖动 stop_price 这条线
   7850 ┤━━━━━━━━━ entry_basis_price（蓝色）
        │  ←─── 拖动 add_1_price 这条线
   7730 ┤━━━━━━━━━ stop_price（红色）
        │
   7700 ┤
        └──────────────────
```

**交互流程**：
1. 用户鼠标按下价格线（光标变 ⬍）
2. 拖动到目标价格
3. 鼠标松开时，自动调价 API
4. **确认弹窗**（v1.3 设计）：
```
┌──────────────────────────────────────┐
│  确认调价                        [×] │
├──────────────────────────────────────┤
│  原价: 7730.0  →  新价: 7700.0       │
│  价格线: 止损线                       │
│  生效范围: 当前 Session                │
├──────────────────────────────────────┤
│        [取消]  [确认调价]             │
└──────────────────────────────────────┘
```

**提交 API**：`PUT /session/{id}/line/{line_type}?account_id=...`

**响应处理**：
- 200：更新前端价格线显示，标记 `is_override: true`
- 422 范围越界：Toast 提示

---

## 三、组件树

### 3.1 全局组件

```
<App>
├── <TopBar>                            // 顶部栏
│   ├── <StrategySelector>              // 策略切换器
│   ├── <AccountSelector>               // 账户切换器
│   └── <ActionGroup>                   // 4 个操作按钮
│       ├── <ManualEntryButton>         // ➕建仓
│       ├── <ManualAddButton>           // ➕加仓
│       ├── <ManualReduceButton>        // ➖减仓
│       └── <CloseAllButton>            // 🔒全平
│
└── <TabContainer>
    ├── <SignalTab>                     // Tab 1
    │   ├── <ContractGrid>              // 品种网格
    │   │   └── <ContractItem>          // 品种项（高亮主力）
    │   ├── <SignalDetailPanel>         // 信号详情面板
    │   │   ├── <SignalStateCard>       // 当前信号状态
    │   │   ├── <KLineChart>            // K 线图
    │   │   │   └── <PriceLineLayer>    // 价格线层
    │   │   │       └── <DraggableLine> // 可拖动价格线
    │   │   └── <SignalHistoryList>     // 历史信号
    │   └── ...
    │
    ├── <SimTab>                        // Tab 2
    │   ├── <AccountInfoCard>           // 账户信息卡
    │   ├── <PositionList>              // 持仓列表
    │   │   └── <PositionItem>          // 持仓项
    │   ├── <OrderList>                 // 委托列表
    │   └── <TradeList>                 // 成交列表
    │
    ├── <LiveTab>                       // Tab 3（占位）
    │   └── <ComingSoonNotice>          // CTP 未启用提示
    │
    ├── <BacktestTab>                   // Tab 4
    │   ├── <BacktestRunList>           // 回测列表
    │   └── <BacktestDetailPanel>       // 回测详情
    │       ├── <MetricsCard>           // 指标卡
    │       ├── <KLineChart>            // K 线图
    │       └── <BacktestTradeList>     // 成交列表
    │
    └── <SessionTab>                    // Tab 5（v1.4 新增）
        ├── <SessionList>               // open session 列表
        │   └── <SessionItem>           // session 项
        ├── <SessionDetailPanel>        // session 详情
        │   ├── <SessionInfoCard>       // 会话信息卡
        │   ├── <UnitGrid>              // 4 个 Unit 卡片
        │   │   └── <UnitCard>          // Unit 卡片
        │   ├── <KLineChart>            // K 线图
        │   │   └── <PriceLineLayer>    // 价格线层
        │   ├── <SessionEventLog>       // 事件流（折叠）
        │   └── <TurtleProcessLog>      // 海龟过程流水（v1.5，折叠）
        └── ...
```

### 3.2 核心组件详细说明

#### `<KLineChart>`（K 线图组件）

**职责**：
- 渲染日 K 线 / 分 K 线
- 叠加价格线（entry/stop/add_1/.../add_3）
- 支持价格线拖动调价
- 支持买卖点标记（回测 Tab）

**Props**：
```typescript
interface KLineChartProps {
  contractCode: string;
  klineData: KLineData[];
  priceLines: PriceLine[];
  onPriceLineDrag: (lineType: string, newPrice: number) => void;
  markers?: TradeMarker[];        // 回测用
  mode: 'signal' | 'session' | 'backtest';
}
```

**价格线颜色约定**：
- entry_basis_price：蓝色 `#2196F3`
- stop_price：红色 `#F44336`
- add_1 / add_2 / add_3：绿色（深浅区分）`#4CAF50` / `#66BB6A` / `#81C784`
- exit_20：橙色 `#FF9800`
- 用户 override 后：实线 + 旁边 ⓘ 图标

#### `<PositionItem>`（持仓项）

**显示字段**：品种 / 方向 / 数量 / 开仓均价 / 当前价 / 浮动盈亏 / 持仓时长

**交互**：
- 点击 → 切换到 Session Tab + 选中对应 session
- 右键 → 弹出加仓/减仓/全平菜单

#### `<UnitCard>`（Unit 卡片）

**显示字段**：
- Unit 编号（#1 / #2 / #3 / #4）
- 开仓价
- 止损价
- 状态（open / closed / stopped）
- 浮动盈亏

**交互**：
- 点击 → 在 K 线图上高亮该 Unit 的开仓点

---

## 四、状态管理

### 4.1 全局状态（Pinia store / Redux）

```typescript
// 全局账户 + 策略
interface GlobalState {
  currentAccountId: string;           // 当前选中账户
  currentStrategyId: string;          // 当前选中策略
  accounts: Account[];                // 所有账户
  strategies: Strategy[];             // 当前账户的所有策略
  openSessions: Session[];            // open sessions（每 5 秒轮询）
}

// UI 状态
interface UIState {
  activeTab: 'signal' | 'sim' | 'live' | 'backtest' | 'session';
  selectedSymbol: string;             // 当前选中品种
  selectedContractCode: string;       // 当前选中合约
  selectedSessionId: string | null;   // 当前选中 session
}
```

### 4.2 本地状态（组件内 useState）

- 模态框显示 / 隐藏
- 表格分页 / 排序 / 筛选
- K 线图缩放 / 拖动状态
- 表单输入值

### 4.3 数据缓存策略

| 数据 | 缓存位置 | 失效时机 |
|------|---------|---------|
| 账户列表 | 全局 store | 创建/删除账户时失效 |
| 策略列表 | 全局 store | 注册新策略时失效 |
| 品种合约 | 全局 store | 每日同步后失效 |
| 行情 | 组件内 state | 3 秒轮询覆盖 |
| K 线 | 组件内 state | 用户切换品种/合约时失效 |
| 信号状态 | 组件内 state | 5 秒轮询覆盖 |
| 持仓 | 全局 store | 5 秒轮询覆盖 |
| session 详情 | 组件内 state | 用户切换 session 时失效 |
| 价格线 | 组件内 state | 用户调价时失效 |
| 事件流 | 组件内 state | 10 秒轮询覆盖 |

### 4.4 错误处理

**全局错误拦截**：
- 401：跳转登录页
- 403 / 404：Toast 提示
- **423 session_lock_held**：Toast 提示 + 自动重试 1 次（间隔 500ms）
- 429 rate_limit：自动重试 + 指数退避
- 5xx：Toast 提示 + 触发上报

**用户操作回滚**：
- 提交按钮 loading 态
- 失败时按钮恢复可点
- 表单不清空（让用户修正重提）

---

## 五、操作流（4 个核心流程）

### 5.1 手动建仓流程

```
用户点击"➕建仓"
    ↓
打开<ManualEntryModal>
    ↓
用户填写表单 + 点击"确认建仓"
    ↓
[前端] 验证必填字段
    ↓ 失败 → 字段红框 + 错误提示
[前端] 调用 POST /session
    ↓ 成功（200）→ 关闭模态框 + Toast 成功 + 刷新 Session Tab
    ↓ 失败（423）→ Toast 提示 + 500ms 后自动重试 1 次
    ↓ 失败（422 资金不足）→ Toast 提示
    ↓ 失败（其他）→ Toast 提示
[后端] 详见 02-backend.md §3.2
```

### 5.2 手动加仓/减仓流程

```
用户在 Session Tab 选中 session
    ↓
点击顶部"➕加仓"或"➖减仓"
    ↓
打开<ManualAddReduceModal>（预填 session 信息）
    ↓
用户填写表单 + 点击"确认"
    ↓
[前端] 验证 + 调用 POST /session/{id}/orders
    ↓ 成功 → 关闭模态框 + Toast 成功 + 刷新当前 session 详情
    ↓ 失败 → Toast 提示
```

### 5.3 全部平仓流程

```
用户在 Session Tab 选中 session
    ↓
点击顶部"🔒全平"
    ↓
打开<CloseAllModal>（高危操作：橙色确认按钮 + ⚠️ 图标）
    ↓
用户点击"⚠️ 确认全平"
    ↓
[前端] 调用 POST /session/{id}/close
    ↓ 成功 → 关闭模态框 + Toast 成功 + session 从 open 列表消失
    ↓ 失败（409）→ Toast 提示
```

### 5.4 用户调价流程

```
用户在 K 线图上拖动价格线
    ↓
[前端] 实时显示新价格（拖动过程中）
    ↓
鼠标松开
    ↓
打开<ConfirmPriceChangeModal>（显示原价/新价/价格线类型）
    ↓
用户点击"确认调价"
    ↓
[前端] 调用 PUT /session/{id}/line/{line_type}?account_id=...
    ↓ 成功 → 更新价格线显示（is_override=true + ⓘ 图标）
    ↓ 失败 → 价格线回弹到原价 + Toast 提示
```

### 5.5 查看海龟过程流水流程（v1.5）

```
用户在 Session Tab 选中 session（且策略是海龟）
    ↓
点击"海龟过程流水"折叠面板
    ↓
[前端] 调用 GET /session/{id}/trade-process
    ↓ 成功 → 渲染时间线列表（10 种 event_type 颜色区分）
    ↓ 失败 → Toast 提示
[用户] 可点击某条事件 → 在 K 线图上跳转高亮
```

---

## 六、前端视角的交互（调用哪些 API 完成业务）

### 6.1 启动流程

```
1. GET /accounts                         → 填充账户切换器
2. GET /strategies?account_id=...        → 填充策略切换器
3. GET /sessions?status=open             → 填充 Session Tab 列表
4. GET /contracts/AG                     → 填充品种网格（默认品种）
5. 启动 5 秒轮询:
   - GET /strategy/signal/state/AG?strategy_id=...
   - GET /sim/positions?account_id=...
6. 启动 10 秒轮询:
   - GET /session/{id}/events
   - GET /session/{id}/trade-process
```

### 6.2 切换品种

```
1. 用户点击品种网格项
2. 缓存失效（K 线 / 信号状态 / 价格线）
3. GET /quotes/{contract_code}          → 实时行情（3 秒轮询启动）
4. GET /futures/daily?contract_code=... → 日 K 线
5. GET /futures/min?contract_code=...   → 分 K 线
6. GET /strategy/signal/state/{sym}?strategy_id=...   → 当前信号
7. GET /strategy/signals/{sym}?strategy_id=...        → 历史信号
```

### 6.3 切换 Session

```
1. 用户点击 session 列表项
2. 缓存失效（session 详情 / Unit / 价格线 / 事件流）
3. GET /sim/sessions?account_id=...&strategy_id=...  → session 详情
4. GET /session/{id}/lines?account_id=...            → 价格线
5. GET /session/{id}/events                         → 事件流
6. GET /session/{id}/trade-process                  → 海龟过程（如果是海龟）
7. 启动 10 秒轮询:
   - GET /session/{id}/events
   - GET /session/{id}/trade-process
```

### 6.4 提交操作（建仓/加仓/减仓/全平/调价）

| 操作 | API | 成功后刷新 | 失败后处理 |
|------|-----|-----------|----------|
| 建仓 | POST /session | Session Tab + 模拟 Tab 持仓 | Toast |
| 加仓 | POST /session/{id}/orders | 当前 session 详情 + Unit 网格 | Toast |
| 减仓 | POST /session/{id}/orders | 当前 session 详情 + Unit 网格 | Toast |
| 全平 | POST /session/{id}/close | Session Tab 列表（移除）| Toast |
| 调价 | PUT /session/{id}/line/{line_type} | 当前价格线显示 | Toast + 回弹 |

---

## 七、可访问性 / 国际化（未来）

- **可访问性**（v1.5 不做，Phase 6+ 考虑）：
  - 键盘快捷键（Alt+S 切换策略 / Alt+A 切换账户）
  - 屏幕阅读器支持
- **国际化**（v1.5 不做，Phase 6+ 考虑）：
  - i18n 框架（react-intl / vue-i18n）
  - 中文 / 英文切换

---

## 八、与后端 / 整合的衔接

- **后端**：详见 `02-backend.md`
- **联调 / 错误 / 性能 / 部署**：详见 `04-integration.md`
- **总体设计**：详见 `01-overall.md`
- **主设计文档**（最详细）：`../../0006_数据模型与界面重构设计.md`

---

## 九、9 个核心交互流（后端视角提炼自 0006 §七 + 前端补充）

> 本节补充上文 §五 中未覆盖的 4 个交互流（信号后端触发流程、价格线后端重算流程、Session 生命周期后端处理、海龟过程后端写入）。

### 9.1 策略执行循环（后端 + 前端）

```
[每根 K 线 tick]
    ↓
[后端] fetch_minute_data → 写 futures_min
    ↓
[后端] 策略执行器从 strategies 表读 strategy_id
    ↓
[后端] 策略.on_bar(kline)：
    ├─ 检测到开仓信号 → 写 strategy_signals（仅 entry_long/entry_short）
    ├─ 检测到加仓信号 → 触发 SessionLifecycle.on_signal_add
    ├─ 检测到止损 → 触发 SessionLifecycle.on_signal_close
    └─ 写 strategy_event_log（v1.4 新增）
    ↓
[前端] 3 秒轮询 /strategy/signal/state/{sym} 拉取最新信号
    ↓
[前端] 信号 Tab 重新渲染
```

### 9.2 价格线计算（后端实时算 + 前端拖动触发）

```
[用户] 进入 Session Tab 选中 session
    ↓
[前端] GET /session/{id}/lines?account_id=...
    ↓ 200
[后端] 实时算价格线（详见 02-backend.md §九）
    ↓ 返回 JSON
[前端] 渲染 K 线图 + 价格线
    ↓
[用户] 拖动 add_unit_1 价格线
    ↓
[前端] 实时显示新价格（拖动过程中）
    ↓ 鼠标松开
[前端] 打开 <ConfirmPriceChangeModal>
    ↓ 用户确认
[前端] PUT /session/{id}/line/add_unit_1?account_id=...
    ↓ 200
[后端] 更新 trade_sessions.price_overrides_json
    ↓
[前端] GET /session/{id}/lines 重新拉取
    ↓
[前端] 价格线更新（is_override=true + ⓘ 图标）
```

### 9.3 用户调价流程（K 线图拖动）

```javascript
// K 线图组件初始化
async function initKLChart(symbol, sessionId, accountId) {
    // 1. 加载 K 线
    const klines = await fetch(`/futures/min?contract_code=${symbol}`).then(r => r.json());
    
    // 2. 加载价格线
    const linesData = await fetch(`/session/${sessionId}/lines?account_id=${accountId}`).then(r => r.json());
    
    // 3. 渲染 K 线
    chart.setData(klines);
    
    // 4. 叠加价格线
    for (const line of linesData.lines) {
        const color = line.basis === 'actual_fill' && line.is_triggered
            ? '#F44336'   // 已成交：红色
            : line.is_overridden
                ? '#9C27B0'  // 用户调价：紫色
                : '#2196F3'; // 算法预测：蓝色
        const style = line.is_triggered ? 'solid' : 'dashed';
        
        chart.addHorizontalLine({
            price: line.price,
            color: color,
            lineStyle: style,
            text: line.line_type,
            draggable: !line.is_triggered  // 已成交的线不可拖动
        });
    }
}

// 用户拖动水平线
chart.onHorizontalLineDrag((lineType, newPrice) => {
    // 实时显示新价格（拖动过程中）
    // ...
    
    // 鼠标松开后：
    fetch(`/session/${sessionId}/line/${lineType}?account_id=${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_price: newPrice })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            // 立即重算所有线（递归影响）
            refreshLines();
        } else {
            // 回弹到原价
            chart.revertLine(lineType);
            toast.error(data.message);
        }
    });
});
```

### 9.4 Session 生命周期（后端 + 前端）

```
[信号触发 entry_long] OR [用户点击"➕建仓"]
    ↓
[后端] 拿 session_lock
    ↓ DB SELECT 看是否已 open
[后端] INSERT trade_sessions
    ├─ 成功 → 撮合引擎撮合 first_entry
    │   ├─ 成功 → 写 position_units (unit_index=1)
    │   │       写 turtle_session_data（如果是海龟）
    │   │       写 session_event_log（event_type=created）
    │   └─ 失败 → 状态回退，session 不创建
    └─ UNIQUE 冲突 → 抛异常
    ↓
[前端] POST /session 200
    ↓
[前端] 关闭模态框 + Toast 成功 + 刷新 Session Tab
    ↓
[5 秒轮询] /sessions?status=open 包含新建的 session
```

### 9.5 海龟过程写入（v1.5）

```
[海龟策略] 每根 K 线 tick
    ↓
[策略] 检测：
    ├─ entry_long / entry_short → 写 turtle_trade_process (entry_signal)
    ├─ 0.5N 间隔加仓 → 写 turtle_trade_process (add_signal)
    ├─ 2N 止损价检查 → 触发时存前后 5 根 (stop_loss_check)
    ├─ 20日反向检查 → 触发时存前后 5 根 (check_exit)
    └─ 撮合回报：
        ├─ entry_filled
        ├─ add_filled
        ├─ add_skipped_gap（跳空跳过）
        ├─ stop_loss_triggered
        ├─ exit_20_triggered
        └─ unit_closed
    ↓
[用户] 在 Session Tab 展开"海龟过程流水"面板
    ↓
[前端] GET /session/{id}/trade-process
    ↓ 200
[后端] SELECT * FROM turtle_trade_process WHERE session_id=? ORDER BY bar_time
    ↓ 返回 JSON
[前端] 渲染时间线（10 种 event_type 颜色区分）
    ↓
[用户] 点击某条事件 → 在 K 线图上跳转高亮该 bar_time
```

### 9.6 手动建仓流程（已详 §5.1）

### 9.7 手动加仓流程（已详 §5.2）

### 9.8 手动减仓流程（v1.4 补全）

```
用户在 Session Tab 选中 session
    ↓
点击顶部"➖减仓"
    ↓
打开<ManualAddReduceModal>（action=reduce）
    ↓
用户填写数量 + 点击"确认"
    ↓
[前端] 调用 POST /session/{id}/orders { action: "reduce", quantity: 1 }
    ↓ 200
[后端] 找到最后 unit_index 的 open unit
    ├─ 创建 sim_sell_order
    ├─ 撮合成交
    ├─ 更新 position_units（close_price + close_time + status=closed）
    ├─ 更新 trade_sessions.current_units -1
    ├─ 写 session_event_log（event_type=reduced）
    └─ 写 turtle_trade_process（event_type=unit_closed，如果是海龟）
    ↓
[前端] 关闭模态框 + Toast 成功 + 刷新当前 session 详情
    ↓
[前端] Unit 网格：被关闭的 unit 卡片置灰 + 显示 close_price
```

### 9.9 全部平仓流程（已详 §5.3）

---

## 十、前端 K 线图集成（v1.3 核心实现）

### 10.1 组件接口

```typescript
interface KLineChartProps {
  contractCode: string;
  klineData: KLineData[];              // 日 K 线 / 分 K 线
  priceLines: PriceLine[];             // 价格线数组
  onPriceLineDrag: (lineType: string, newPrice: number) => void;
  markers?: TradeMarker[];             // 回测 Tab 用（买卖点）
  mode: 'signal' | 'session' | 'backtest';
  height?: number;
  theme?: 'light' | 'dark';
}

interface PriceLine {
  line_type: string;                   // entry / add_unit_1 / stop_loss_unit_1 / exit_20
  price: number;
  basis: 'actual_fill' | 'signal';
  is_triggered: boolean;               // 已成交？
  is_overridden: boolean;              // 用户调价？
  color: string;
  style: 'solid' | 'dashed';
  draggable: boolean;
  text?: string;                       // 显示文字
}

interface TradeMarker {
  time: string;
  price: number;
  type: 'buy' | 'sell';
  quantity: number;
}
```

### 10.2 价格线颜色 / 样式约定

| line_type | 颜色 | 线型 | 可拖动 | 含义 |
|-----------|------|------|--------|------|
| `entry` | `#F44336`（红）| solid | 否（已成交）| 已成交 entry |
| `entry`（pending）| `#2196F3`（蓝）| dashed | 是 | 未成交 entry |
| `add_unit_N`（actual）| `#F44336`（红）| solid | 否 | 已成交加仓 |
| `add_unit_N`（predicted）| `#2196F3`（蓝）| dashed | 是 | 预测加仓 |
| `add_unit_N`（override）| `#9C27B0`（紫）| solid | 是 | 用户调价 |
| `stop_loss_unit_N` | `#F44336`（红）| solid | 是 | 止损线 |
| `exit_20` | `#FF9800`（橙）| dashed | 是 | 20日反向离市线 |

**override 后**：实线 + 旁边 ⓘ 图标（hover 显示 `override_at` 时间）

### 10.3 状态联动

```
用户拖动价格线
    ↓ 鼠标按下 → 选中（光标变 ⬍）
    ↓ 拖动中 → 实时显示新价格（其他线自动重算）
    ↓ 鼠标松开 → 打开 <ConfirmPriceChangeModal>
    ↓ 用户确认 → PUT /session/{id}/line/{line_type}
    ↓ 成功 → 标记 is_override=true + 颜色变紫 + 加 ⓘ 图标
    ↓ 失败 → 价格线回弹到原价 + Toast 错误
```

---

## 十一、前后端数据格式约定

### 11.1 列表 API 响应（统一）

```json
{
  "data": [
    { "session_id": "abc-123", "symbol": "AG", "direction": "long", "current_units": 2, "...": "..." }
  ],
  "total": 123,
  "page": 1,
  "page_size": 50,
  "has_more": true
}
```

### 11.2 详情 API 响应（统一）

```json
{
  "data": {
    "session_id": "abc-123",
    "entry_time": "2026-06-02T10:30:00+08:00",
    "entry_basis_price": 7850.0,
    "entry_locked_atr": 120.5,
    "current_units": 2
  }
}
```

### 11.3 错误响应（统一）

```json
{
  "error": "error_code",
  "message": "人类可读消息（中文）",
  "details": {
    "field": "具体错误字段"
  },
  "trace_id": "uuid（用于日志追踪）"
}
```

### 11.4 字段格式约定

| 类型 | 格式 | 示例 |
|------|------|------|
| 时间 | ISO 8601 + 时区 | `2026-06-02T10:30:00+08:00` |
| 金额 | 浮点数，2 位小数 | `7850.00` |
| 数量 | 整数 | `1` |
| UUID | 标准 UUID v4 | `abc-123-def-456` |
| 方向 | `long` / `short` | `long` |
| 状态 | `pending` / `open` / `closed` | `open` |
| 事件类型 | 8 个枚举（session_event_log）| `created` / `added` / `reduced` / `closed` |
| 海龟事件 | 10 个枚举（turtle_trade_process）| `entry_signal` / `entry_filled` / `add_signal` / ... |

---

## 十二、推送 vs 轮询决策详情

| 数据 | 决策 | 频率 | 取消机制 | 失败重试 |
|------|------|------|---------|---------|
| 行情（`/quotes`）| **轮询** | 3 秒 | `AbortController` 组件卸载时取消 | 1 次重试 |
| 信号（`/signal/state`）| **轮询** | 5 秒 | `AbortController` | 1 次重试 |
| 持仓（`/sim/positions`）| **轮询** | 5 秒 | `AbortController` | 1 次重试 |
| open sessions（`/sessions?status=open`）| **轮询** | 5 秒 | `AbortController` | 1 次重试 |
| 事件流（`/session/{id}/events`）| **轮询** | 10 秒 | `AbortController` | 1 次重试 |
| 海龟过程（`/session/{id}/trade-process`）| **轮询** | 10 秒 | `AbortController` | 1 次重试 |

**为什么不用 WebSocket？**
- 实现复杂度高（连接管理 / 心跳 / 重连）
- 当前业务量级不需要实时推送
- 简单可控，便于调试
- **未来优化**：Phase 6+ 可考虑 WebSocket 推送

**轮询实现模板**：

```typescript
function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  
  useEffect(() => {
    let timer: NodeJS.Timeout;
    
    const poll = async () => {
      abortRef.current = new AbortController();
      try {
        const result = await fetcher();
        setData(result);
        setError(null);
      } catch (e) {
        if (!abortRef.current.signal.aborted) {
          setError(e as Error);
        }
      } finally {
        timer = setTimeout(poll, intervalMs);
      }
    };
    
    poll();
    
    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [intervalMs]);
  
  return { data, error };
}
```

---

## 十三、可访问性 / 性能 / 国际化（v1.5 不做，Phase 6+ 考虑）

### 13.1 可访问性（未来）

- **键盘快捷键**：
  - `Alt+S`：切换策略
  - `Alt+A`：切换账户
  - `Alt+1` ~ `Alt+5`：切换 Tab
  - `Ctrl+E`：建仓
  - `Ctrl+Shift+C`：全平（高危操作需二次确认）
- **屏幕阅读器支持**：ARIA 标签 + 语义化 HTML
- **对比度**：WCAG 2.1 AA 标准

### 13.2 性能（已实现）

- **K 线图**：Canvas 渲染（不用 SVG）
- **表格**：虚拟滚动（`vue-virtual-scroller` / `react-window`）
- **事件流**：分页 + 折叠面板
- **海龟过程**：分页 + 时间线展示
- **代码分割**：按 Tab 分割（`import()` 动态加载）
- **路由懒加载**：`React.lazy` / `Vue Router` 懒加载
- **第三方库按需引入**：`lodash-es` / `antd` 按需
- **压缩**：gzip / brotli

### 13.3 国际化（未来）

- **i18n 框架**：`react-intl` / `vue-i18n`
- **语言切换**：中文 / 英文
- **数字格式**：千分位 / 小数点本地化
- **时间格式**：本地时区

---

*本文档是 _requirements/data-model-redesign/01-design/ 下的前端设计（v1.5），与主设计文档（0006）保持一致。*
