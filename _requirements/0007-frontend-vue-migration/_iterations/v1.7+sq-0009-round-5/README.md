# v1.7+sq-0009-round-5 — K 线日线支持 + 混合展示

> **归属**：v1.7+sq-0009 的 round-5 迭代子条目（验收反馈触发）。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **触发场景**：用户实测发现
> 1. 行情 K 线只支持分时周期（5/15/30/60min），无 daily 选项
> 2. 查询时间范围 >10 天时（akshare 5min 窗口外），缺数据没法看

## 状态汇总（最终）

| 阶段 | 状态 | 进度 | 备注 |
|------|------|------|------|
| commit 11: K 线加 daily 周期 | ✅ 完成 | 100% | useKLineData + SymbolDetail + MarketDataSync |
| commit 12: 混合展示 | ✅ 完成 | 100% | 分时 + 日线自动补缺 |
| hotfix1-12: K 线日线渲染 / 维度对齐 / OHLC 还原 | ✅ 完成 | 100% | hotfix6 5min/daily 时间宽度 + hotfix8 OHLC 线性插值（后回滚）+ hotfix12 过滤 minute 已有的日期 |
| **最终验收** | ✅ **closed**（2026-06-14）| — | 用户浏览器实测：K 线 23:30 段不再"等高全红" → 验收通过 |

## 最终交付

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| ae31f3c | feat(webapp): K 线日线支持 + 混合展示（合并 commit 11/12） | webapp/src/composables/useKLineData.ts + SymbolDetail.vue + MarketDataSync.vue |
| 4791c45 | fix: mixDaily daily 拉取范围 bug | useKLineData.ts |
| 9d3f323 | fix: mixDaily 智能补缺 | useKLineData.ts |
| 6f4e85b | fix: 默认值让 mixDaily 触发 | useKLineData.ts |
| 53f4476 | fix: KLineChart 加 debug 显示 | KLineChart.vue |
| 914d110 | fix: K 线默认显示最近 200 根 | useKLineData.ts |
| fec100d | fix: daily 拆 30 根 5min 占 1 天宽度 | useKLineData.ts |
| cff80eb | fix: daily datetime UTC 时区错位 | useKLineData.ts |
| f6ddb8b | fix: daily 30 根 OHLC 线性插值（后回滚）| useKLineData.ts |
| 7f26876 | fix: 调整回 hotfix6 datetime + 保留 hotfix8 OHLC | useKLineData.ts |
| a1320c0 | fix: 撤销 hotfix8 OHLC 线性插值 | useKLineData.ts |
| 3027335 | fix: 回滚到 hotfix6 原始设计 | useKLineData.ts |
| **eeb163c** | **fix: daily 过滤 minute 已有的日期（hotfix12）** | **useKLineData.ts** |

## 2 拆 commit 范围

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| **commit 11** | useKLineData.ts 加 daily 类型 + fetchKLineData daily 分支<br>SymbolDetail.vue + MarketDataSync.vue 加 daily chip<br>isMinutePeriod 调整 → daily 时 daysOptions 全开 | 3 文件 |
| **commit 12** | fetchKLineData 加 mixDaily=true（默认 true）<br>period='5min' + days>10 自动拉日线补缺<br>日线 datetime=23:55:00 占更宽时间（chart 自然稀疏渲染）| 1 文件 |

## 关键决策

- **不拒绝** days > 10 的请求（让用户看到混合数据）
- **自动混合**：period='5min' 且 days > 10 → 自动拉日线补缺
- **日线占更宽时间**：daily bar datetime 用当天最后 5min 时段（23:55），chart 按真实时间比例渲染
- **不混合标识**：混合后用 source 标签告诉用户哪些是 5min 哪些是 daily

## 关联

- 主设计文档：`/home/yuan/.openclaw/workspace/projects/stock-quant/0009_缓存层优化设计.md`
- round-1：`../v1.7+sq-0009/README.md`
- round-2：`../v1.7+sq-0009-round-2/README.md`
- round-3：`../v1.7+sq-0009-round-3/README.md`
- round-4：`../v1.7+sq-0009-round-4/README.md`