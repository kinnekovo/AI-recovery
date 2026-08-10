<template>
  <section class="page-stack">
    <div class="page-heading split">
      <div>
        <span class="kicker">康复记录</span>
        <h1>最近训练概览</h1>
        <p>报告基于已保存的过程性监控和阶段性评估生成。</p>
      </div>
      <RouterLink class="primary-link" to="/training">继续训练</RouterLink>
    </div>

    <p v-if="loading" class="success-text">正在加载康复记录。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section class="report-overview">
      <div class="report-count">
        <span class="metric">{{ report?.training_count ?? 0 }}</span>
        <p>已生成反馈的训练次数</p>
      </div>
      <div class="report-suggestion">
        <strong>下一步建议</strong>
        <p>{{ report?.suggestion || '完成一次训练后生成建议。' }}</p>
      </div>
    </section>

    <section class="report-section">
      <div class="panel-heading">
        <div>
          <h2>过程性监控汇总</h2>
          <p>统计已保存的脚本正确率、错误次数、语速和响度。</p>
        </div>
      </div>
      <div v-if="hasProcessData" class="metric-grid report-metrics">
        <div v-for="metric in processMetricCards" :key="metric.key" class="metric-card">
          <span>{{ metric.value }}</span>
          <p>{{ metric.label }}</p>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>完成一次训练并生成反馈后，这里会显示过程性监控均值。</p>
        <RouterLink to="/training">开始训练</RouterLink>
      </div>
    </section>

    <section class="report-section">
      <div class="panel-heading">
        <div>
          <h2>阶段性变化摘要</h2>
          <p>基于 baseline 和当前阶段评估，展示 WAB、CADL 与接受度变化。</p>
        </div>
      </div>
      <div v-if="hasEffectComparison" class="comparison-table">
        <div class="comparison-row comparison-head">
          <span>指标</span>
          <span>训练前</span>
          <span>当前</span>
          <span>变化</span>
        </div>
        <div v-for="row in effectRows" :key="row.key" class="comparison-row">
          <span>{{ row.label }}</span>
          <span>{{ row.baseline }}</span>
          <span>{{ row.current }}</span>
          <span :class="{ 'positive-change': Number(row.change) > 0 }">{{ row.change }}</span>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>录入 baseline 和训练后评估后，这里会生成阶段性变化摘要。</p>
        <RouterLink to="/evaluation">查看康复评估</RouterLink>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { reportsApi } from '@/api/reports'
import type { LatestReport, ProcessMonitoringSummary, ReportMetricComparison } from '@/types/api'

const report = ref<LatestReport | null>(null)
const loading = ref(true)
const error = ref('')

const processMetricLabels: Record<keyof ProcessMonitoringSummary, string> = {
  avg_script_accuracy: '平均脚本正确率',
  avg_error_count: '平均错误次数',
  avg_speech_rate: '平均字/min',
  avg_loudness: '平均 dBA'
}

const effectLabels: Record<string, string> = {
  wab_information: 'WAB 信息量',
  wab_fluency: 'WAB 流利性',
  wab_grammar: 'WAB 语法',
  wab_word_order: 'WAB 语序',
  wab_comprehensibility: 'WAB 可懂度',
  wab_repetition_comprehensibility: 'WAB 复述可懂度',
  cadl: 'CADL',
  acceptance: '接受度'
}

const hasProcessData = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return !!summary && Object.values(summary).some((value) => value !== null)
})

const processMetricCards = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return (Object.keys(processMetricLabels) as Array<keyof ProcessMonitoringSummary>).map((key) => ({
    key,
    label: processMetricLabels[key],
    value: summary?.[key] === null || summary?.[key] === undefined ? '--' : formatNumber(summary[key])
  }))
})

const hasEffectComparison = computed(() => !!report.value?.effect_comparison.has_comparison)

const effectRows = computed(() => {
  const effect = report.value?.effect_comparison
  if (!effect) return []
  const rows = Object.entries(effect.wab).map(([key, item]) => toEffectRow(key, effectLabels[key], item))
  if (effect.cadl) rows.push(toEffectRow('cadl', effectLabels.cadl, effect.cadl))
  if (effect.acceptance) rows.push(toEffectRow('acceptance', effectLabels.acceptance, effect.acceptance))
  return rows
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

function toEffectRow(key: string, label: string, item: ReportMetricComparison) {
  return {
    key,
    label,
    baseline: valueOrDash(item.baseline),
    current: valueOrDash(item.current),
    change: valueOrDash(item.change)
  }
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function valueOrDash(value: number | null) {
  return value === null ? '--' : formatNumber(value)
}
</script>
