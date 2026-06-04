# Stock Quant - 期货量化交易系统 v1.5

> 数据驱动的期货策略回测 / 模拟交易 / 监控一体化平台

| 项目 | 值 |
|------|---|
| **项目名称** | Stock Quant |
| **当前版本** | v1.5 |
| **项目路径** | `~/.openclaw/workspace/projects/stock-quant/` |
| **仓库** | Gitee + GitHub 双端同步 |
| **飞书根节点** | 股票量化 (`CAmhwOvBLiXhaUkVidccCluDnxg`) |
| **技术栈** | Python 3.12+ / FastAPI / SQLite / akshare |

---

## 🚀 启动流程

### 前置条件

- Python 3.12+
- 安装依赖：`pip install -r requirements.txt`
- 初始化数据库（一次性）：`python3 -c "from data.data_loader import init_db; init_db()"`
- 数据库文件路径：`data/futures_akshare.db`

### 启动 API 服务（必做）

```bash
cd /home/yuan/.openclaw/workspace/projects/stock-quant
nohup python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning > /tmp/uvicorn.log 2>&1 &
disown
sleep 4
curl http://localhost:8000/health  # 验证：{"status":"healthy"}
```

**端口**：`8000`  
**健康检查**：`GET /health` → `{"status":"healthy"}`  
**根路径**：`GET /` → `{"message":"Stock Quant API","version":"1.5"}`

### 启动前端

```bash
# 前端是单文件 index.html（不需要 build）
# 方式 1：直接用浏览器打开
#   open www/index.html

# 方式 2：用 HTTP 服务器（推荐）
cd www
python3 -m http.server 8080
# 访问 http://localhost:8080
```

**前端端口**：`8080`  
**入口文件**：`www/index.html`（2119 行，单文件包含 HTML+CSS+JS）

### 跑测试

```bash
cd /home/yuan/.openclaw/workspace/projects/stock-quant
pytest tests/ -v                              # 82 个用例
pytest tests/ --cov=api.services --cov=strategies  # 覆盖率
```

### 完整启动检查清单

| 步骤 | 命令 | 期望输出 |
|------|------|----------|
| 1. 装依赖 | `pip install -r requirements.txt` | 无报错 |
| 2. 初始化 DB | `python3 -c "from data.data_loader import init_db; init_db()"` | 22 张表创建 |
| 3. 启动 API | `nohup python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning > /tmp/uvicorn.log 2>&1 &` | 后台进程 |
| 4. 健康检查 | `curl http://localhost:8000/health` | `{"status":"healthy"}` |
| 5. 启动前端 | `cd www && python3 -m http.server 8080` | 浏览器访问 8080 |
| 6. 跑测试 | `pytest tests/ -v` | 82/82 通过 |

---

## 🌐 系统架构（4 大功能模块）

| 模块 | 路径 | 职责 | 入口 | 规模 |
|------|------|------|------|------|
| **数据层** | `data/data_loader.py` | 22 张表 + 5 FK + 7 索引 + init_db | `from data.data_loader import init_db, get_futures_daily` | 2228 行 |
| **API 层** | `api/main.py` + `api/routers/` | 9 域 44 端点 + 根 2 端点（sq-0008 拆分） | http://localhost:8000/docs（Swagger 自动生成） | main 80 行 / routers 1599 行 |
| **策略层** | `strategies/` | turtle V1 海龟系统 + loader + executor + trade_process_logger | `from strategies.loader import get_strategy` | base / loader / executor / trade_process_logger / turtle/ |
| **前端层** | `www/index.html` | 4 模态 + 顶部操作 + 8 汇总卡片 + K 线图 + 4 Unit + 价格线 + 时间线 | http://localhost:8080/ | 2119 行 |

### 数据层详情

- **表数量**：22 张（v1.5 比 v1.4 多 1 张 turtle_trade_process）
- **外键**：5 个 FK 关系
- **索引**：7 个索引
- **核心表**：`contracts` / `quotes_daily` / `quotes_minute` / `strategies` / `sessions` / `units` / `orders` / `events` / `lines` / `backtest_runs` / `turtle_trade_process` 等
- **数据源**：akshare（期货数据）+ baostock（股票辅助）

### API 层详情

- **总端点数**：46 个（44 router 端点 + 根 2 端点）
- **框架**：FastAPI + Pydantic v2
- **架构**：分层 router → service → data（sq-0008 拆分后）
- **入口**：`api/main.py`（80 行，9 router 注册 + 根 2 端点 + 静态文件）
- **routers/**：9 文件 / 1599 行（详见后端结构）
- **schemas/**：8 文件 / 561 行 Pydantic 类
- **helpers/**：4 文件（backtest_runner / signal_calc / pnl / factor）
- **state.py**：进程内共享状态（position_manager + cached_prices）
- **自动文档**：`/docs`（Swagger UI）+ `/redoc`（ReDoc）

### 策略层详情

- `base.py`：策略基类（信号生成、订单执行抽象）
- `loader.py`：策略加载器（YAML 配置 → 实例）
- `executor.py`：订单执行器（建仓/加仓/减仓/平仓）
- `trade_process_logger.py`：海龟交易过程日志
- `turtle/`：海龟策略实现
  - `factors.py`：因子计算（ATR、55日突破、20日离场）
  - `position.py`：持仓管理
  - `V1/`：海龟 V1 版本完整实现

### 前端层详情

- **单文件**：`www/index.html`（HTML + CSS + JS 全栈）
- **4 个模态框**：建仓 / 加仓 / 减仓 / 全部平仓
- **8 个汇总卡片**：余额 / 可用 / 持仓 / 浮动盈亏 / 已实现 / Open Sessions / Open Units / 近 N 天成交
- **4 Unit 详情面板**：每个 session 显示 4 个 unit 卡片
- **跳空标志**：跳空（is_gap=1）的 unit 显示 ⚠️ 金色边
- **价格线**：调价 3 色线（红止损 / 蓝加仓 / 紫 20日反向）
- **时间线**：订单 / 信号 / 调价事件时间线
- **K 线图**：双击调价 + 拖动水平线 → PUT /session/{id}/line/{line_type}

---

## 🎯 功能模块入口（用户端）

### 主界面（K 线图 + 品种网格）

- 访问 `www/index.html`
- 默认显示合约/品种行情
- 点击品种卡片看详情
- 顶部"📊 账户中心"按钮看汇总

### 4 个操作模态框（顶部按钮）

- **📈 建仓**：手动建仓（输入合约 + 方向 + unit 数）
- **➕ 加仓**：0.5N 间隔加仓（金字塔）
- **➖ 减仓**：减仓单个 unit
- **🚪 全部平仓**：关闭整个 session

### 8 个账户汇总卡片

| 卡片 | 数据来源 API | 说明 |
|------|---------------|------|
| 余额 | GET /account/overview | 总资金 |
| 可用 | GET /account/overview | 余额 - 占用保证金 |
| 持仓 | GET /account/overview | 当前持仓市值 |
| 浮动盈亏 | GET /account/overview | 未实现盈亏 |
| 已实现 | GET /account/overview | 已平仓盈亏 |
| Open Sessions | GET /account/overview | 进行中的 session 数 |
| Open Units | GET /account/overview | 所有 session 的 unit 总和 |
| 近 N 天成交 | GET /account/{id}/trades | 最近交易记录 |

### 4 Unit 详情面板 + 跳空标志

- 每个 session 显示 4 个 unit 卡片（建仓 + 3 次加仓）
- 跳空（is_gap=1）的 unit 显示 ⚠️ 金色边
- 跳空指开盘价相对前收跳空（可能改变 unit 成本基准）

### 调价集成（双击 K 线图）

- 调价 3 色线（红止损 / 蓝加仓 / 紫 20日反向）
- 用户拖动水平线 → PUT /session/{id}/line/{line_type}
- 系统实时重算 + 持久化

---

## 🛠️ 管理端 / API 入口

### Swagger 文档

```
http://localhost:8000/docs    # FastAPI Swagger UI
http://localhost:8000/redoc   # ReDoc 风格
```

### 后端结构（sq-0008 拆分后）

#### 入口

- `api/main.py`（80 行）：FastAPI app + 9 router 注册 + 全局 `position_manager` + 静态文件挂载 + 根 2 端点（`/`、`/health`）
- `api/state.py`（17 行）：进程内共享状态（`cached_prices` dict + `position_manager` 实例位置说明）

#### routers/（9 文件 / 1599 行 / 44 端点）

| 文件 | 行数 | 端点数 | 主要路径前缀 |
|------|------|-------|------------|
| `session.py` | 315 | 9 | `/session`, `/sessions` |
| `strategy.py` | 303 | 8 | `/strategies` |
| `market.py` | 289 | 6 | `/contracts`, `/quotes`, `/main-contract`, `/minute`, `/daily` |
| `account.py` | 261 | 5 | `/account` |
| `backtest.py` | 211 | 5 | `/backtest` |
| `turtle.py` | 85 | 6 | `/turtle/signals`, `/turtle/scan` |
| `position.py` | 74 | 2 | `/position` |
| `signal.py` | 43 | 2 | `/signals` |
| `cache.py` | 18 | 1 | `/cache` |
| **合计** | **1599** | **44** | — |

#### schemas/（8 文件 / 561 行 Pydantic 类）

| 文件 | 行数 | 主要模型 |
|------|------|----------|
| `session.py` | 100 | SessionEvent/Order/Lines/TradeProcess |
| `account.py` | 98 | Overview/Position/Unit/Trades |
| `backtest.py` | 90 | BacktestResponse/Run/Trades |
| `market.py` | 69 | Contracts/Quotes/Daily/Minute |
| `strategy.py` | 66 | Strategy/Event/Signal/ParamHistory |
| `signal.py` | 28 | Signal/All |
| `common.py` | 26 | ErrorResponse/HealthResponse |
| `position.py` | 26 | PositionResponse/AddRequest |
| **合计** | **561** | — |

#### helpers/（4 文件 / 387 行）

- `backtest_runner.py`（263 行）— 回测执行辅助
- `signal_calc.py`（76 行）— 信号计算
- `factor.py`（23 行）— 因子工具
- `pnl.py`（20 行）— 盈亏计算

#### services/（业务逻辑层，未拆分）

- `sim_engine.py`（`SimEngine` 撮合引擎）
- `session_lifecycle.py`（session 生命周期）
- `line_calculator.py`（价格线计算）
- `event_logger.py`（事件日志）

#### 备份（main.py 历史快照）

- `api/main.py.bak.20260604-pre-p4`（1452 行，md5 `5cd0d1cbace85b055e10bfbee8a6ee3f`）— P4 拆分前 baseline
- `api/main.py.bak.20260604-sq-0008-final`（80 行，md5 `a47fff36d04abbc7000945afea0ae4f0`）— sq-0008 完工快照

### 46 端点清单（按 router 分类，sq-0008 后）

#### signal router（2）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/signals/all` | 批量所有品种信号 |
| GET | `/signals/{symbol}` | 单品种信号 |

#### cache router（1）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/cache/status` | 缓存状态诊断 |

#### position router（2）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/position/{symbol}` | 查询持仓 |
| POST | `/position/{symbol}/add` | 手动登记持仓 |

#### account router（5）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/account/overview` | 账户总览（聚合 5 表 + 价格线） |
| GET | `/account/{account_id}/positions` | 账户持仓 |
| GET | `/account/{account_id}/units` | 账户 4 Unit 明细 |
| GET | `/account/{account_id}/sessions` | 账户 sessions |
| GET | `/account/{account_id}/trades` | 账户成交 |

#### market router（6）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/contracts/{symbol}` | 合约列表 |
| GET | `/quotes/{contract_code}` | 行情 |
| GET | `/main-contract/{symbol}` | 主力合约 |
| GET | `/minute/{symbol}` | 分时数据 |
| GET | `/daily/{symbol}` | 日线数据 |
| POST | `/minute/sync` | 同步分时数据 |

#### backtest router（5）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/backtest/run` | 启动回测 |
| GET | `/backtest/runs` | 回测列表 |
| GET | `/backtest/runs/{run_id}` | 单次回测详情 |
| GET | `/backtest/runs/{run_id}/trades` | 回测成交 |
| GET | `/backtest/{job_id}` | 异步回测状态 |

#### turtle router（6）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/turtle/signals/{symbol}` | 单品种海龟信号 |
| GET | `/turtle/signals/active` | 当前未离市信号 |
| GET | `/turtle/signals/alerts` | 最近 N 分钟新信号 |
| POST | `/turtle/scan/{symbol}` | 扫描历史信号 |
| POST | `/turtle/scan/all` | 全量扫描 |
| GET | `/turtle/signal/latest` | 最新信号 |

#### session router（9）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/session` | 创建 session |
| POST | `/session/{session_id}/orders` | 加仓 |
| POST | `/session/{session_id}/orders/reduce` | 减仓 |
| POST | `/session/{session_id}/close` | 平仓 |
| GET | `/session/{session_id}/events` | session 事件 |
| GET | `/session/{session_id}/trade-process` | 交易过程 |
| GET | `/sessions` | session 列表 |
| GET | `/session/{session_id}/lines` | 价格线 |
| PUT | `/session/{session_id}/line/{line_type}` | 覆盖价格线 |

#### strategy router（8）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/strategies` | 策略列表 |
| GET | `/strategies/{strategy_id}` | 策略详情 |
| POST | `/strategies` | 创建策略 |
| PUT | `/strategies/{strategy_id}` | 更新策略 |
| DELETE | `/strategies/{strategy_id}` | 删除策略 |
| GET | `/strategies/{strategy_id}/signals` | 策略信号 |
| GET | `/strategies/{strategy_id}/param-history` | 参数历史 |
| GET | `/strategies/{strategy_id}/events` | 策略事件 |

#### 根端点（main.py，2）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 主页（FileResponse → `www/index.html`） |
| GET | `/health` | 健康检查 |

**端点总数**：2+1+2+5+6+5+6+9+8+2 = **46**（44 router 端点 + 2 根端点）

---

## ⏰ 后台定时调度

### news-recommendation-system / push_news（v1.5）

- **任务 ID**：`06fe5f13-da63-4e86-8d93-fc7ba056f691`
- **调度**：每天 09:25（上海时间）
- **功能**：抓新闻 + 多领域分类 + 飞书机器人推送
- **脚本路径**：`news-recommendation-system/scripts/daily_push_runner.py`
- **输出**：100 条/天 / ~60s 跑完
- **依赖**：push_news skill v0.2.0

### stock-quant / change-scan

- **调度**：每 30 分钟
- **功能**：扫 git / 飞书变更记录，提醒主 agent
- **状态**：活跃

---

## 🧪 测试

### 跑测试

```bash
pytest tests/ -v                              # 82 个用例
pytest tests/ --cov=api.services --cov=strategies  # 覆盖率
```

### 当前覆盖率（v1.5）

- **总覆盖**：53%
- **5 服务层平均 71.6%**：

| 服务模块 | 覆盖率 | 说明 |
|---------|--------|------|
| sim_engine | 80% | 模拟撮合引擎 |
| loader | 98% | 策略加载器 |
| base | 77% | 策略基类 |
| session_lifecycle | 73% | session 生命周期 |
| line_calculator | 72% | 价格线计算 |
| event_logger | 66% | 事件日志 |
| trade_process_logger | 67% | 海龟交易过程日志 |

### 测试文件清单

| 文件 | 用例数 | 覆盖 |
|------|--------|------|
| `test_sim_engine.py` | ~15 | sim_engine |
| `test_strategy_loader.py` | ~12 | loader |
| `test_session_lifecycle.py` | ~14 | session_lifecycle |
| `test_line_calculator.py` | ~10 | line_calculator |
| `test_event_logger.py` | ~8 | event_logger |
| `test_trade_process_logger.py` | ~10 | trade_process_logger |
| `test_multi_account.py` | ~10 | 多账户 |
| `test_integration.py` | 13 | 端到端集成 |
| **总计** | **82** | 53% |

### 性能基线

| 场景 | 性能 | 测试方式 |
|------|------|----------|
| 100 session 建仓 | 0.84s | pytest benchmark |
| 100 调价 | 0.38s | pytest benchmark |
| 50 session × 4 unit 全平仓 | 1.81s | pytest benchmark |
| locust 5s 压测 | 20.52 RPS / 0 失败 | locust 2.44.0 |

---

## 📚 文档导航（飞书知识库）

| 文档 | 本地路径 | 飞书链接 |
|------|----------|----------|
| 0001 项目设计 | `0001_项目设计.md` | https://feishu.cn/wiki/UJDhw9xJfi6j0uk5KAhcRrZinLc |
| 0002 技术设计 | `0002_技术设计.md` | https://feishu.cn/wiki/U5I7dUb7Zo8PIux8IuNc1cv6njd |
| 0003 变更日志 | `0003_变更日志.md` | https://feishu.cn/wiki/HAH3d7XlaozWYHx5aE6ckjDYnEc |
| 0004 数据源设计 | `0004_数据源设计.md` | https://feishu.cn/wiki/NXIhdHnO0iN0Buk9KK8cvguWnlg |
| 0005 海龟信号监控设计 | `0005_海龟信号监控设计.md` | https://feishu.cn/wiki/HE3uw7G5hiyjm4kLbYmcdFo1nsf |
| 0006 数据模型与界面重构设计 v1.5 | `0006_数据模型与界面重构设计.md` | https://feishu.cn/wiki/OMwUwjCDAi0QOyk6gINcDZVUnlc |
| 实施过程（5 阶段 12 个 doc） | `_requirements/data-model-redesign/` | 见上一条飞书链接清单 |

### 文档分层说明

- **0001-0006**（设计文档）：项目"怎么实现"的规范
- **README.md**（使用文档）：项目"怎么用"的入口 ← **本文件**
- **_requirements/**（过程记录）：需求实施的过程文档（5 阶段 12 个 doc）

---

## 🔧 维护 / 故障排查

### uvicorn 启动失败

| 症状 | 排查 | 解法 |
|------|------|------|
| 端口 8000 占用 | `lsof -i :8000` | kill 旧进程（`kill -9 <pid>`） |
| DB 文件损坏 | `data/futures_akshare.db` | 恢复备份：`cp data/futures_akshare.db.bak-* data/futures_akshare.db` |
| FK 不生效 | init_db() 末尾未加 `PRAGMA foreign_keys = ON` | 改 init_db() + 重跑 |
| 启动 SIGKILL | OpenClaw 60s timeout | 改用 nohup 后台启动 + 后续 curl 验证 |
| 依赖未装 | ModuleNotFoundError | `pip install -r requirements.txt` |

### 端点 404

- **路径参数错**：`/session/{id}/` 而非 `/session/{id}` → 检查路径末尾的 `/`
- **DB 表没创建**：重跑 `init_db()`，确认 22 张表都建好
- **方法不支持**：GET/POST/PUT 混用 → 查 Swagger 文档

### 前端无法连接 API

- **CORS 错误**：API 默认允许所有源（如有限制需调整 `api/main.py`）
- **端口不对**：API 在 8000，前端在 8080（默认配置可改）
- **健康检查失败**：先 `curl http://localhost:8000/health` 验证 API 在线

### 飞书同步失败

- **必查** `feishu_wiki spaces` + `nodes` 列父节点 → 确认父子关系正确
- **400 错误**多为 rate limit — 间隔 3-5 秒重试
- **大文档（>200 块）**优先 `feishu_doc write` 一次写，不调 lark SDK
- **同步策略**：详见 `~/.openclaw/plugin-skills/feishu-doc/SKILL.md` 的 "Write Strategy by Document Size" 章节

### 性能调优

- **回测慢**：检查 `backtest_engine.py` 是否走索引（lookback 期间用 `quotes_daily_idx`）
- **API 慢**：检查 `lines` / `events` 表的索引是否生效
- **前端卡**：浏览器 DevTools → Network → 看哪个端点慢

---

## 📦 依赖

### 运行时

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | >= 0.100.0 | Web 框架 |
| uvicorn[standard] | >= 0.23.0 | ASGI 服务器 |
| pandas | >= 2.0.0 | 数据处理 |
| numpy | >= 1.24.0 | 数值计算 |
| akshare | >= 1.12.0 | 期货数据源 |
| baostock | >= 0.8.8 | 股票辅助数据 |
| pydantic | >= 2.0.0 | 数据校验 |
| matplotlib | >= 3.7.0 | 图表（回测） |
| seaborn | >= 0.12.0 | 可视化（回测） |
| jupyter | >= 1.0.0 | Notebook（研究） |

### 测试

| 包 | 版本 | 用途 |
|----|------|------|
| pytest | 9.0.3 | 测试框架 |
| pytest-cov | 7.1.0 | 覆盖率 |
| locust | 2.44.0 | 压测 |

---

## 🗂️ 项目结构

```
stock-quant/
├── api/                    # API 层（FastAPI，sq-0008 拆分后）
│   ├── main.py            # 入口（80 行 / 9 router 注册 + 根 2 端点）
│   ├── state.py           # 全局状态（cached_prices / position_manager）
│   ├── routers/           # 9 域 1599 行（session/strategy/market/...）
│   ├── schemas/           # 8 文件 561 行 Pydantic 类
│   ├── helpers/           # 4 文件（backtest_runner/signal_calc/pnl/factor）
│   ├── services/          # 业务层（sim_engine/session_lifecycle/line_calculator/event_logger）
│   └── main.py.bak.*      # 备份（pre-p4 / sq-0008-final）
├── data/                   # 数据层（SQLite + akshare）
│   ├── data_loader.py     # DB 初始化 + 22 张表
│   └── futures_akshare.db # SQLite 数据库
├── strategies/             # 策略层
│   ├── base.py            # 策略基类
│   ├── loader.py          # 策略加载器
│   ├── executor.py        # 订单执行器
│   ├── trade_process_logger.py  # 海龟交易过程
│   └── turtle/            # 海龟策略
│       ├── factors.py
│       ├── position.py
│       └── V1/            # 海龟 V1 实现
├── www/                    # 前端层
│   └── index.html         # 单文件前端（2119 行）
├── tests/                  # 测试
│   ├── test_sim_engine.py
│   ├── test_strategy_loader.py
│   ├── test_session_lifecycle.py
│   ├── test_line_calculator.py
│   ├── test_event_logger.py
│   ├── test_trade_process_logger.py
│   ├── test_multi_account.py
│   ├── test_integration.py
│   └── locustfile.py      # 压测脚本
├── backtest/               # 回测引擎
│   └── backtest_engine.py
├── config/                 # 配置文件
├── notebooks/              # 研究 Notebooks
├── _requirements/          # 需求过程文档
│   └── data-model-redesign/  # 5 阶段 12 doc
├── 0001_项目设计.md        # 设计文档
├── 0002_技术设计.md
├── 0003_变更日志.md
├── 0004_数据源设计.md
├── 0005_海龟信号监控设计.md
├── 0006_数据模型与界面重构设计.md  # v1.5
├── PROJECT.md              # 项目总览
├── README.md               # 本文件（项目使用入口）
├── requirements.txt        # 依赖清单
└── pytest.ini              # pytest 配置
```

---

## 📊 关键指标（v1.5 完工态）

| 维度 | 指标 |
|------|------|
| 数据 | 22 张表 / 5 FK / 7 索引 |
| API | 46 端点（9 router / 44 + 根 2，sq-0008 拆分后）|
| 策略 | 海龟 V1 + 通用基类 |
| 前端 | 2119 行（4 模态 + 8 卡片 + 4 Unit + 调价线） |
| 测试 | 82 用例 / 53% 覆盖 / 5 服务层 71.6% 平均 |
| 性能 | 100 session 0.84s / 20.52 RPS / 0 失败 |
| 文档 | 6 大核心 + 5 阶段过程 + README.md（本文件） |
| 飞书 | 18 节点结构正确 |
| Cron | 2 个（push_news 09:25 / change-scan 30min） |

---

## 🆚 设计文档 vs 使用文档

| 类别 | 文件 | 内容 | 受众 |
|------|------|------|------|
| **设计文档** | 0001-0006 | "怎么做"（架构 / 表结构 / 算法） | 开发者 |
| **使用文档** | README.md（本文件） | "怎么用"（启动 / 入口 / 故障排查） | 用户 / 新成员 |
| **过程文档** | _requirements/ | 实施过程（5 阶段 12 doc） | 复盘 / 审计 |

**README.md 不带 4 位序号**——序号用于设计文档，README 是"项目使用说明"。

---

## 📜 License

Internal use only（v1.5 阶段）

---

> **维护者**：Alex Yuan  
> **最后更新**：2026-06-04 v1.6.1（README 同步 sq-0008 后端拆分）  
> **反馈**：发现文档错误或缺失 → 直接更新本文档
