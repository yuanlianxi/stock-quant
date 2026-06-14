# 0007 前端 Vue 模块化迁移 — 子任务规划

> 创建：2026-06-03 23:21
> 设计文档：`0007_前端模块化重构设计.md` v0.1.0（已批准）
> 状态：✅ v1.6 完工（D 联调 + E 切版 2026-06-14 完成）

## 子任务清单

| Phase | 子任务 ID | 内容 | 派发时间 | 状态 | 超时 |
|-------|-----------|------|---------|------|------|
| A | `sq-0007-a-scaffold` | 脚手架（Vite + Vue 3 + TS + Pinia） | 23:21 | ✅ 完成（2m13s） | 30 分钟 |
| B | `sq-0007-b-basics` | 基础能力（useApi/Toast/Modal/5 store/8 services） | 23:24 | ✅ 完成（2m） | 60 分钟 |
| C1 | `sq-0007-c1-views` | 11 个视图组件 | 6/3-6/8 | ✅ 完成（12 视图/组件） | 90 分钟 |
| C2 | `sq-0007-c2-modals` | 5 个手动交易模态框 + ActionModalHost | 6/8-6/10 | ✅ 完成（6 modals + ActionModalHost + AccountCenterModal） | 30 分钟 |
| D | `sq-0007-d-integrate` | 联调灰度（FastAPI 挂载 + 并行新旧版） | 6/14 | ✅ 完成（webapp dist + /legacy + SPA fallback） | 60 分钟 |
| E | `sq-0007-e-cutover` | 切换清理（旧版归档 + 飞书同步） | 6/14 | ✅ 完成（www/ → www_legacy_v1.5/，D 阶段联调通过） | 30 分钟 |

## 派发规范

1. **真改文件**（MEMORY 教训）：每个子任务 prompt 必须明确「必须修改 X 文件，验收点 Y」
2. **限时 25-30 分钟**：超时即放弃，不延长
3. **可粘贴代码块**：关键文件提供完整代码，子任务不允许"只描述不写"
4. **立即验收**：子任务返回后立刻按验收点核对，未达标派 v2
5. **变更日志即时**：每阶段完成后立即更新 0003_变更日志.md
6. **git commit 命名**：`v1.6-phase-A` / `v1.6-phase-B` / ... `/ v1.6-phase-E`

## 当前进度

- 2026-06-03 23:21：设计 v0.1.0 决策已批准，开始派 Phase A
- 2026-06-03 23:23：Phase A 完成（11 个文件 / 53 依赖 / dev 200 / 类型 0 错 / build 364ms）
- 2026-06-03 23:24：派发 Phase B（基础能力：composables + 5 store + 8 services + 3 基础组件）
- 2026-06-03 23:26：Phase B 完成（25 个文件 / vue-tsc 0 错 / signals=33 / symbols=49）
- 2026-06-03 23:27：派发 Phase C1（11 个 view 视图组件）
- 2026-06-08 ~ 06-10：C1（12 视图/组件）+ C2（6 modals + ActionModalHost + AccountCenterModal）实质完成
- 2026-06-14：D 联调（`api/main.py` 挂载 webapp dist + /legacy + SPA fallback）+ E 切版（`www/index.html` 删 / `www_legacy_v1.5/` 归档）完工
- 2026-06-14：6 项 curl 验证全过（`/` / `/legacy/` / `/health` / `/symbol-detail` SPA / `/docs` / `/assets/xxx.js`）

---

## v1.X 迭代子条目（验收阶段发现/触发的衍生需求）

> ⚠️ **归属说明**（2026-06-07 复盘补）：以下需求是 0007 验收阶段发现/触发的衍生需求，
> **应作为本需求（0007）的 v1.X+ 迭代子条目**，**不是**独立 `_requirements/`。
>
> **根因**：0007 还没正式验收结束（`04-verification/feedback.md` 决策 = `iterate: v1.7+`），
> 根据 `PROJECT_COLLAB_RULES.md §X.3` 跨需求归属规则，未结束的需求**禁止**派生独立 `_requirements/`。
>
> **后续动作**：等 0007 正式验收结束后（feedback.md 决策 = `iterate: v1.7+`），
> 这些条目会作为本目录的 `_iterations/v1.7/` 子目录（具体结构见 `PROJECT_ZONE.md §八.2`）。

| 迭代 ID | 触发日期 | 标题 | 状态 | 详情 |
|---------|---------|------|------|------|
| `v1.7+sq-0008` | 2026-06-04 | 后端 API 模块化拆分（main.py 1848→80 行）| ✅ 已完工 | commit `877fb05` / 7 子任务 / 65 分钟 / 82 pytest 全过 |
| `v1.7+sq-0009` | 2026-06-07 | 缓存层优化（调度 + 记录 + 手动拉取 + 页面）| ✅ **已完工 closed**（2026-06-14）| 5 轮迭代 + 12 hotfix / 18 commits / round-5 K 线日线验收通过 |

