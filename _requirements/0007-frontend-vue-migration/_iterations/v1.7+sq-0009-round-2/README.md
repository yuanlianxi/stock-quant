# v1.7+sq-0009-round-2 — 缓存中心前端增强（K 线图 + 同步范围）

> **归属**：v1.7+sq-0009 的 round-2 迭代子条目（验收反馈触发的衍生需求）。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **触发场景**：v1.7+sq-0009 完工后用户实测发现 3 个补全点
> 1. K 线展示缺失（SymbolDetail 占位注释未集成 lightweight-charts）
> 2. 分时数据类型入口缺失
> 3. 手动同步缺时间范围 + 全部品种选项

## 状态汇总（3 commit 计划）

| 阶段 | 状态 | 进度 | 开始/完成 | 链接 |
|------|------|------|----------|------|
| commit 1: K 线图 Tab | 🔄 进行中 | 0% | 2026-06-07 / - | 见下 |
| commit 2: 手动拉取增强 | ⏳ 待开始 | 0% | - / - | - |
| commit 3: 联动 + 验收 | ⏳ 待开始 | 0% | - / - | - |

## 3 拆 commit 范围

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| **commit 1** | K 线图 Tab（5th Tab）<br>• 新建 `components/KLineChart.vue`（lightweight-charts 实例化）<br>• MarketDataSync.vue 加 Tab 5<br>• 品种 + 周期 + 渲染 + 数据源标签 | 2 文件 |
| **commit 2** | 手动拉取增强（Tab 3）<br>• 品种加 "全部 (38 品种)"<br>• 加 start_date / end_date 输入框<br>• 加 sync_type 切换 (incremental / backfill) | 3 文件 |
| **commit 3** | 联动 + 验收 + 推送<br>• Tab 3 拉取成功 → 自动切到 Tab 5 刷新<br>• vue-tsc 0 错 + vite build 通过<br>• 14 端点 200 + pytest 90 全过<br>• commit + pushall（Gitee + GitHub）| 多文件 |

## SSOT 引用

- 主设计文档：`/home/yuan/.openclaw/workspace/projects/stock-quant/0009_缓存层优化设计.md`
- v1.7+sq-0009 round-1：`../v1.7+sq-0009/README.md`
- 协作规范：`PROJECT_ZONE.md §八.6` + `PROJECT_COLLAB_RULES.md §X`

## 关联后端（已就绪）

- `GET /minute/{symbol}?period=5min/15min/30min/60min&days=N` —— K 线数据源
- `GET /cache/coverage` —— 覆盖率（含 5 周期 status）
- `POST /cache/backfill?symbol=&period=&years=&days=` —— 回填（含时间范围）

## 结束条件

`commit 3 推送成功` → round-2 结束，**等用户验收后 v1.7+sq-0009 正式验收** →

按 `PROJECT_COLLAB_RULES.md §X.2`：

| 决策 | 动作 |
|------|------|
| `closed` | round-2 结束 + v1.7+sq-0009 验收通过 → 归档 `_requirements/_archive/v1.7+sq-0009/` |
| `iterate: v1.7+` | 触发 round-3（开 `_iterations/v1.7+sq-0009-round-3/`）|
| `blocked: <原因>` | 阻塞暂停 |
