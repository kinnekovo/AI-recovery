<template>
  <section class="process-feedback">
    <div v-if="result.transcript || result.process_details" class="patient-explain-panel">
      <div>
        <span class="chip ok">本次表达</span>
        <h3>{{ patientSummary }}</h3>
        <p v-if="result.transcript">系统听到：{{ result.transcript }}</p>
      </div>
      <div v-if="simpleMismatch.length" class="simple-mismatch-row">
        <span v-for="item in simpleMismatch" :key="item">{{ item }}</span>
      </div>
    </div>
    <div class="metric-grid">
      <div v-for="metric in metricCards" :key="metric.key" class="metric-card">
        <span>{{ metric.value }}</span>
        <p>{{ metric.label }}</p>
        <small>{{ metric.hint }}</small>
      </div>
    </div>

    <div class="feedback-list">
      <article v-for="item in result.feedback" :key="item.metric" class="feedback-item">
        <div>
          <span class="chip ok">{{ metricLabel(item.metric) }}</span>
          <h3>{{ item.current_performance }}</h3>
        </div>
        <p>{{ item.suggestion }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TrainingFeedbackResult } from '@/types/api'
import { formatPatientMetricValue, isProcessMetricKey, processMetricCatalog, type ProcessMetricKey } from '@/utils/processMetrics'

const props = defineProps<{ result: TrainingFeedbackResult }>()

const patientSummary = computed(() => {
  const metrics = props.result.process_metrics
  if (metrics.script_accuracy >= 90 && metrics.error_count <= 1) return '这次说得比较完整，继续保持。'
  if (metrics.script_accuracy >= 70) return '主要内容说出来了，下一次可以再说完整一点。'
  return '这次有些地方没说完整，先放慢一点练短句。'
})

const simpleMismatch = computed(() => {
  const mismatch = props.result.process_details?.script_mismatch_events || {}
  const items = []
  if ((mismatch.omission || 0) > 0) items.push(`少说 ${mismatch.omission} 处`)
  if ((mismatch.addition || 0) > 0) items.push(`多说 ${mismatch.addition} 处`)
  if ((mismatch.substitution || 0) > 0) items.push(`换说 ${mismatch.substitution} 处`)
  return items
})

const processMetricOrder: ProcessMetricKey[] = ['script_accuracy', 'error_count', 'speech_rate', 'loudness']
const metricCards = computed(() =>
  processMetricOrder.map((key) => ({
    key,
    value: formatPatientMetricValue(key, props.result.process_metrics[key]),
    label: processMetricCatalog[key].patientLabel,
    hint: processMetricCatalog[key].patientHint
  }))
)

function metricLabel(metric: string) {
  return isProcessMetricKey(metric) ? processMetricCatalog[metric].label : metric
}
</script>
