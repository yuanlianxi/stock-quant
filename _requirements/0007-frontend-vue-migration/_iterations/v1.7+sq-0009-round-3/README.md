# v1.7+sq-0009-round-3 — 分时数据窗口与范围控制

> **归属**：v1.7+sq-0009 的 round-3 迭代子条目（验收反馈触发的衍生需求）。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **触发场景**：用户实测发现
> 1. "半年 5min 拉不到" —— akshare 数据源 5/15/30/60min 仅返回最近 5-10 天
> 2. K 线需要范围选择器（7天/30天/半年/1年/2年/3年）+ 不同周期最长范围不同

## 状态汇总（3 commit 计划）

| 阶段 | 状态 | 进度 | 备注 |
|------|------|------|------|
| commit 5: source_window 提示 | 🔄 进行中 | 0% | 后端字段 + 前端展示 |
| commit 6: 范围选择器 + 联动约束 | ⏳ 待开始 | 0% | 2 处前端 + useKLineData 增强 |
| commit 7: 调度器加完整回填 | ⏳ 待开始 | 0% | 17:00 日线后追加 17:05 分时全回填 |

## 3 拆 commit 范围

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| **commit 5** | `source_window_days` 字段加 get_coverage 响应<br>前端 Tab 1 覆盖率表加列展示 | 3 文件 |
| **commit 6** | SymbolDetail.vue + MarketDataSync.vue Tab 5 加 days 下拉（7/30/180/365/730/1095）<br>period × days 联动（5/15/30/60min 禁用 >180 天）<br>useKLineData 增强支持 days 切换 | 3 文件 |
| **commit 7** | scheduler.py 加 `_run_minute_full_backfill` 函数<br>让 daily_sync 完成后追加触发 1 次完整 10 天分时回填 | 1 文件 |

## 关键决策

- **不拒绝** days > 14 的请求（让用户看到 0-N 条结果自己判断）
- **不限制**手动拉取（保留灵活性）
- **明确告知** UI 限制（分时周期禁用 >180 天选项）
- **自动兜底** daily_sync 17:00 后追加 17:05 完整回填

## 关联

- 主设计文档：`/home/yuan/.openclaw/workspace/projects/stock-quant/0009_缓存层优化设计.md`
- v1.7+sq-0009 round-1：`../v1.7+sq-0009/README.md`
- v1.7+sq-0009 round-2：`../v1.7+sq-0009-round-2/README.md`
