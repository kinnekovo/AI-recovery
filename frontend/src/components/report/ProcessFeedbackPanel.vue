<template>
  <section class="process-feedback">
    <section v-if="scenario" class="scenario-result-panel" :class="`status-${scenario.goal_status}`">
      <div>
        <span class="chip ok">场景沟通结果</span>
        <h3>{{ scenarioHeadline }}</h3>
        <p>{{ scenario.communication_goal }}</p>
      </div>
      <div class="scenario-unit-list" aria-label="关键信息识别结果">
        <div v-for="unit in scenario.required_information_units" :key="unit.id" :class="['scenario-unit', { matched: unit.matched }]">
          <span aria-hidden="true">{{ unit.matched ? '✓' : '○' }}</span>
          <div>
            <strong>{{ unit.label }}</strong>
            <small>{{ unit.matched ? `已识别${unit.matches.length ? `：${unit.matches.join('、')}` : ''}` : '下次可以补充' }}</small>
          </div>
        </div>
      </div>
      <p v-if="scenario.repair_ability?.status === 'not_observed'" class="scene-boundary">沟通修复能力：本题没有发生追问，暂不评分。</p>
    </section>
    <div v-if="result.transcript || result.process_details" class="patient-explain-panel">
      <div>
        <span class="chip ok">{{ scenario ? '系统听到' : '本次表达' }}</span>
        <h3>{{ patientSummary }}</h3>
        <p v-if="result.transcript">系统听到：{{ result.transcript }}</p>
      </div>
      <div v-if="!scenario && simpleMismatch.length" class="simple-mismatch-row">
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
import type { ScenarioEvaluation, TrainingFeedbackResult } from '@/types/api'
import { formatPatientMetricValue, isProcessMetricKey, processMetricCatalog, type ProcessMetricKey } from '@/utils/processMetrics'

const props = defineProps<{ result: TrainingFeedbackResult }>()
const scenario = computed(() => props.result.process_details?.scenario_evaluation as ScenarioEvaluation | null | undefined)

const patientSummary = computed(() => {
  if (scenario.value?.goal_status === 'achieved') return '主要需求已经说清楚了。'
  if (scenario.value?.goal_status === 'partly_achieved') return '主要意思已经有了，再补充一点会更清楚。'
  if (scenario.value) return '先从最重要的需求开始说就可以。'
  const metrics = props.result.process_metrics
  if (metrics.script_accuracy >= 90 && metrics.error_count <= 1) return '这次说得比较完整，继续保持。'
  if (metrics.script_accuracy >= 70) return '主要内容说出来了，下一次可以再说完整一点。'
  return '这次有些地方没说完整，先放慢一点练短句。'
})

const scenarioHeadline = computed(() => {
  if (scenario.value?.goal_status === 'achieved') return '沟通目标已达成'
  if (scenario.value?.goal_status === 'partly_achieved') return '沟通目标部分达成'
  return '再补充一点关键信息'
})

const simpleMismatch = computed(() => {
  const mismatch = props.result.process_details?.script_mismatch_events || {}
  const items = []
  if ((mismatch.omission || 0) > 0) items.push(`少说 ${mismatch.omission} 处`)
  if ((mismatch.addition || 0) > 0) items.push(`多说 ${mismatch.addition} 处`)
  if ((mismatch.substitution || 0) > 0) items.push(`换说 ${mismatch.substitution} 处`)
  return items
})

const processMetricOrder: ProcessMetricKey[] = ['error_count', 'speech_rate', 'loudness']
const metricCards = computed(() =>
  (scenario.value ? processMetricOrder : ['script_accuracy', ...processMetricOrder] as ProcessMetricKey[]).map((key) => ({
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
