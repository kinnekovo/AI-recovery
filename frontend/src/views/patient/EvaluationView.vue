<template>
  <section class="page-stack evaluation-page">
    <div class="page-heading split">
      <div>
        <span class="kicker">我的进步</span>
        <h1>看看最近练得怎么样</h1>
        <p>这里用简单的话记录每次训练后的变化，帮助你知道下一次怎么练。</p>
      </div>
      <RouterLink class="primary-link" to="/training">继续训练</RouterLink>
    </div>

    <p v-if="loading" class="success-text">正在加载训练变化。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section class="evaluation-summary">
      <div v-for="metric in latestMetricCards" :key="metric.key" class="metric-card patient-metric-card">
        <span>{{ metric.value }}</span>
        <p>{{ metric.label }}</p>
      </div>
    </section>

    <section class="chart-panel">
      <div class="panel-heading">
        <div>
          <h2>最近训练变化</h2>
          <p>{{ trend.items.length ? `已记录最近 ${trend.items.length} 次训练` : '完成训练后会自动记录' }}</p>
        </div>
      </div>
      <div v-if="trend.items.length" ref="trendChartEl" class="chart-box"></div>
      <div v-else class="empty-state">
        <p>完成一次训练并生成反馈后，这里会显示最近的练习变化。</p>
        <RouterLink to="/training">开始训练</RouterLink>
      </div>
    </section>

    <section class="comparison-panel">
      <div class="panel-heading">
        <div>
          <h2>下一次怎么练</h2>
          <p>建议来自最近的训练记录，只作为练习参考。</p>
        </div>
      </div>
      <div class="patient-advice">
        <strong>{{ adviceTitle }}</strong>
        <p>{{ adviceText }}</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { evaluationsApi } from '@/api/evaluations'
import type { ProcessMetrics, ProcessTrend } from '@/types/api'

const trend = ref<ProcessTrend>({ items: [] })
const loading = ref(true)
const error = ref('')
const trendChartEl = ref<HTMLElement | null>(null)
let trendChart: ECharts | null = null

use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const latestMetrics = computed(() => trend.value.items[trend.value.items.length - 1]?.metrics)

const latestMetricCards = computed(() => {
  const metrics = latestMetrics.value
  return [
    {
      key: 'expression',
      label: '表达完整度',
      value: metrics ? `${formatNumber(metrics.script_accuracy)}%` : '--'
    },
    {
      key: 'attention',
      label: '需要留意的地方',
      value: metrics ? `${formatNumber(metrics.error_count)}处` : '--'
    },
    {
      key: 'pace',
      label: '说话节奏',
      value: metrics ? paceLabel(metrics.speech_rate) : '--'
    },
    {
      key: 'voice',
      label: '声音状态',
      value: metrics ? loudnessLabel(metrics.loudness) : '--'
    }
  ]
})

const adviceTitle = computed(() => {
  const metrics = latestMetrics.value
  if (!metrics) return '先完成一次训练'
  if (metrics.script_accuracy < 70 || metrics.error_count >= 4) return '先把短句说稳'
  if (metrics.speech_rate < 180) return '可以练连续表达'
  if (metrics.loudness < 60) return '试着把声音放出来'
  return '保持现在的节奏'
})

const adviceText = computed(() => {
  const metrics = latestMetrics.value
  if (!metrics) return '完成一次训练后，系统会根据你的练习情况给出下一步建议。'
  if (metrics.script_accuracy < 70 || metrics.error_count >= 4) {
    return '下一次可以选择短一点、熟悉一点的句子，先把一句话完整说出来。'
  }
  if (metrics.speech_rate < 180) {
    return '下一次可以试着少停顿，把熟悉的短句连起来说。'
  }
  if (metrics.loudness < 60) {
    return '下一次可以坐直一点，慢慢吸气后再开口，让声音更清楚。'
  }
  return '最近练习比较稳定，可以继续完成今天的训练。'
})

onMounted(async () => {
  await loadEvaluationData()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  trendChart?.dispose()
})

async function loadEvaluationData() {
  loading.value = true
  error.value = ''
  try {
    trend.value = await evaluationsApi.processTrend(20)
    await nextTick()
    renderTrendChart()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '训练变化加载失败'
  } finally {
    loading.value = false
  }
}

function renderTrendChart() {
  trendChart?.dispose()
  trendChart = null
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
      lineSeries('表达完整度', 'script_accuracy', '#2563eb'),
      lineSeries('需要留意', 'error_count', '#e86f51')
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

function resizeChart() {
  trendChart?.resize()
}

function paceLabel(value: number) {
  if (value < 180) return '偏慢'
  if (value > 240) return '偏快'
  return '合适'
}

function loudnessLabel(value: number) {
  if (value < 60) return '偏轻'
  if (value > 78) return '偏响'
  return '稳定'
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}
</script>
