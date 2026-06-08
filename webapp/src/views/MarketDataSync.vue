<!--
  MarketDataSync.vue（sq-0009-p6 + v1.7+sq-0009-round-2 commit 1）
  5 Tab:
    1. 覆盖率（38 品种 × 5 周期矩阵）
    2. 拉取记录（分页 + 过滤）
    3. 手动拉取（选品种 + period + 触发）
    4. 调度状态（2 任务卡片 + 启停）
    5. K 线图（lightweight-charts 渲染）
-->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useCacheStore } from '@/stores/cache'
import { ALL_SYMBOLS } from '@/config/symbols'
import { useToast } from '@/composables/useToast'
import { useKLineData, type KLinePeriod, type KLineSource } from '@/composables/useKLineData'
import KLineChart from '@/components/KLineChart.vue'
import { marketApi } from '@/services/market'
import { cacheApi } from '@/services/cache'

const store = useCacheStore()
const toast = useToast()
const kline = useKLineData()

// Tab 切换
const activeTab = ref<'coverage' | 'logs' | 'manual' | 'schedule' | 'kline'>('coverage')

// 手动拉取表单（commit 2 增强）
const manualSymbol = ref<string>('AG')
const manualPeriod = ref<'daily' | '5min' | '15min' | '30min' | '60min'>('daily')
const manualSyncType = ref<'incremental' | 'backfill'>('incremental')
const manualStartDate = ref<string>(new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10))
const manualEndDate = ref<string>(new Date().toISOString().slice(0, 10))
// 计算回填天数
const backfillDays = computed(() => {
  if (!manualStartDate.value || !manualEndDate.value) return 0
  const a = new Date(manualStartDate.value).getTime()
  const b = new Date(manualEndDate.value).getTime()
  return Math.max(0, Math.floor((b - a) / 86400_000) + 1)
})

// K 线图表单（Tab 5）
const klineSymbol = ref<string>('AG')
const klinePeriod = ref<KLinePeriod>('15min')
const klineDays = ref<number>(7)

// 记录过滤
const filterSymbol = ref<string>('')
const filterType = ref<string>('')
const filterStatus = ref<string>('')

// 颜色映射
function statusColor(s: 'fresh' | 'stale' | 'missing'): string {
  if (s === 'fresh') return '#22c55e'    // 绿
  if (s === 'stale') return '#eab308'    // 黄
  return '#ef4444'                        // 红
}

function statusLabel(s: 'fresh' | 'stale' | 'missing'): string {
  if (s === 'fresh') return '●'
  if (s === 'stale') return '◐'
  return '○'
}

// 初始化
onMounted(async () => {
  await store.fetchCoverage()
  await store.fetchSyncLogs()
  await store.fetchSchedule()
})

// 切换记录 Tab 时刷新
async function refreshLogs() {
  store.setSyncLogsFilter({
    symbol: filterSymbol.value || undefined,
    sync_type: filterType.value || undefined,
    status: filterStatus.value || undefined,
  })
  await store.fetchSyncLogs(1)
}

// 切换分页
async function changePage(p: number) {
  await store.fetchSyncLogs(p)
}

// 手动拉取（commit 2 增强：全品种 + 时间范围 + sync_type）
async function doTrigger() {
  try {
    if (manualSyncType.value === 'incremental') {
      // 增量：调 /daily/sync 或 /minute/sync
      const sym = manualSymbol.value === 'ALL' ? 'all' : manualSymbol.value
      if (manualPeriod.value === 'daily') {
        await marketApi.dailySync(sym)
        toast.push({ kind: 'success', title: '✅ 日线同步触发', body: `${manualSymbol.value}` })
      } else {
        await marketApi.minuteSync({ symbol: sym, period: manualPeriod.value })
        toast.push({ kind: 'success', title: '✅ 分时同步触发', body: `${manualSymbol.value} ${manualPeriod.value}` })
      }
    } else {
      // 回填：调 /cache/backfill
      const days = backfillDays.value || 7
      const r: any = await cacheApi.backfill(manualSymbol.value, manualPeriod.value, undefined, days)
      toast.push({ kind: 'success', title: '✅ 回填完成', body: `${manualSymbol.value} ${manualPeriod.value}: 新增 ${r.rows_new ?? 0} 行 (${days} 天)` })
    }
    await store.fetchSyncLogs(1)
    await store.fetchCoverage()
  } catch (e: any) {
    toast.push({ kind: 'error', title: '拉取失败', body: String(e) })
  }
}

// 调度启停
async function doToggle(taskName: string, enabled: boolean) {
  try {
    await store.toggleScheduleTask(taskName, enabled)
    toast.push({
      kind: 'success',
      title: enabled ? '✅ 已启用' : '⏸ 已停用',
      body: taskName,
    })
  } catch (e: any) {
    toast.push({ kind: 'error', title: '切换失败', body: String(e) })
  }
}

// 总览
const summary = computed(() => store.coverage?.summary)

// ===== Tab 5: K 线图 =====

// 数据源标签映射
const sourceLabel = computed<KLineSource | null>(() => kline.source.value)
const sourceBadge = computed(() => {
  if (kline.source.value === 'cache') return { text: '🟢 缓存', color: '#22c55e' }
  if (kline.source.value === 'resample') return { text: '🟡 Resample (5min→目标)', color: '#eab308' }
  if (kline.source.value === 'empty') return { text: '⚪ 空', color: '#9ca3af' }
  return null
})

// 查询 K 线
async function queryKLine() {
  await kline.fetchKLineData(klineSymbol.value, klinePeriod.value, klineDays.value)
}
</script>

<template>
  <div class="sync-center">
    <header class="sync-header">
      <h2>📊 行情数据同步中心</h2>
      <span class="subtitle" v-if="summary">
        {{ summary.total_symbols }} 品种 × 5 周期 = {{ summary.total_cells }} cells
        ｜ 🟢 {{ summary.fresh_cells }} 🟡 {{ summary.stale_cells }} 🔴 {{ summary.missing_cells }}
      </span>
    </header>

    <nav class="tab-bar">
      <button :class="{ active: activeTab === 'coverage' }" @click="activeTab = 'coverage'">1. 覆盖率</button>
      <button :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'">2. 拉取记录</button>
      <button :class="{ active: activeTab === 'manual' }" @click="activeTab = 'manual'">3. 手动拉取</button>
      <button :class="{ active: activeTab === 'schedule' }" @click="activeTab = 'schedule'">4. 调度状态</button>
      <button :class="{ active: activeTab === 'kline' }" @click="activeTab = 'kline'">5. K 线图</button>
    </nav>

    <!-- Tab 1: 覆盖率 -->
    <section v-if="activeTab === 'coverage'" class="tab-panel">
      <div v-if="store.coverageLoading" class="loading">加载中...</div>
      <div v-else-if="store.coverageError" class="error">❌ {{ store.coverageError }}</div>
      <div v-else-if="store.coverage" class="coverage-grid">
        <table>
          <thead>
            <tr>
              <th>品种</th>
              <th v-for="p in store.coverage.periods" :key="p">{{ p }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sym in store.coverage.symbols" :key="sym">
              <td class="sym-cell">{{ sym }}</td>
              <td v-for="p in store.coverage.periods" :key="p"
                  :style="{ background: statusColor(store.coverage.matrix[sym][p].status), color: '#fff', textAlign: 'center' }"
                  :title="store.coverage.matrix[sym][p].latest || '无'">
                {{ statusLabel(store.coverage.matrix[sym][p].status) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Tab 2: 拉取记录 -->
    <section v-if="activeTab === 'logs'" class="tab-panel">
      <div class="filter-bar">
        <label>品种 <input v-model="filterSymbol" placeholder="AG" /></label>
        <label>类型
          <select v-model="filterType">
            <option value="">全部</option>
            <option value="manual">manual</option>
            <option value="backfill">backfill</option>
            <option value="scheduled">scheduled</option>
          </select>
        </label>
        <label>状态
          <select v-model="filterStatus">
            <option value="">全部</option>
            <option value="success">success</option>
            <option value="failed">failed</option>
            <option value="partial">partial</option>
            <option value="running">running</option>
          </select>
        </label>
        <button @click="refreshLogs" :disabled="store.syncLogsLoading">查询</button>
      </div>
      <div v-if="store.syncLogsLoading" class="loading">加载中...</div>
      <table v-else-if="store.syncLogs.length > 0">
        <thead>
          <tr>
            <th>ID</th><th>品种</th><th>周期</th><th>类型</th><th>状态</th>
            <th>新增/总</th><th>开始</th><th>触发源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in store.syncLogs" :key="log.id">
            <td>{{ log.id }}</td>
            <td>{{ log.symbol }}</td>
            <td>{{ log.period }}</td>
            <td>{{ log.sync_type }}</td>
            <td :class="'status-' + log.status">{{ log.status }}</td>
            <td>{{ log.rows_new }} / {{ log.rows_total }}</td>
            <td class="ts">{{ log.start_at }}</td>
            <td class="ts">{{ log.trigger_source }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">暂无记录</div>
      <div class="pager" v-if="store.syncLogsTotal > 20">
        <button :disabled="store.syncLogsPage <= 1" @click="changePage(store.syncLogsPage - 1)">← 上一页</button>
        <span>第 {{ store.syncLogsPage }} 页 / 共 {{ Math.ceil(store.syncLogsTotal / 20) }} 页（{{ store.syncLogsTotal }} 条）</span>
        <button :disabled="store.syncLogsPage >= Math.ceil(store.syncLogsTotal / 20)"
                @click="changePage(store.syncLogsPage + 1)">下一页 →</button>
      </div>
    </section>

    <!-- Tab 3: 手动拉取（v1.7+sq-0009-round-2 commit 2 增强）-->
    <section v-if="activeTab === 'manual'" class="tab-panel">
      <div class="form">
        <label>品种
          <select v-model="manualSymbol">
            <option value="ALL">📦 全部 ({{ ALL_SYMBOLS.length }} 品种)</option>
            <option v-for="s in ALL_SYMBOLS" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>周期
          <select v-model="manualPeriod">
            <option value="daily">daily（日线）</option>
            <option value="5min">5min</option>
            <option value="15min">15min</option>
            <option value="30min">30min</option>
            <option value="60min">60min</option>
          </select>
        </label>
        <label>同步类型
          <select v-model="manualSyncType">
            <option value="incremental">增量（最新数据）</option>
            <option value="backfill">回填（按时间范围）</option>
          </select>
        </label>
        <template v-if="manualSyncType === 'backfill'">
          <label>开始日期
            <input type="date" v-model="manualStartDate" />
          </label>
          <label>结束日期
            <input type="date" v-model="manualEndDate" />
          </label>
          <span class="hint">回填范围 [{{ manualStartDate || '?' }}, {{ manualEndDate || '?' }}] ({{ backfillDays }} 天)</span>
        </template>
        <button @click="doTrigger" :disabled="store.triggerLoading">
          {{ store.triggerLoading ? '拉取中...' : '立即拉取' }}
        </button>
      </div>
      <div v-if="store.lastTriggerResult" class="result">
        <h4>最近一次拉取结果：</h4>
        <pre>{{ JSON.stringify(store.lastTriggerResult, null, 2) }}</pre>
      </div>
    </section>

    <!-- Tab 4: 调度状态 -->
    <section v-if="activeTab === 'schedule'" class="tab-panel">
      <div v-if="store.scheduleLoading" class="loading">加载中...</div>
      <div class="schedule-grid" v-else>
        <div v-for="s in store.schedule" :key="s.task_name" class="schedule-card">
          <h3>{{ s.task_name }}</h3>
          <div class="info">
            <div><span>上次：</span>{{ s.last_run_at || '—' }}</div>
            <div><span>下次：</span>{{ s.next_run_at || '—' }}</div>
            <div><span>状态：</span>{{ s.last_status || '—' }}</div>
            <div><span>累计：</span>成功 {{ s.run_count }} / 失败 {{ s.fail_count }}</div>
          </div>
          <button @click="doToggle(s.task_name, !s.enabled)"
                  :class="s.enabled ? 'btn-stop' : 'btn-start'">
            {{ s.enabled ? '⏸ 停用' : '▶ 启用' }}
          </button>
        </div>
      </div>
    </section>

    <!-- Tab 5: K 线图（v1.7+sq-0009-round-2 commit 1）-->
    <section v-if="activeTab === 'kline'" class="tab-panel">
      <div class="kline-toolbar">
        <label>品种
          <select v-model="klineSymbol">
            <option v-for="s in ALL_SYMBOLS" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>周期
          <select v-model="klinePeriod">
            <option value="5min">5min</option>
            <option value="15min">15min</option>
            <option value="30min">30min</option>
            <option value="60min">60min</option>
          </select>
        </label>
        <label>天数
          <input type="number" v-model.number="klineDays" min="1" max="180" style="width: 70px" />
        </label>
        <button @click="queryKLine" :disabled="kline.loading.value">
          {{ kline.loading.value ? '查询中...' : '查询 K 线' }}
        </button>
        <span v-if="sourceBadge" class="source-badge" :style="{ color: sourceBadge.color }">
          数据源：{{ sourceBadge.text }}（{{ kline.data.value.length }} 条）
        </span>
        <span v-if="kline.error.value" class="error" style="margin-left: 12px">
          ❌ {{ kline.error.value }}
        </span>
      </div>
      <KLineChart :data="kline.data.value" :height="500" />
    </section>
  </div>
</template>

<style scoped>
.sync-center { padding: 16px; }
.sync-header { display: flex; align-items: baseline; gap: 16px; margin-bottom: 12px; }
.sync-header h2 { margin: 0; font-size: 18px; color: var(--accent); }
.subtitle { color: var(--muted); font-size: 12px; }
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--border); }
.tab-bar button { background: transparent; border: none; padding: 8px 16px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; }
.tab-bar button.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-panel { min-height: 400px; }
.coverage-grid table { width: 100%; border-collapse: collapse; font-size: 12px; }
.coverage-grid th, .coverage-grid td { padding: 4px 6px; border: 1px solid var(--border); }
.coverage-grid .sym-cell { font-weight: bold; }
.filter-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.filter-bar label { display: flex; gap: 4px; align-items: center; font-size: 12px; }
.filter-bar input, .filter-bar select { padding: 4px 8px; }
.filter-bar button { padding: 4px 12px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { padding: 6px 8px; border: 1px solid var(--border); text-align: left; }
th { background: var(--card); }
.status-success { color: #22c55e; }
.status-failed { color: #ef4444; }
.status-partial { color: #eab308; }
.status-running { color: #3b82f6; }
.ts { font-family: monospace; font-size: 11px; }
.pager { display: flex; gap: 12px; align-items: center; margin-top: 12px; justify-content: center; }
.pager button { padding: 4px 12px; }
.pager button:disabled { opacity: 0.5; }
.empty, .loading, .error { padding: 24px; text-align: center; color: var(--muted); }
.error { color: #ef4444; }
.form { display: flex; gap: 16px; align-items: center; padding: 16px; }
.form label { display: flex; gap: 4px; align-items: center; }
.form select, .form input { padding: 6px 10px; }
.form button { padding: 6px 20px; background: var(--accent); color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.form button:disabled { opacity: 0.5; }
.result { margin-top: 16px; padding: 12px; background: var(--card); border-radius: 4px; }
.result pre { font-size: 12px; overflow-x: auto; }
.schedule-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.schedule-card { background: var(--card); padding: 16px; border-radius: 6px; border: 1px solid var(--border); }
.schedule-card h3 { margin: 0 0 12px 0; color: var(--accent); }
.info { font-size: 12px; line-height: 1.8; }
.info span { color: var(--muted); display: inline-block; min-width: 50px; }
.btn-start, .btn-stop { padding: 6px 16px; border: none; border-radius: 4px; cursor: pointer; color: #fff; margin-top: 12px; }
.btn-start { background: #22c55e; }
.btn-stop { background: #eab308; }
.kline-toolbar { display: flex; gap: 16px; align-items: center; padding: 12px 0; flex-wrap: wrap; }
.kline-toolbar label { display: flex; gap: 4px; align-items: center; font-size: 13px; }
.kline-toolbar select, .kline-toolbar input { padding: 4px 8px; }
.kline-toolbar button { padding: 6px 16px; background: var(--accent); color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.kline-toolbar button:disabled { opacity: 0.5; }
.source-badge { font-size: 12px; padding: 4px 10px; background: var(--card); border-radius: 4px; border: 1px solid var(--border); }
</style>
