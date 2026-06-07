# 02 计划阶段 — v1.7+sq-0009

> **状态**：✅ 完成（2026-06-07，用户授权直接进入自动执行）
>
> 计划内容：见根目录 `0009_缓存层优化设计.md` §八 Phase 拆分表 + 02-plan/README.md 摘要。
> 按用户选择 A（**现状即可**），不补独立 `plan.md`，README 摘要即为计划。

## 进入条件（checkbox）

- [x] 设计阶段已完成（01-design/README.md 状态 = ✅）
- [x] 主设计文档已审核通过（用户口头"可以"）
- [ ] `plan.md` 编写（Phase 拆分 + 时间线 + 风险）

## 待产出物（清单）

- [ ] `plan.md`（必含：Phase 拆分 + 时间线 + 风险 + 资源）

## Phase 拆分（从 0009_缓存层优化设计.md §八 抽取）

| Phase | 内容 | 估时 | 依赖 |
|-------|------|------|------|
| P1 | DB 迁移 2 表 | 30 min | — |
| P2 | api/cache_sync.py 核心 | 1.5 h | P1 |
| P3 | POST /daily/sync | 20 min | P2 |
| P4 | cache.py 6 端点 | 1 h | P2 |
| P5 | api/scheduler.py | 1.5 h | P2 |
| P6 | 前端 MarketDataSync.vue | 2.5 h | P4 |
| P7 | pytest + 冒烟 + commit | 1.5 h | P1-P6 |

**总计约 9 小时**。

## 时间线（草案）

- P1-P2 后端基础：~2 h
- P3-P4 端点扩展：~1.5 h
- P5 调度器：~1.5 h
- P6 前端（与 P3-P5 并行）：~2.5 h
- P7 验收：~1.5 h

## 风险

- APScheduler 进程内调度，**重启后内存 JobStore 丢失**——v1 接受，重启后从 `cache_schedule_state` 表读 `last_run_at` 重算
- akshare 限流风险——5min 任务每 5 分钟 38 品种 = 456 次/小时，理论安全
- 交易日历未过滤（v1 不做，cron `1-5` 自然跳过周末）

## 结束条件（→ 03 执行）

计划阶段结束 = `plan.md` 审核通过。
