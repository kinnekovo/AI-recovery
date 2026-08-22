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
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.script_accuracy) }}%</span>
        <p>表达完整度</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.error_count) }}</span>
        <p>需要留意</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.speech_rate) }}</span>
        <p>说话节奏 字/min</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.loudness) }}</span>
        <p>声音响度 dBA</p>
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

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function metricLabel(metric: string) {
  const labels: Record<string, string> = {
    script_accuracy: '表达完整度',
    error_count: '错误统计',
    speech_rate: '言语速率',
    loudness: '响度'
  }
  return labels[metric] || metric
}
</script>
