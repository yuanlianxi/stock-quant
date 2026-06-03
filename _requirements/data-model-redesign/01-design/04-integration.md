# 整合文档：联调 / 错误处理 / 性能 / 部署

> 文档版本：v1.5
> 创建日期：2026-06-01
> 修订日期：2026-06-02
> 负责人：Alex + Blex
> 状态：✅ 完成（v1.5 最新版）

> **本文档是 `0006_数据模型与界面重构设计.md` 的"整合视角"详细拆分**。总体设计看 `01-overall.md`，后端看 `02-backend.md`，前端看 `03-frontend.md`。

---

## 一、联调方案

### 1.1 三个环境

| 环境 | 用途 | 数据 | 部署 |
|------|------|------|------|
| **开发环境** | 前后端联调 | mock 数据 / 小样本真实数据 | 本地 |
| **测试环境** | 集成测试 + 回归测试 | 全量历史数据（脱敏）| 内网 |
| **生产环境** | 真实用户使用 | 真实数据 | 外网 + 备份 |

### 1.2 开发环境联调流程

```
1. 前端启动本地 dev server（vite / webpack-dev-server）
   http://localhost:5173
2. 后端启动本地服务（uvicorn / fastapi）
   http://localhost:8000
3. 前端通过 vite proxy 转发 /api → http://localhost:8000
4. 前后端通过 OpenAPI 自动生成类型 + Mock 数据
5. 联调用例：
   - 启动流程（账户/策略/session 列表）
   - 切换品种（K 线/信号/价格线）
   - 建仓/加仓/减仓/全平（4 个模态框）
   - 调价（拖动价格线）
   - 事件流 / 海龟过程
```

### 1.3 测试环境集成测试

```
测试类型：
1. 单元测试（pytest / jest）
   - 后端：每个 service 函数一个测试用例
   - 前端：每个组件一个测试用例
2. 集成测试（pytest + httpx）
   - 完整 API 调用链（建仓 → 撮合 → 持仓更新 → 事件流）
3. 端到端测试（playwright / cypress）
   - 模拟用户完整操作（启动 → 切换 → 建仓 → 调价 → 全平）
4. 性能测试（locust / k6）
   - 并发 100 用户同时查询 /session/{id}/lines
   - 5 秒轮询 1000 个 session 的 P99 延迟
```

### 1.4 生产环境部署

```
1. 灰度发布：10% 流量 → 50% → 100%
2. 监控指标：
   - API P99 延迟 < 200ms
   - API 错误率 < 0.1%
   - 撮合成功率 > 99.9%
   - DB 连接池使用率 < 80%
3. 回滚预案：
   - DB 迁移回滚脚本（每个 migration 配一个 down）
   - 前端版本切换（CDN 回滚到老版本）
   - 后端版本切换（k8s rollout undo）
```

---

## 二、错误处理（前端 + 后端）

### 2.1 前端错误处理

#### 错误码映射表

| HTTP | 错误码 | 前端处理 | 用户感知 |
|------|--------|---------|---------|
| 400 | `invalid_request` | Toast 提示 | 弹窗："参数错误：xxx" |
| 401 | `unauthorized` | 跳转登录页 | 弹窗："请重新登录" |
| 403 | `forbidden` | Toast 提示 | 弹窗："无权限操作" |
| 404 | `not_found` | Toast 提示 | 弹窗："资源不存在" |
| 409 | `conflict` | Toast 提示 + 自动刷新数据 | 弹窗："状态已变更，请刷新" |
| **423** | **`session_lock_held`** | **Toast + 自动重试 1 次（500ms 后）** | **弹窗："系统忙，请稍后"** |
| 422 | `insufficient_funds` | Toast 提示 | 弹窗："资金不足" |
| 422 | `invalid_session_state` | Toast 提示 | 弹窗："session 已关闭" |
| 429 | `rate_limit_exceeded` | 自动重试 + 指数退避 | 静默（用户无感知）|
| 500 | `internal_error` | Toast + 上报 Sentry | 弹窗："服务异常，请稍后" |
| 502 | `bad_gateway` | Toast + 触发重连 | 弹窗："撮合服务无响应" |
| 503 | `service_unavailable` | Toast | 弹窗："服务维护中" |

#### 错误码本地化消息

```typescript
const ERROR_MESSAGES: Record<string, string> = {
  invalid_request: '参数错误：{details}',
  unauthorized: '请重新登录',
  forbidden: '无权限操作此资源',
  not_found: '资源不存在',
  conflict: '状态已变更，请刷新',
  session_lock_held: '系统忙，请稍后重试',
  insufficient_funds: '资金不足',
  invalid_session_state: 'session 已关闭',
  rate_limit_exceeded: '请求过于频繁',
  internal_error: '服务异常，请稍后重试',
  bad_gateway: '撮合服务无响应',
  service_unavailable: '服务维护中',
};
```

#### 全局错误拦截（axios interceptor 示例）

```typescript
axios.interceptors.response.use(
  response => response,
  async error => {
    const status = error.response?.status;
    const code = error.response?.data?.error;

    if (status === 401) {
      // 跳转登录
      router.push('/login');
    } else if (status === 423) {
      // session_lock_held：自动重试 1 次
      await new Promise(r => setTimeout(r, 500));
      return axios.request(error.config);
    } else if (status === 429) {
      // rate_limit：指数退避
      const retryAfter = error.response.headers['retry-after'] || 1;
      await new Promise(r => setTimeout(r, retryAfter * 1000));
      return axios.request(error.config);
    } else {
      // 其他错误：Toast
      toast.error(ERROR_MESSAGES[code] || '未知错误');
      Sentry.captureException(error);
    }
    return Promise.reject(error);
  }
);
```

### 2.2 后端错误处理

#### 重试策略（不长时间死等）

| 场景 | 重试次数 | 重试间隔 | 降级路径 |
|------|---------|---------|---------|
| DB 连接失败 | 3 次 | 1s, 2s, 4s（指数退避）| 抛 500 给前端 |
| 撮合引擎无响应 | 2 次 | 1s, 2s | 抛 502 给前端 |
| 行情推送失败 | 无限重试 | 5s 固定 | 静默失败（不影响主流程）|
| 第三方 API（CTP / 行情）| 3 次 | 1s, 2s, 4s | 降级到本地缓存数据 |

> **核心原则**：API 调用错误 → 立即重试，不长时间调试或死等（详见 AGENTS.md §七+1）。

#### 错误日志

```python
import structlog

logger = structlog.get_logger()

# 业务错误（用户可见）
logger.warning("session_lock_held", session_id=session_id, account_id=account_id)

# 系统错误（运维可见）
logger.error("db_connection_failed", error=str(e), retry_count=retry_count)

# 致命错误（告警 + 立即通知）
logger.critical("matching_engine_down", error=str(e))
# 触发 PagerDuty / 飞书机器人告警
```

#### 错误响应格式（统一）

```json
{
  "error": "error_code",
  "message": "人类可读消息（英文）",
  "details": {
    "field": "具体错误字段"
  },
  "trace_id": "uuid（用于日志追踪）"
}
```

---

## 三、性能考量

### 3.1 后端性能

#### API 缓存策略

| API | 缓存策略 | TTL | 失效时机 |
|-----|---------|-----|---------|
| `GET /accounts` | 内存缓存 | 5 分钟 | 创建/删除账户时主动失效 |
| `GET /strategies?account_id=...` | 内存缓存 | 5 分钟 | 注册新策略时主动失效 |
| `GET /contracts/{symbol}` | 内存缓存 | 1 小时 | 每日同步后主动失效 |
| `GET /quotes/{contract_code}` | **不缓存**（实时）| — | — |
| `GET /futures/daily?contract_code=...` | 内存缓存（同查询参数）| 1 小时 | 用户切换合约时主动失效 |
| `GET /session/{id}/lines?account_id=...` | **不缓存**（实时算）| — | 用户调价时主动失效 |

#### 价格线实时计算性能

- 计算复杂度：O(N) 单元数（一般 < 10 个 line）
- 优化：预计算 K 线 N 值（缓存到内存）
- 目标：< 100ms

#### 表格分页（防大数据量）

| 表 | 分页大小 | 排序 |
|----|---------|------|
| `sim_orders` | 50/页 | 按 time DESC |
| `sim_trades` | 50/页 | 按 time DESC |
| `strategy_signals` | 50/页 | 按 signal_time DESC |
| `session_event_log` | 100/页 | 按 event_at DESC |
| `turtle_trade_process` | 100/页 | 按 kline_time ASC |
| `backtest_runs` | 20/页 | 按 created_at DESC |

### 3.2 前端性能

#### 轮询频率（已优化）

| 数据 | 频率 | 原因 |
|------|------|------|
| 行情 | 3 秒 | 实时性要求高 |
| 信号状态 | 5 秒 | 实时性中等 |
| 持仓 | 5 秒 | 实时性中等 |
| open sessions | 5 秒 | 实时性中等 |
| 事件流 | 10 秒 | 实时性低 |
| 海龟过程 | 10 秒 | 实时性低 |

> 所有轮询使用 `useInterval` + `AbortController`（组件卸载时取消）。

#### 大数据量渲染优化

- **K 线图**：Canvas 渲染（不用 SVG），分时按需加载
- **表格**：虚拟滚动（vue-virtual-scroller / react-window）
- **事件流**：分页 + 折叠面板（默认折叠）
- **海龟过程**：分页 + 时间线展示

#### 打包优化

- 代码分割（按 Tab 分割）
- 路由懒加载
- 第三方库按需引入（lodash-es / antd 按需）
- 压缩：gzip / brotli

### 3.3 数据库性能

#### 索引（已建 + 待建）

**已建**：
- 主键索引（自动）
- 外键索引
- 业务唯一索引（trade_sessions UNIQUE）
- 部分索引（trade_sessions idx_ts_status_open）

**待建**（Phase 1-3 实施时确认）：
- `idx_ttp_session_time`（turtle_trade_process）
- `idx_sesl_session_at`（session_event_log）
- `idx_sel_strategy_at`（strategy_event_log）

#### 查询优化

- N+1 问题：批量查询 + JOIN
- 大结果集：分页 + 游标
- 频繁查询：物化视图 / 缓存

#### 数据库连接池

- 开发：10 个连接
- 测试：50 个连接
- 生产：200 个连接（根据实际负载调整）

---

## 四、部署顺序（Phase 1-7）

> 详见 `0006_数据模型与界面重构设计.md` §九，本节为摘要。

### Phase 1：合约行情领域（3-4 天）

**目标**：
- 4 张表创建 + 索引
- 5 个 API（contracts / quotes / daily / min）
- 数据同步脚本（每日 16:00 同步日线 + 主力合约识别）

**验收**：
- 品种网格能列出 AG 下所有合约
- 主力合约高亮
- K 线图能加载日线 + 分时

### Phase 2：策略领域（3 天）

**目标**：
- 6 张表创建 + 索引（strategies / strategy_param_history / strategy_signals / strategy_event_log / turtle_trade_process）
- 7 个 API（strategies CRUD / signal state / signal history）
- 策略代码组织（`strategies/<type>/V<N>/strategy.py`）
- 策略执行器（loader + 主循环）

**验收**：
- 策略切换器能切换海龟 V1
- 策略执行器能生成 entry_long / entry_short 信号

### Phase 3：交易 / 账户领域（10-12 天，v1.4 + v1.5 强化）

**目标**：
- 10 张表创建 + 索引（trade_sessions / sim_account / sim_orders / sim_trades / sim_positions / position_units / turtle_session_data / session_event_log + 3 预留 live_*）
- 12 个 API（含 v1.4 新增 6 个）
- 撮合引擎（sim_engine）
- Session 生命周期管理器（session_lifecycle）
- 事件流写入服务（event_logger）
- 4 个模态框前端
- 顶部操作组前端

**验收**：
- 手动建仓 → 撮合 → 持仓更新 → 事件流 → 单元详情
- 加仓到 4 Unit
- 调价生效（override + is_override 标记）
- 全部平仓 → session 从 open 列表消失
- 并发 423 处理

### Phase 4：回测持久化（3 天）

**目标**：
- 1 张表创建 + 索引（backtest_runs）
- 3 个 API（runs / 详情 / 成交）
- 回测结果持久化（每次回测完成写 backtest_runs）
- 回测 Tab 前端（列表 + 详情 + 成交）

**验收**：
- 跑完一次回测后，列表能看到
- 点击详情能看 K 线 + 买卖点标记 + 成交列表

### Phase 5：账户中心页（2 天）

**目标**：
- 账户信息卡前端
- 账户总览 API（/account/overview）

**验收**：
- 模拟 Tab 顶部账户信息卡正确显示余额 / 可用 / 保证金 / 盈亏

### Phase 6：单元 + 集成测试（2-3 天）

**目标**：
- 单元测试覆盖率 > 80%
- 集成测试覆盖 4 个核心流程
- 端到端测试（playwright）
- 性能测试（locust）

**验收**：
- 自动化测试全部通过
- 性能指标达标

### Phase 7（可选）：CTP 接入（后续）

**目标**：
- CTP 接口对接
- live_orders / live_trades / live_positions 启用
- 真实 Tab 启用

**v1.5 状态**：未实施。

---

## 五、监控告警

### 5.1 关键指标（Metrics）

| 类别 | 指标 | 阈值 | 告警级别 |
|------|------|------|---------|
| **API 性能** | P99 延迟 | > 500ms | Warning |
| | P99 延迟 | > 1s | Critical |
| **API 错误率** | 5xx 错误率 | > 0.1% | Warning |
| | 5xx 错误率 | > 1% | Critical |
| **撮合引擎** | 撮合成功率 | < 99.9% | Warning |
| | 撮合成功率 | < 99% | Critical |
| **数据库** | 连接池使用率 | > 80% | Warning |
| | 连接池使用率 | > 95% | Critical |
| **业务** | session_lock_held 比例 | > 5% | Warning |
| | open session 数 | > 100 | Info |

### 5.2 告警渠道

| 级别 | 渠道 | 响应时间 |
|------|------|---------|
| **Critical** | 飞书机器人 + 短信 + 电话 | 5 分钟内 |
| **Warning** | 飞书机器人 | 30 分钟内 |
| **Info** | 飞书机器人（群消息）| 当日处理 |

### 5.3 日志

- **结构化日志**：JSON 格式（structlog）
- **日志级别**：DEBUG / INFO / WARNING / ERROR / CRITICAL
- **日志保留**：30 天（生产环境）
- **日志聚合**：ELK / Loki

### 5.4 链路追踪

- **Trace ID**：每个请求生成 UUID
- **传递方式**：HTTP Header（X-Trace-Id）
- **追踪工具**：Jaeger / Zipkin（可选）

---

## 六、安全性

### 6.1 认证 & 授权

- **认证**：JWT（access_token + refresh_token）
- **授权**：RBAC（角色：viewer / trader / admin）
- **关键操作二次确认**：建仓/加仓/减仓/全平（前端模态框确认）

### 6.2 数据安全

- **传输加密**：HTTPS（TLS 1.3）
- **存储加密**：DB 字段级加密（敏感字段：password / token）
- **日志脱敏**：账户密码 / token 不写日志

### 6.3 API 安全

- **限流**：单账户每秒 < 10 次下单（429 拒绝）
- **CSRF**：前后端分离，CSRF 风险低
- **CORS**：生产环境限制白名单
- **SQL 注入**：使用 ORM（SQLAlchemy / Tortoise ORM）
- **XSS**：前端 React/Vue 自动转义

---

## 七、风险与回退

### 7.1 主要风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 撮合引擎性能不达标 | 中 | 高 | 提前性能测试，必要时降级到 5 秒撮合 |
| Session 并发 423 频繁 | 中 | 中 | 调优互斥锁粒度（按 (account_id, symbol) 而非全局）|
| 价格线计算慢 | 低 | 中 | 预计算 N 值缓存到内存 |
| 数据迁移失败 | 中 | 高 | 完整备份 + 回滚脚本 |
| 真实 Tab 误启用 | 低 | 中 | 强 Feature Flag（默认关闭）|

### 7.2 回退方案

| 场景 | 回退方案 |
|------|---------|
| Phase 3 上线后问题多 | 回滚到 Phase 2 状态（DB 迁移 down + 前端回滚）|
| 撮合引擎严重 bug | 切换到 5 秒轮询人工模式（半自动）|
| 价格线计算慢 | 临时回退到"持久化 trade_session_lines 表"（v1.3 旧版方案）|
| CTP 接入有问题 | 关闭真实 Tab（Feature Flag）|

---

## 八、文档与培训

### 8.1 文档清单

- [x] 总体设计（01-overall.md）
- [x] 后端设计（02-backend.md）
- [x] 前端设计（03-frontend.md）
- [x] 整合文档（本文档）
- [x] 主设计文档（0006_数据模型与界面重构设计.md）
- [x] 主变更日志（0003_变更日志.md）
- [ ] API 文档（OpenAPI 自动生成 + Swagger UI）
- [ ] 部署手册（DEPLOY.md）
- [ ] 运维手册（OPERATIONS.md）

### 8.2 培训

- **开发培训**：1 小时（讲解整体架构 + 关键决策）
- **测试培训**：30 分钟（讲解测试环境 + 用例）
- **运维培训**：30 分钟（讲解监控告警 + 回退方案）

---

## 九、与总体 / 后端 / 前端的衔接

- **总体设计**：详见 `01-overall.md`
- **后端**：详见 `02-backend.md`
- **前端**：详见 `03-frontend.md`
- **主设计文档**（最详细）：`../../0006_数据模型与界面重构设计.md`

---

## 十、详细测试用例（覆盖 4 个核心流程）

### 10.1 手动建仓流程

| # | 测试场景 | 预期结果 | 验收点 |
|---|---------|---------|--------|
| 1 | 正常建仓（市场 open 时）| 200 + 新建 session + Unit #1 | session.status=open, current_units=1 |
| 2 | 资金不足 | 422 insufficient_funds | 账户余额 < 建仓所需保证金 |
| 3 | 合约已收盘 | 撮合失败 → session.status=pending | 等开盘后重试 |
| 4 | 同一账户同方向已有 open session | UNIQUE 冲突 → 423 session_lock_held | 不创建新 session |
| 5 | 并发 2 个手动建仓 | 1 个成功 1 个 423 | asyncio.Lock 生效 |
| 6 | 限价单（价格未到）| session.status=pending | 等价格触及后撮合 |

### 10.2 手动加仓流程

| # | 测试场景 | 预期结果 | 验收点 |
|---|---------|---------|--------|
| 1 | 当前 1 Unit 加仓到 2 Unit | 200 + 新建 Unit #2 | position_units 新增 1 行 |
| 2 | 当前 4 Unit 加仓到 5 Unit | 422 invalid_session_state | max_units=4 限制 |
| 3 | 加仓数量 > 1（加多份）| 200 + 多个 Unit 一次性建 | unit_index 递增 |
| 4 | session 已 close | 422 invalid_session_state | 不允许在已关闭 session 上加仓 |
| 5 | 跳空加仓（K 线越过加仓价）| unit 创建但 is_gap=1 | turtle_session_data.skip_add_count +1 |

### 10.3 用户调价流程

| # | 测试场景 | 预期结果 | 验收点 |
|---|---------|---------|--------|
| 1 | session.status=open 调价 | 200 + price_overrides_json 更新 | 重新计算时使用新价 |
| 2 | session.status=closed 调价 | 422 invalid_session_state | 不允许 |
| 3 | 调价价格 < 0 | 400 invalid_request | 校验失败 |
| 4 | 调价后该线已成交（actual_fill）| 200 但 override 不生效 | 子线重算用 actual_fill |
| 5 | K 线图拖动 + 确认弹窗取消 | 价格线回弹到原价 | UI 联动正确 |

### 10.4 全部平仓流程

| # | 测试场景 | 预期结果 | 验收点 |
|---|---------|---------|--------|
| 1 | session.status=open 全平 | 200 + session.status=closed + 所有 unit closed | realized_pnl 计算正确 |
| 2 | session.status=closed 全平 | 409 conflict | 不允许重复 close |
| 3 | 全平 4 Unit | 4 个 close_trade 创建 | sim_trades 4 行 |
| 4 | 止损触发自动全平 | session.status=closed + exit_reason=stop_loss | 自动触发 |
| 5 | 20日反向自动全平 | session.status=closed + exit_reason=exit_20 | 自动触发 |

### 10.5 并发 & 性能测试

| # | 测试场景 | 目标 | 验收点 |
|---|---------|------|--------|
| 1 | 100 用户同时查询 /session/{id}/lines | P99 < 100ms | locust 压测 |
| 2 | 5 秒轮询 1000 个 session | 内存 < 500MB | 资源占用 |
| 3 | DB 连接池 50 并发 | 无连接超时 | 池配置 + 监控 |
| 4 | WebSocket 替代轮询（未来）| P99 < 50ms | 优化验证 |

---

## 十一、详细部署步骤

### 11.1 后端部署（FastAPI + Uvicorn）

```bash
# 1. 拉代码
cd /home/yuan/projects/stock-quant
git pull origin master

# 2. 装依赖
pip install -r requirements.txt

# 3. 跑 migration
python scripts/migrate.py --to v1.5

# 4. 启动服务（开发）
uvicorn api.main:app --reload --port 8000

# 5. 启动服务（生产）
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 11.2 前端部署（Vite + Nginx）

```bash
# 1. 拉代码
cd /home/yuan/projects/stock-quant/www
git pull origin master

# 2. 装依赖
npm install

# 3. 打包
npm run build  # 输出到 dist/

# 4. 上传到服务器
scp -r dist/* user@server:/var/www/stock-quant/

# 5. Nginx 配置（/etc/nginx/sites-enabled/stock-quant）
server {
    listen 80;
    server_name quant.example.com;
    
    location / {
        root /var/www/stock-quant;
        try_files $uri $uri/ /index.html;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Trace-Id $request_id;
    }
}
```

### 11.3 数据库迁移

```bash
# 单次迁移
python scripts/migrate.py --to v1.5

# 回滚（每个 migration 配一个 down）
python scripts/migrate.py --rollback v1.4

# 查看 migration 状态
python scripts/migrate.py --status
```

**Migration 清单（v1.0 → v1.5）**：

| # | 迁移 | 表 | 操作 |
|---|------|----|----|
| 1 | v1.0 | 4 张表 | CREATE futures_contracts / futures_quotes / futures_daily / futures_min |
| 2 | v1.1 | 1 张表 | CREATE strategy_param_history |
| 3 | v1.2 | 5 张表 | CREATE strategies / strategy_signals / trade_sessions / sim_account / sim_orders / sim_trades / sim_positions / position_units / backtest_runs |
| 4 | v1.3 | ALTER | +account_id / +price_overrides_json / +main_contract_code / +date / +atr / DROP futures_atr / DROP strategy_signal_states |
| 5 | v1.4 | 3 张表 | CREATE turtle_session_data / session_event_log / strategy_event_log |
| 6 | v1.5 | 1 张表 | CREATE turtle_trade_process |

### 11.4 灰度发布

```
1. 10% 流量（30 分钟）
   - 监控 API P99 延迟、错误率
   - 用户反馈渠道（飞书群）
2. 50% 流量（1 小时）
   - 监控同上
3. 100% 流量
   - 持续监控 24 小时
4. 异常立即回滚
   - 触发条件：错误率 > 1% 或 P99 > 1s
```

### 11.5 回滚流程

```
1. 停止新版本：kubectl rollout undo deployment/api
2. 回滚 DB：python scripts/migrate.py --rollback v1.4
3. 回滚前端：CDN 回滚到老版本（保留最近 5 个版本）
4. 通知用户：飞书群 + 邮件
5. 复盘：记录到 deploy-log.md
```

---

## 十二、详细安全性

### 12.1 认证 & 授权

**JWT 实现**：
```python
# 登录
@app.post("/auth/login")
async def login(username: str, password: str):
    user = verify_user(username, password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    access_token = create_jwt(
        payload={"user_id": user.id, "role": user.role},
        expires_in=3600  # 1 小时
    )
    refresh_token = create_jwt(
        payload={"user_id": user.id, "type": "refresh"},
        expires_in=86400 * 7  # 7 天
    )
    return {"access_token": access_token, "refresh_token": refresh_token}

# 鉴权
async def require_role(role: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            token = extract_token_from_header()
            payload = decode_jwt(token)
            if payload.get("role") != role:
                raise HTTPException(403, "Forbidden")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@app.post("/session")
@require_role("trader")
async def create_session(...): ...
```

**RBAC 角色**：

| 角色 | 权限 |
|------|------|
| `viewer` | 只读（GET 类）|
| `trader` | 读写（下单/调价）|
| `admin` | 全部（含用户管理）|

### 12.2 数据安全

- **传输加密**：HTTPS（TLS 1.3），HTTP 强制 301 跳转
- **存储加密**：DB 字段级加密（敏感字段：`password` / `token`）
  ```python
  from cryptography.fernet import Fernet
  
  def encrypt_field(plaintext: str) -> str:
      return Fernet.load_key().encrypt(plaintext.encode()).decode()
  
  def decrypt_field(ciphertext: str) -> str:
      return Fernet.load_key().decrypt(ciphertext.encode()).decode()
  ```
- **日志脱敏**：账户密码 / token 不写日志
  ```python
  logger.info("user_login", user_id=user.id, password="***")  # 脱敏
  ```

### 12.3 API 安全

- **限流**：单账户每秒 < 10 次下单（429 拒绝）
  ```python
  from slowapi import Limiter
  
  limiter = Limiter(key_func=lambda: get_current_account_id())
  
  @app.post("/session")
  @limiter.limit("10/second")
  async def create_session(...): ...
  ```
- **CSRF**：前后端分离，CSRF 风险低，但保留 SameSite Cookie 兜底
- **CORS**：生产环境限制白名单
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://quant.example.com"],
      allow_methods=["GET", "POST", "PUT", "DELETE"],
      allow_headers=["*"],
  )
  ```
- **SQL 注入**：使用 ORM（SQLAlchemy / Tortoise ORM），禁止字符串拼接 SQL
- **XSS**：前端 React/Vue 自动转义；危险内容用 `dangerouslySetInnerHTML` 时需过滤

### 12.4 审计日志

```python
@app.middleware("http")
async def audit_log(request: Request, call_next):
    user_id = get_current_user_id()
    log = {
        "user_id": user_id,
        "method": request.method,
        "path": request.url.path,
        "ip": request.client.host,
        "timestamp": datetime.now().isoformat(),
    }
    
    response = await call_next(request)
    log["status_code"] = response.status_code
    
    if request.method in ("POST", "PUT", "DELETE"):
        logger.info("audit", **log)
        # 写 audit_log 表
        await db.execute("INSERT INTO audit_log ...")
    
    return response
```

**审计日志表**：

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT,
    action      TEXT NOT NULL,           -- create_session / override_line / close_session
    target_id   TEXT,                    -- session_id / line_type
    context_json TEXT,
    ip          TEXT,
    user_agent  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

---

## 十三、链路追踪与日志聚合

### 13.1 链路追踪

**Trace ID 传递**：

```python
# 后端入口生成 trace_id
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    # 传递到下游
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
```

```typescript
// 前端 axios interceptor 添加 trace_id
axios.interceptors.request.use(config => {
  config.headers['X-Trace-Id'] = generateUUID();
  return config;
});
```

### 13.2 结构化日志

```python
import structlog

logger = structlog.get_logger()

# 业务日志
logger.info("session_created",
    session_id=session_id,
    account_id=account_id,
    strategy_id=strategy_id,
    trace_id=request.state.trace_id
)

# 错误日志（含堆栈）
logger.error("db_query_failed",
    error=str(e),
    query=query,
    params=params,
    trace_id=request.state.trace_id,
    exc_info=True
)
```

**日志格式（JSON）**：
```json
{
  "event": "session_created",
  "session_id": "abc-123",
  "account_id": "sim_001",
  "strategy_id": "turtle_v1",
  "trace_id": "uuid",
  "timestamp": "2026-06-02T10:30:00+08:00",
  "level": "info"
}
```

### 13.3 日志聚合（ELK / Loki）

**Loki + Grafana** 配置示例：

```yaml
# promtail 配置（采集本地日志）
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: stock-quant
    static_configs:
      - targets: [localhost]
        labels:
          job: stock-quant
          __path__: /var/log/stock-quant/*.log
```

**Grafana 查询**：

```logql
{job="stock-quant"} |= "error" | json | level="error"
```

---

## 十四、上线检查清单（Go-Live Checklist）

### 14.1 部署前

- [ ] 代码 review 通过
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过
- [ ] 性能测试达标（P99 < 200ms）
- [ ] 安全扫描通过（无高危漏洞）
- [ ] DB migration 脚本测试通过（含回滚）
- [ ] 配置文件检查（生产环境 URL / Token）

### 14.2 部署中

- [ ] 后端镜像构建成功
- [ ] 前端打包成功
- [ ] DB migration 执行成功
- [ ] Nginx 配置 reload
- [ ] 服务启动无报错
- [ ] 健康检查 endpoint 200

### 14.3 部署后

- [ ] 5xx 错误率 < 0.1%
- [ ] P99 延迟 < 500ms
- [ ] 撮合成功率 > 99.9%
- [ ] 用户可正常登录
- [ ] 用户可正常建仓 / 加仓 / 平仓
- [ ] 价格线拖动可生效
- [ ] 监控告警无 critical 告警
- [ ] 飞书群通知用户

### 14.4 紧急回滚触发条件

- 5xx 错误率 > 1%（持续 5 分钟）
- P99 延迟 > 1s（持续 5 分钟）
- 用户无法登录（持续 5 分钟）
- DB 写入失败
- 价格线计算错误
- 撮合引擎崩溃

---

*本文档是 _requirements/data-model-redesign/01-design/ 下的整合文档（v1.5），与主设计文档（0006）保持一致。*
