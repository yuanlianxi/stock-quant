# v1.7+sq-0009 — 缓存层优化（v1.7 迭代子条目）

> **归属**：本需求是 `0007-frontend-vue-migration` 验收阶段触发的 v1.7+ 迭代子条目，**不是**独立 `_requirements/`。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **关联规范**：`PROJECT_COLLAB_RULES.md §X`（_requirements 触发与结束）+ `PROJECT_ZONE.md §八.6`（生命周期阶段管理与结束条件）

## 状态汇总（4 阶段总览）

| 阶段 | 状态 | 进度 | 开始/完成时间 | 链接 |
|------|------|------|--------------|------|
| 1. 设计 | ✅ 完成 | 100% | 2026-06-07 / 2026-06-07 | [01-design/](01-design/README.md) |
| 2. 计划 | ⏳ 待开始 | 0% | - / - | [02-plan/](02-plan/README.md) |
| 3. 执行 | ⏳ 待开始 | 0% | - / - | [03-execution/](03-execution/README.md) |
| 4. 验收 | ⏳ 待开始 | 0% | - / - | [04-verification/](04-verification/README.md) |

## 主设计文档 SSOT

**不在本目录重复内容**（按 `PROJECT_ZONE.md §八.5` 主文档 SSOT 原则）：

- 主设计文档：`/home/yuan/.openclaw/workspace/projects/stock-quant/0009_缓存层优化设计.md`
- 包含 11 章：背景 / 7 决策 / 架构 / DB / 后端 / 前端 / SSOT / Phase / v2 / 配套变更 / 执行记录

## 范围摘要

- 调度器（APScheduler）：2 任务（daily_sync + minute_sync_5min）
- 后端：`api/cache_sync.py`（核心 SSOT，9 函数）+ `api/scheduler.py`（APScheduler 集成）
- 端点：+7 端点（market `/daily/sync` + cache 6 端点），总计 47 → 54
- 前端：`MarketDataSync.vue`（4 Tab）+ `cache.ts` store + 15/30/60min resample 降级
- 估时约 9 小时（7 Phase）

## 生命周期结束条件

满足任一即结束：
- `04-verification/feedback.md` 决策 = `closed`（验收通过 + 无后续）
- `04-verification/feedback.md` 决策 = `iterate: v1.7+`（验收通过 + 触发新迭代）→ 在本目录下建 `_iterations/v1.7+/<新需求名>/`
- 决策 = `blocked: <原因>`（阻塞暂停）

> 详见 `PROJECT_ZONE.md §八.6`。
