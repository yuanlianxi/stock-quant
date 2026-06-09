# v1.7+sq-0009-round-4 — 拉取记录时区隔与范围透传

> **归属**：v1.7+sq-0009 的 round-4 迭代子条目（验收反馈触发）。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **触发场景**：用户实测发现
> 1. 拉取 0/0 条时不知道为什么（缓存已最新，但用户看不到原因）
> 2. 拉取记录没记"开始/结束时间"——`end_at` 已记但前端没显示
> 3. 拉取记录没记"用户选择的时间范围"——`start_date/end_date` 字段不存在
> 4. rows_existing/rows_new/rows_total 没区分（只看了 rows_new 一栏）

## 状态汇总（2 commit 计划）

| 阶段 | 状态 | 进度 | 备注 |
|------|------|------|------|
| commit 9: 拓字段 + 透传 | 🔄 进行中 | 0% | 7 处改动 |
| commit 10: 展示增强 | ⏳ 待开始 | 0% | 1 处前端 |

## 2 拆 commit 范围

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| **commit 9** | cache_sync_log 表加 start_date/end_date 字段<br>_log_start 加可选参数<br>cache_sync.backfill_daily/minute 接 start_date/end_date<br>cache.py /cache/backfill 端点接 query params<br>Pydantic schema 加字段<br>services/cache.ts backfill 方法传参数<br>MarketDataSync.vue Tab 3 doTrigger 传 start_date/end_date | 7 文件 |
| **commit 10** | MarketDataSync.vue Tab 2 加"开始/结束时间"列<br>加"时间范围"列（start_date ~ end_date）<br>展示 rows_existing/rows_new/rows_total 三栏 | 1 文件 |

## 关键决策

- **不修改 data_loader 行为**（避免大改动）：start_date/end_date **只记录不执行**
- 拉 0/0 条 = 缓存已最新，是正常的，不算 bug
- 前端补展示后用户能自己判断"为什么 0 条"

## 关联

- 主设计文档：`/home/yuan/.openclaw/workspace/projects/stock-quant/0009_缓存层优化设计.md`
- v1.7+sq-0009 round-1：`../v1.7+sq-0009/README.md`
- v1.7+sq-0009 round-2：`../v1.7+sq-0009-round-2/README.md`
- v1.7+sq-0009 round-3：`../v1.7+sq-0009-round-3/README.md`
