<template>
  <section class="process-feedback">
    <div class="metric-grid">
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.script_accuracy) }}%</span>
        <p>脚本正确率</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.error_count) }}</span>
        <p>错误次数</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.speech_rate) }}</span>
        <p>字/min</p>
      </div>
      <div class="metric-card">
        <span>{{ formatNumber(result.process_metrics.loudness) }}</span>
        <p>dBA</p>
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
import type { TrainingFeedbackResult } from '@/types/api'

defineProps<{ result: TrainingFeedbackResult }>()

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function metricLabel(metric: string) {
  const labels: Record<string, string> = {
    script_accuracy: '脚本正确率',
    error_count: '错误统计',
    speech_rate: '言语速率',
    loudness: '响度'
  }
  return labels[metric] || metric
}
</script>
