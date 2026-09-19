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
        <p>这里用简短的话说明最近练习状态，方便你决定下一次怎么练。</p>
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
          <h2>场景表达</h2>
          <p>只汇总场景表达；跟读成绩不会混在这里。至少完成 3 次可比场景后再看趋势。</p>
        </div>
      </div>
      <div v-if="scenarioSummary.attempt_count" class="scenario-report-summary">
        <div>
          <span>{{ scenarioValue(scenarioSummary.independent_goal_achievement_rate) }}</span>
          <p>近期独立沟通达成</p>
        </div>
        <div>
          <span>{{ scenarioValue(scenarioSummary.median_information_unit_score) }}</span>
          <p>关键信息完整度中位数</p>
        </div>
        <div>
          <span>{{ scenarioValue(scenarioSummary.median_independence_score) }}</span>
          <p>独立表达中位数</p>
        </div>
      </div>
      <div v-else class="empty-state compact-empty">
        <p>完成一次场景表达后，这里会单独记录“是否把需求说清楚”。</p>
      </div>
      <p v-if="scenarioSummary.attempt_count" class="scenario-report-note">{{ scenarioSummary.summary }}</p>
      <p v-if="scenarioSummary.therapist_reviewed_count" class="scenario-review-note">
        治疗师已复核 {{ scenarioSummary.therapist_reviewed_count }} 次场景表达{{ scenarioSummary.therapist_adjusted_count ? `，并修正其中 ${scenarioSummary.therapist_adjusted_count} 次自动结论` : '' }}。
      </p>
      <RouterLink v-if="scenarioSummary.attempt_count >= 3" class="secondary-link scenario-probe-link" to="/training/scenario?mode=generalization_probe">
        试试一个新场景小测
      </RouterLink>
      <div v-if="scenarioSummary.generalization_probe_count" class="generalization-note">
        <strong>新场景小测</strong>
        <p>独立沟通达成：{{ scenarioValue(scenarioSummary.generalization_independent_goal_achievement_rate) }}</p>
        <p>已覆盖 {{ scenarioSummary.generalization_probe_distinct_date_count }} 个不同训练日期</p>
        <p>{{ scenarioSummary.generalization_summary }}</p>
      </div>
      <div v-if="dialogueTrends.training.dialogue_count" class="generalization-note">
        <strong>多轮场景对话趋势</strong>
        <p>已完成 {{ dialogueTrends.training.dialogue_count }} 段日常对话；独立目标达成：{{ trendPercent(dialogueTrends.training.independent_goal_achievement_rate) }}</p>
        <p>平均提示等级：{{ dialogueTrends.training.average_prompt_level ?? '--' }}；有效回应：{{ trendPercent(dialogueTrends.training.effective_response_rate, false) }}</p>
        <p v-if="dialogueTrends.generalization_probe.dialogue_count">新场景小测 {{ dialogueTrends.generalization_probe.dialogue_count }} 段，独立达成：{{ trendPercent(dialogueTrends.generalization_probe.independent_goal_achievement_rate) }}</p>
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
import { loudnessBand } from '@/config/algorithmThresholds'
import { reportsApi } from '@/api/reports'
import { scenarioDialoguesApi } from '@/api/scenarioDialogues'
import type { LatestReport, ProcessMonitoringSummary, ScenarioCommunicationSummary } from '@/types/api'
import { toUserMessage } from '@/utils/errors'
import { formatPatientMetricValue, type ProcessMetricKey } from '@/utils/processMetrics'

const report = ref<LatestReport | null>(null)
const loading = ref(true)
const error = ref('')
type DialogueTrend = { dialogue_count: number; independent_goal_achievement_rate: number | null; median_information_score: number | null; effective_response_rate: number | null; average_prompt_level: number | null; observed_repair_success_rate: number | null }
const emptyTrend: DialogueTrend = { dialogue_count: 0, independent_goal_achievement_rate: null, median_information_score: null, effective_response_rate: null, average_prompt_level: null, observed_repair_success_rate: null }
const dialogueTrends = ref<{ training: DialogueTrend; generalization_probe: DialogueTrend }>({ training: { ...emptyTrend }, generalization_probe: { ...emptyTrend } })
const scenarioSummary = computed<ScenarioCommunicationSummary>(() => report.value?.scenario_communication_summary || {
  attempt_count: 0,
  recent_valid_count: 0,
  independent_goal_achievement_rate: null,
  median_information_unit_score: null,
  median_independence_score: null,
  generalization_probe_count: 0,
  generalization_probe_distinct_date_count: 0,
  generalization_independent_goal_achievement_rate: null,
  generalization_summary: '尚未完成新场景泛化探测。',
  therapist_reviewed_count: 0,
  therapist_adjusted_count: 0,
  summary: '还没有完成可用的场景表达反馈。'
})

const hasProcessData = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return !!summary && Object.values(summary).some((value) => value !== null)
})

const patientSuggestion = computed(() => {
  if (report.value?.suggestion) return report.value.suggestion
  const summary = report.value?.process_monitoring_summary
  if (!summary || summary.avg_script_accuracy === null) return '完成一次训练后，系统会给出下一步练习建议。'
  if (summary.avg_script_accuracy < 70 || (summary.avg_error_count ?? 0) >= 4) {
    return '建议先练短句，把一句话说完整，再慢慢增加难度。'
  }
  if (summary.avg_speech_rate !== null && summary.avg_speech_rate < 180) {
    return '可以继续练熟悉短句，重点放在少停顿、连起来说。'
  }
  if (summary.avg_loudness !== null && loudnessBand(summary.avg_loudness) === 'low') {
    return '可以试着把声音放清楚一点，不用着急，稳定开口最重要。'
  }
  return '最近练习比较稳定，继续保持今天的训练节奏。'
})

const processMetricCards = computed(() => {
  const summary = report.value?.process_monitoring_summary
  return [
    {
      key: 'script_accuracy',
      label: '平均表达完整度',
      value: patientValue('script_accuracy', summary?.avg_script_accuracy)
    },
    {
      key: 'error_count',
      label: '需要留意的地方',
      value: patientValue('error_count', summary?.avg_error_count)
    },
    {
      key: 'speech_rate',
      label: '说话节奏',
      value: patientValue('speech_rate', summary?.avg_speech_rate)
    },
    {
      key: 'loudness',
      label: '声音状态',
      value: patientValue('loudness', summary?.avg_loudness)
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
    const [latest, trends] = await Promise.all([reportsApi.latest(), scenarioDialoguesApi.trends()])
    report.value = latest
    dialogueTrends.value = trends
  } catch (err) {
    error.value = toUserMessage(err, '康复记录加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
})

function patientValue(key: ProcessMetricKey, value: ProcessMonitoringSummary[keyof ProcessMonitoringSummary] | undefined) {
  return value === null || value === undefined ? '--' : formatPatientMetricValue(key, value)
}

function scenarioValue(value: number | null) {
  return value === null ? '--' : `${value}%`
}

function trendPercent(value: number | null, fraction = true) {
  if (value === null) return '--'
  return `${Math.round((fraction ? value * 100 : value) * 10) / 10}%`
}
</script>
