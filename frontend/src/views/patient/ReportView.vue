<template>
  <section class="page-stack">
    <div class="page-heading split">
      <div>
        <span class="kicker">康复记录</span>
        <h1>最近练习小结</h1>
        <p>这里把训练记录整理成容易理解的小结，帮助你和家人看到坚持练习的变化。</p>
      </div>
      <RouterLink class="primary-link" to="/training">继续训练</RouterLink>
    </div>

    <p v-if="loading" class="success-text">正在加载康复记录。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section class="report-overview">
      <div class="report-count">
        <span class="metric">{{ report?.training_count ?? 0 }}</span>
        <p>已完成反馈的训练</p>
      </div>
      <div class="report-suggestion">
        <strong>下一步建议</strong>
        <p>{{ patientSuggestion }}</p>
      </div>
    </section>

    <section class="report-section">
      <div class="panel-heading">
        <div>
          <h2>最近表现</h2>
          <p>系统把专业指标转成练习时更容易理解的说法。</p>
        </div>
      </div>
      <div v-if="hasProcessData" class="metric-grid report-metrics">
        <div v-for="metric in processMetricCards" :key="metric.key" class="metric-card patient-metric-card">
          <span>{{ metric.value }}</span>
          <p>{{ metric.label }}</p>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>完成一次训练并生成反馈后，这里会显示最近练习小结。</p>
        <RouterLink to="/training">开始训练</RouterLink>
      </div>
    </section>

    <section class="report-section">
      <div class="panel-heading">
        <div>
          <h2>阶段记录</h2>
          <p>阶段评估由治疗师或研究人员记录，患者端只显示简化结果。</p>
        </div>
      </div>
      <div class="patient-advice">
        <strong>{{ stageTitle }}</strong>
        <p>{{ stageText }}</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { reportsApi } from '@/api/reports'
import type { LatestReport, ProcessMonitoringSummary } from '@/types/api'

const report = ref<LatestReport | null>(null)
const loading = ref(true)
const error = ref('')

const hasProcessData = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return !!summary && Object.values(summary).some((value) => value !== null)
})

const patientSuggestion = computed(() => {
  const summary = report.value?.process_monitoring_summary
  if (!summary || summary.avg_script_accuracy === null) return '完成一次训练后，系统会给出下一步练习建议。'
  if (summary.avg_script_accuracy < 70 || (summary.avg_error_count ?? 0) >= 4) {
    return '建议先练短句，把一句话说完整，再慢慢增加难度。'
  }
  if (summary.avg_speech_rate !== null && summary.avg_speech_rate < 180) {
    return '可以继续练熟悉短句，重点放在少停顿、连起来说。'
  }
  if (summary.avg_loudness !== null && summary.avg_loudness < 60) {
    return '可以试着把声音放清楚一点，不用着急，稳定开口最重要。'
  }
  return '最近练习比较稳定，继续保持今天的训练节奏。'
})

const processMetricCards = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return [
    {
      key: 'expression',
      label: '平均表达完整度',
      value: toPercent(summary?.avg_script_accuracy)
    },
    {
      key: 'attention',
      label: '平均需要留意',
      value: summary?.avg_error_count === null || summary?.avg_error_count === undefined
        ? '--'
        : `${formatNumber(summary.avg_error_count)}处`
    },
    {
      key: 'pace',
      label: '说话节奏',
      value: summary?.avg_speech_rate === null || summary?.avg_speech_rate === undefined
        ? '--'
        : paceLabel(summary.avg_speech_rate)
    },
    {
      key: 'voice',
      label: '声音状态',
      value: summary?.avg_loudness === null || summary?.avg_loudness === undefined
        ? '--'
        : loudnessLabel(summary.avg_loudness)
    }
  ]
})

const stageTitle = computed(() => {
  if (!report.value?.effect_comparison.has_comparison) return '还没有完整阶段记录'
  return '已完成一次阶段对比'
})

const stageText = computed(() => {
  if (!report.value?.effect_comparison.has_comparison) {
    return '后续由治疗师或研究人员录入训练前后的阶段评估，患者端会显示简化后的变化说明。'
  }
  return '系统已记录训练前后的阶段变化。后续建议会结合这些记录，但这里不展示专业量表细节。'
})

onMounted(async () => {
  try {
    report.value = await reportsApi.latest()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '康复记录加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
})

function toPercent(value: ProcessMonitoringSummary[keyof ProcessMonitoringSummary] | undefined) {
  return value === null || value === undefined ? '--' : `${formatNumber(value)}%`
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
