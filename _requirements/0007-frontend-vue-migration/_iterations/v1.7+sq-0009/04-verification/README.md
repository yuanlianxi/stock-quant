# 04 验收阶段 — v1.7+sq-0009

> **状态**：⏳ 待开始

## 进入条件（checkbox）

- [x] 设计阶段完成
- [x] 计划阶段完成
- [x] 执行阶段完成（P1-P7 全过）
- [ ] `feedback.md` 验收记录

## 待产出物（清单）

- [ ] `feedback.md`（功能/性能/UX 验收 + 决策 closed/iterate/blocked）

## 验收清单（占位）

### 功能验收

- [ ] 调度 2 任务按 cron 触发（手动验证 daily_sync 17:00 + minute_sync_5min 9-15/5min）
- [ ] `/cache/coverage` 返回 38 品种 × 5 周期矩阵
- [ ] `/cache/sync/logs` 拉取记录分页查询
- [ ] `POST /cache/sync/daily` 手动日线触发
- [ ] `POST /cache/sync/minute` 手动分时触发（5/15/30/60min 任一周期）
- [ ] `POST /cache/backfill` 回填历史
- [ ] `/cache/schedule` 调度状态
- [ ] `POST /cache/schedule/{task}/toggle` 启停调度
- [ ] 前端 `MarketDataSync.vue` 4 Tab 完整可用
- [ ] 15/30/60min 缓存降级：库有查库，无则 resample

### 性能验收

- [ ] pytest 82 全过 + 7 新端点冒烟全过
- [ ] daily_sync 38 品种完成时间 < 60s
- [ ] minute_sync_5min 38 品种完成时间 < 30s
- [ ] 端到端 11 端点回归 + 7 新端点 = 18 端点 200

### 用户体验验收

- [ ] 前端覆盖率矩阵绿/黄/红清晰
- [ ] 拉取记录表格可分页 + 过滤
- [ ] 手动拉取界面操作流畅
- [ ] 调度状态卡片展示清晰

## 结束条件（→ 生命周期结束）

`feedback.md` 末尾写明**决策**：

| 决策 | 含义 | 下一步 |
|------|------|--------|
| `closed` | 验收通过，无后续 | 归档到 `_requirements/_archive/v1.7+sq-0009/` |
| `iterate: v1.7+` | 触发新迭代 | 在本目录下建 `_iterations/v1.7+/<新需求名>/` |
| `blocked: <原因>` | 阻塞暂停 | 保持当前状态，等解除 |

> 详见 `PROJECT_COLLAB_RULES.md §X.2` + `PROJECT_ZONE.md §八.6`。
