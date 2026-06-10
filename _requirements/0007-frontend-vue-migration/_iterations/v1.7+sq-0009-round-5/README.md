# v1.7+sq-0009-round-5 — K 线日线支持 + 混合展示

> **归属**：v1.7+sq-0009 的 round-5 迭代子条目（验收反馈触发）。
> 详见上级目录 `../README.md` 的「v1.X 迭代子条目」说明。
>
> **触发场景**：用户实测发现
> 1. 行情 K 线只支持分时周期（5/15/30/60min），无 daily 选项
> 2. 查询时间范围 >10 天时（akshare 5min 窗口外），缺数据没法看

## 状态汇总（2 commit 计划）

| 阶段 | 状态 | 进度 | 备注 |
|------|------|------|------|
| commit 11: K 线加 daily 周期 | 🔄 进行中 | 0% | useKLineData + SymbolDetail + MarketDataSync |
| commit 12: 混合展示 | ⏳ 待开始 | 0% | 分时 + 日线自动补缺 |

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