<template>
  <section class="page-stack evaluation-page">
    <div class="page-heading split">
      <div>
        <span class="kicker">康复评估</span>
        <h1>训练变化看得见</h1>
        <p>这里汇总单次训练的过程性指标，并对比阶段性 WAB、CADL 与接受度评估。</p>
      </div>
      <RouterLink class="primary-link" to="/training">继续训练</RouterLink>
    </div>

    <section class="evaluation-summary">
      <div v-for="metric in latestMetricCards" :key="metric.key" class="metric-card">
        <span>{{ metric.value }}</span>
        <p>{{ metric.label }}</p>
      </div>
    </section>

    <p v-if="loading" class="success-text">正在加载康复评估数据。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section class="evaluation-grid">
      <article class="chart-panel">
        <div class="panel-heading">
          <div>
            <h2>过程性指标趋势</h2>
            <p>最近 {{ trend.items.length }} 次训练</p>
          </div>
        </div>
        <div v-if="trend.items.length" ref="trendChartEl" class="chart-box"></div>
        <div v-else class="empty-state">
          <p>完成一次训练并生成反馈后，这里会显示脚本正确率、错误次数、语速和响度趋势。</p>
          <RouterLink to="/training">开始训练</RouterLink>
        </div>
      </article>

      <article class="chart-panel">
        <div class="panel-heading">
          <div>
            <h2>阶段性效果对比</h2>
            <p>{{ compareLabel }}</p>
          </div>
        </div>
        <div v-if="hasAssessmentCompare" ref="radarChartEl" class="chart-box"></div>
        <div v-else class="empty-state">
          <p>录入 baseline 和训练后评估后，这里会显示 WAB、CADL 与接受度对比。</p>
          <RouterLink to="/report">查看康复记录</RouterLink>
        </div>
      </article>
    </section>

    <section class="comparison-panel">
      <div class="panel-heading">
        <div>
          <h2>训练前 vs 当前</h2>
          <p>差值为当前评估减去 baseline 评估。</p>
        </div>
      </div>
      <div v-if="hasAssessmentCompare" class="comparison-table">
        <div class="comparison-row comparison-head">
          <span>指标</span>
          <span>训练前</span>
          <span>当前</span>
          <span>变化</span>
        </div>
        <div v-for="row in comparisonRows" :key="row.key" class="comparison-row">
          <span>{{ row.label }}</span>
          <span>{{ row.baseline }}</span>
          <span>{{ row.current }}</span>
          <span :class="{ 'positive-change': Number(row.change) > 0 }">{{ row.change }}</span>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>阶段性评估数据不足，暂时无法生成训练前后对比。</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { assessmentApi } from '@/api/assessment'
import { evaluationsApi } from '@/api/evaluations'
import type { AssessmentCompare, ProcessMetrics, ProcessTrend } from '@/types/api'

const trend = ref<ProcessTrend>({ items: [] })
const compare = ref<AssessmentCompare | null>(null)
const loading = ref(true)
const error = ref('')
const trendChartEl = ref<HTMLElement | null>(null)
const radarChartEl = ref<HTMLElement | null>(null)
let trendChart: ECharts | null = null
let radarChart: ECharts | null = null

use([LineChart, RadarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const metricLabels: Record<keyof ProcessMetrics, string> = {
  script_accuracy: '脚本正确率',
  error_count: '错误次数',
  speech_rate: '字/min',
  loudness: 'dBA'
}

const assessmentLabels: Record<string, string> = {
  wab_information: '信息量',
  wab_fluency: '流利性',
  wab_grammar: '语法',
  wab_word_order: '语序',
  wab_comprehensibility: '可懂度',
  wab_repetition_comprehensibility: '复述可懂度',
  cadl_score: 'CADL',
  acceptance_score: '接受度'
}

const latestMetrics = computed(() => trend.value.items[trend.value.items.length - 1]?.metrics)

const latestMetricCards = computed(() => {
  const metrics = latestMetrics.value
  return (Object.keys(metricLabels) as Array<keyof ProcessMetrics>).map((key) => ({
    key,
    label: metricLabels[key],
    value: metrics ? formatNumber(metrics[key]) : '--'
  }))
})

const hasAssessmentCompare = computed(
  () => !!compare.value?.baseline_assessment && !!compare.value?.current_assessment
)

const compareLabel = computed(() => {
  if (!compare.value?.baseline_assessment || !compare.value.current_assessment) return '等待阶段性评估'
  return `${dateLabel(compare.value.baseline_assessment.assessed_at)} 到 ${dateLabel(compare.value.current_assessment.assessed_at)}`
})

const comparisonRows = computed(() => {
  if (!compare.value) return []
  return Object.entries(compare.value.metrics)
    .filter(([key]) => assessmentLabels[key])
    .map(([key, item]) => ({
      key,
      label: assessmentLabels[key],
      baseline: valueOrDash(item.baseline),
      current: valueOrDash(item.current),
      change: valueOrDash(item.change)
    }))
})

onMounted(async () => {
  try {
    const [trendData, compareData] = await Promise.all([
      evaluationsApi.processTrend(20),
      assessmentApi.compare()
    ])
    trend.value = trendData
    compare.value = compareData
    await nextTick()
    renderCharts()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '康复评估数据加载失败'
  } finally {
    loading.value = false
  }
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart?.dispose()
  radarChart?.dispose()
})

function renderCharts() {
  renderTrendChart()
  renderRadarChart()
}

function renderTrendChart() {
  if (!trendChartEl.value || !trend.value.items.length) return
  trendChart = init(trendChartEl.value)
  const labels = trend.value.items.map((item, index) => `第${index + 1}次`)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { top: 28, right: 18, bottom: 54, left: 42 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [
      lineSeries('脚本正确率', 'script_accuracy', '#2563eb'),
      lineSeries('错误次数', 'error_count', '#e86f51'),
      lineSeries('言语速率', 'speech_rate', '#2f9e73'),
      lineSeries('响度', 'loudness', '#7c3aed')
    ]
  })
}

function lineSeries(name: string, key: keyof ProcessMetrics, color: string) {
  return {
    name,
    type: 'line',
    smooth: true,
    symbolSize: 7,
    itemStyle: { color },
    data: trend.value.items.map((item) => item.metrics[key])
  }
}

function renderRadarChart() {
  if (!radarChartEl.value || !hasAssessmentCompare.value || !compare.value) return
  radarChart = init(radarChartEl.value)
  const rows = comparisonRows.value
  radarChart.setOption({
    tooltip: {},
    legend: { bottom: 0 },
    radar: {
      radius: '62%',
      indicator: rows.map((row) => ({
        name: row.label,
        max: radarMax(row.key)
      }))
    },
    series: [
      {
        type: 'radar',
        areaStyle: { opacity: 0.12 },
        data: [
          {
            value: rows.map((row) => Number(row.baseline) || 0),
            name: '训练前',
            itemStyle: { color: '#66756f' }
          },
          {
            value: rows.map((row) => Number(row.current) || 0),
            name: '当前',
            itemStyle: { color: '#2563eb' }
          }
        ]
      }
    ]
  })
}

function resizeCharts() {
  trendChart?.resize()
  radarChart?.resize()
}

function radarMax(key: string) {
  if (key === 'cadl_score') return 100
  if (key === 'acceptance_score') return 10
  return 10
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function valueOrDash(value: number | null) {
  return value === null ? '--' : formatNumber(value)
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>
