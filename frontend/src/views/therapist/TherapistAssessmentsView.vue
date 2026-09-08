<template>
  <section class="page-stack therapist-assessment-page">
    <div class="page-heading therapist-review-heading">
      <div>
        <span class="kicker">阶段评估</span>
        <h1>自动评估复核</h1>
        <p>患者完成训练分析后，系统自动生成评估记录。治疗师只需要确认、必要时修正，并留下临床备注。</p>
      </div>
      <div class="review-summary-strip">
        <span>
          <strong>{{ totalPendingCount }}</strong>
          待复核
        </span>
        <span>
          <strong>{{ history.length }}</strong>
          当前患者记录
        </span>
      </div>
    </div>

    <p v-if="loading" class="success-text">正在加载患者与评估记录。</p>
    <p v-if="pageError" class="error-text">{{ pageError }}</p>

    <section class="therapist-review-grid">
      <article class="therapist-panel patient-queue-panel">
        <div class="panel-heading">
          <div>
            <h2>患者队列</h2>
            <p>优先处理有待复核记录的患者。</p>
          </div>
        </div>
        <div v-if="patients.length" class="patient-picker">
          <button
            v-for="patient in patients"
            :key="patient.user_id"
            type="button"
            class="patient-row"
            :class="{ active: patient.user_id === selectedPatientId }"
            @click="selectPatient(patient.user_id)"
          >
            <span class="patient-row-title">
              <strong>{{ patient.username }}</strong>
              <em v-if="patient.pending_review_count">{{ patient.pending_review_count }}</em>
            </span>
            <span>{{ patient.pending_review_count ? '需要复核' : '暂无待办' }}</span>
            <small>{{ patient.latest_assessment_at ? `最近：${dateLabel(patient.latest_assessment_at)}` : '暂无自动评估' }}</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <p>暂时没有患者账号。</p>
        </div>
      </article>

      <article class="therapist-panel record-list-panel">
        <div class="panel-heading">
          <div>
            <h2>自动评估</h2>
            <p>{{ selectedPatient ? `当前患者：${selectedPatient.username}` : '请先选择患者' }}</p>
          </div>
        </div>
        <div v-if="historyLoading" class="success-text">正在刷新记录。</div>
        <div v-else-if="displayHistory.length" class="review-record-list">
          <button
            v-for="item in displayHistory"
            :key="item.id"
            type="button"
            class="review-record"
            :class="{ active: item.id === selectedAssessmentId, pending: item.review_status === 'pending_review' }"
            @click="selectAssessment(item.id)"
          >
            <span class="record-topline">
              <strong>{{ assessmentTypeLabel(item.assessment_type) }}</strong>
              <span class="review-status" :class="item.review_status">{{ reviewStatusLabel(item.review_status) }}</span>
            </span>
            <span class="record-date">{{ dateTimeLabel(item.assessed_at) }}</span>
            <span class="record-metrics">{{ recordMetricLine(item) }}</span>
          </button>
        </div>
        <div v-else class="empty-state">
          <p>该患者还没有自动评估记录。患者完成训练并点击分析后，这里会出现待复核记录。</p>
        </div>
      </article>

      <article class="therapist-panel review-detail-panel">
        <div class="panel-heading">
          <div>
            <h2>复核详情</h2>
            <p>{{ selectedAssessment ? reviewStatusLabel(selectedAssessment.review_status) : '选择一条记录后复核' }}</p>
          </div>
        </div>

        <div v-if="selectedAssessment" class="review-detail">
          <div class="review-meta">
            <span>{{ sourceLabel(selectedAssessment.evaluation_source) }}</span>
            <span>{{ dateTimeLabel(selectedAssessment.assessed_at) }}</span>
            <span v-if="selectedAssessment.source_attempt_id">训练 {{ shortId(selectedAssessment.source_attempt_id) }}</span>
          </div>

          <div class="auto-summary">
            <strong>系统初步判断</strong>
            <p>{{ autoSummary }}</p>
          </div>

          <div v-if="selectedAssessment.source_audio_url || selectedAssessment.source_asr_text" class="source-evidence-box">
            <div>
              <strong>源训练依据</strong>
              <p v-if="selectedAssessment.source_target_text">目标句：{{ selectedAssessment.source_target_text }}</p>
              <p v-if="selectedAssessment.source_asr_text">ASR 转写：{{ selectedAssessment.source_asr_text }}</p>
            </div>
            <AudioPlayback :src="selectedAssessment.source_audio_url" />
          </div>

          <div class="metric-summary-grid">
            <div v-for="metric in metricCards" :key="metric.key" class="metric-summary-card" :class="metric.tone">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
              <p>{{ metric.brief }}</p>
            </div>
          </div>

          <div class="system-note-box">
            <strong>系统说明</strong>
            <p>{{ systemNotes || '系统未提供额外说明。' }}</p>
          </div>

          <div v-if="processEvidence.length || providerLine" class="system-note-box process-evidence-box">
            <strong>过程性监控依据</strong>
            <div v-if="processEvidence.length" class="evidence-chip-row">
              <span v-for="item in processEvidence" :key="item">{{ item }}</span>
            </div>
            <p v-if="providerLine">{{ providerLine }}</p>
            <p v-if="limitationLine">{{ limitationLine }}</p>
          </div>

          <details class="adjust-panel">
            <summary>需要修正指标</summary>
            <div class="metric-edit-grid">
              <label v-for="metric in metricCards" :key="metric.key">
                {{ metric.label }}
                <span>
                  <input v-model="metricEdits[metric.key]" type="number" step="0.1" :disabled="reviewSubmitting" />
                  <em>{{ metric.unit }}</em>
                </span>
              </label>
            </div>
          </details>

          <label class="assessment-notes">
            治疗师复核备注
            <textarea
              v-model="reviewNotes"
              rows="3"
              maxlength="2000"
              placeholder="例如：与临床观察一致，建议继续当前训练；或说明本次修正依据。"
              :disabled="reviewSubmitting"
            ></textarea>
          </label>

          <div class="action-row review-actions">
            <button
              class="app-button primary"
              type="button"
              :disabled="reviewSubmitting || selectedAssessment.review_status === 'confirmed'"
              @click="confirmAssessment"
            >
              {{ reviewSubmitting ? '处理中' : '确认自动评估' }}
            </button>
            <button class="app-button secondary" type="button" :disabled="reviewSubmitting" @click="adjustAssessment">
              保存修正
            </button>
          </div>
          <div
            v-if="reviewSubmitting || formError || formSuccess"
            class="form-feedback"
            :class="{ error: !!formError, success: !!formSuccess && !formError }"
            role="status"
            aria-live="polite"
          >
            {{ reviewSubmitting ? '正在提交复核结果。' : formError || formSuccess }}
          </div>
        </div>
        <div v-else class="empty-state">
          <p>请选择一条系统自动生成的评估记录。</p>
        </div>
      </article>
    </section>

    <section class="comparison-panel therapist-trend-panel">
      <div class="panel-heading">
        <div>
          <h2>趋势对比</h2>
          <p>默认比较最早一次和最近一次评估，帮助快速判断训练变化。</p>
        </div>
      </div>
      <div v-if="hasCompare" class="comparison-table compact-comparison">
        <div class="comparison-row comparison-head">
          <span>指标</span>
          <span>最早</span>
          <span>最近</span>
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
        <p>至少需要两条评估记录才能形成趋势对比。</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import { therapistApi } from '@/api/therapist'
import type {
  AssessmentCompare,
  AssessmentReviewStatus,
  AssessmentSession,
  AssessmentType,
  EvaluationSource,
  TherapistPatient
} from '@/types/api'
import { toUserMessage } from '@/utils/errors'
import {
  formatMetricValue,
  isProcessMetricKey,
  processMetricBrief,
  processMetricCatalog,
  processMetricTone
} from '@/utils/processMetrics'

const patients = ref<TherapistPatient[]>([])
const selectedPatientId = ref('')
const selectedAssessmentId = ref('')
const history = ref<AssessmentSession[]>([])
const compare = ref<AssessmentCompare | null>(null)
const loading = ref(true)
const historyLoading = ref(false)
const reviewSubmitting = ref(false)
const pageError = ref('')
const formError = ref('')
const formSuccess = ref('')
const reviewNotes = ref('')
const systemNotes = ref('')
const metricEdits = ref<Record<string, string>>({})

const assessmentTypeOptions: Array<{ value: AssessmentType; label: string }> = [
  { value: 'baseline', label: '训练前' },
  { value: 'during', label: '训练中' },
  { value: 'after_30_days', label: '训练 30 天后' },
  { value: 'post_training', label: '训练结束后' }
]

const longTermMetricLabels: Record<string, { label: string; unit: string; polarity: 'positive' | 'negative' | 'neutral' }> = {
  wab_information: { label: 'WAB 信息量', unit: '分', polarity: 'positive' },
  wab_fluency: { label: 'WAB 流利性', unit: '分', polarity: 'positive' },
  wab_grammar: { label: 'WAB 语法', unit: '分', polarity: 'positive' },
  wab_word_order: { label: 'WAB 语序', unit: '分', polarity: 'positive' },
  wab_comprehensibility: { label: 'WAB 可懂度', unit: '分', polarity: 'positive' },
  wab_repetition_comprehensibility: { label: 'WAB 复述可懂度', unit: '分', polarity: 'positive' },
  cadl_score: { label: 'CADL 总分', unit: '分', polarity: 'positive' },
  acceptance_score: { label: '接受度', unit: '分', polarity: 'positive' }
}

function metricDefinition(key: string) {
  if (isProcessMetricKey(key)) return processMetricCatalog[key]
  return longTermMetricLabels[key]
}

const selectedPatient = computed(() => patients.value.find((item) => item.user_id === selectedPatientId.value))
const selectedAssessment = computed(() => history.value.find((item) => item.id === selectedAssessmentId.value))
const displayHistory = computed(() => [...history.value].reverse())
const totalPendingCount = computed(() => patients.value.reduce((sum, item) => sum + item.pending_review_count, 0))
const metricCards = computed(() => {
  const metrics = selectedAssessment.value?.metrics || {}
  return Object.entries(metrics).map(([key, value]) => ({
    key,
    label: metricDefinition(key)?.label || key,
    unit: metricDefinition(key)?.unit || '',
    value: valueOrDash(value),
    tone: metricTone(key, value),
    brief: metricBrief(key, value)
  }))
})

const processEvidence = computed(() => {
  const details = selectedAssessment.value?.source_process_details
  const mismatch = details?.script_mismatch_events || {}
  const errors = details?.error_events || {}
  const items = []
  if (details?.correct_script_word_count != null && details?.total_script_word_count != null) {
    items.push(`正确生成 ${details.correct_script_word_count}/${details.total_script_word_count} 字`)
  }
  if ((mismatch.omission || 0) > 0) items.push(`遗漏 ${mismatch.omission} 处`)
  if ((mismatch.addition || 0) > 0) items.push(`添加 ${mismatch.addition} 处`)
  if ((mismatch.substitution || 0) > 0) items.push(`替换 ${mismatch.substitution} 处`)
  if ((errors.long_pause_over_3s || 0) > 0) items.push(`长停顿 ${errors.long_pause_over_3s} 次`)
  if ((errors.filler || 0) > 0) items.push(`插入语 ${errors.filler} 次`)
  return items
})

const providerLine = computed(() => {
  const sources = selectedAssessment.value?.source_process_details?.input_sources
  if (!sources) return ''
  return `来源：ASR ${sources.asr_provider || 'unknown'}，声学分析 ${sources.acoustic_provider || 'unknown'}。`
})

const limitationLine = computed(() => {
  const limitations = selectedAssessment.value?.source_process_details?.limitations
  return limitations?.length ? limitations.join('；') : ''
})

const autoSummary = computed(() => {
  const metrics = selectedAssessment.value?.metrics || {}
  const parts = [
    summaryForAccuracy(metrics.script_accuracy),
    summaryForErrors(metrics.error_count),
    summaryForSpeechRate(metrics.speech_rate),
    summaryForLoudness(metrics.loudness)
  ].filter(Boolean)
  return parts.length ? parts.join('；') + '。' : '系统已生成评估，等待治疗师复核。'
})

const hasCompare = computed(
  () =>
    !!compare.value?.baseline_assessment &&
    !!compare.value?.current_assessment &&
    compare.value.baseline_assessment.id !== compare.value.current_assessment.id
)

const comparisonRows = computed(() => {
  if (!compare.value) return []
  return Object.entries(compare.value.metrics)
    .filter(([key]) => metricDefinition(key))
    .map(([key, item]) => ({
      key,
      label: metricDefinition(key).label,
      baseline: valueOrDash(item.baseline),
      current: valueOrDash(item.current),
      change: valueOrDash(item.change)
    }))
})

onMounted(async () => {
  try {
    patients.value = await therapistApi.patients()
    patients.value.sort((left, right) => right.pending_review_count - left.pending_review_count)
    if (patients.value[0]) await selectPatient(patients.value[0].user_id)
  } catch (err) {
    pageError.value = toUserMessage(err, '患者列表加载失败')
  } finally {
    loading.value = false
  }
})

async function selectPatient(patientUserId: string) {
  selectedPatientId.value = patientUserId
  selectedAssessmentId.value = ''
  clearMessages()
  await loadPatientAssessments()
}

async function loadPatientAssessments() {
  if (!selectedPatientId.value) return
  historyLoading.value = true
  try {
    const [historyData, compareData] = await Promise.all([
      therapistApi.assessmentHistory(selectedPatientId.value),
      therapistApi.assessmentCompare(selectedPatientId.value)
    ])
    history.value = historyData
    compare.value = compareData
    const pending = history.value.find((item) => item.review_status === 'pending_review')
    selectedAssessmentId.value = pending?.id || history.value[history.value.length - 1]?.id || ''
    syncReviewForm()
  } catch (err) {
    pageError.value = toUserMessage(err, '评估记录加载失败')
  } finally {
    historyLoading.value = false
  }
}

function selectAssessment(assessmentId: string) {
  selectedAssessmentId.value = assessmentId
  clearMessages()
  syncReviewForm()
}

function syncReviewForm() {
  const assessment = selectedAssessment.value
  reviewNotes.value = assessment?.therapist_notes || ''
  systemNotes.value = assessment?.notes || ''
  metricEdits.value = Object.fromEntries(
    Object.entries(assessment?.metrics || {}).map(([key, value]) => [key, String(value)])
  )
}

async function confirmAssessment() {
  await submitReview('confirmed')
}

async function adjustAssessment() {
  await submitReview('adjusted')
}

async function submitReview(reviewStatus: Extract<AssessmentReviewStatus, 'confirmed' | 'adjusted'>) {
  clearMessages()
  if (!selectedPatientId.value || !selectedAssessment.value) {
    formError.value = '请先选择一条评估记录。'
    return
  }
  const metrics = reviewStatus === 'adjusted' ? buildMetricPayload() : null
  if (reviewStatus === 'adjusted' && !metrics) return
  reviewSubmitting.value = true
  try {
    const reviewed = await therapistApi.reviewAssessment(selectedPatientId.value, selectedAssessment.value.id, {
      review_status: reviewStatus,
      metrics,
      notes: systemNotes.value.trim() || null,
      therapist_notes: reviewNotes.value.trim() || null
    })
    formSuccess.value = reviewStatus === 'confirmed' ? '自动评估已确认。' : '评估修正已保存。'
    await refreshAfterReview(reviewed.id)
  } catch (err) {
    formError.value = toUserMessage(err, '复核提交失败')
  } finally {
    reviewSubmitting.value = false
  }
}

async function refreshAfterReview(assessmentId: string) {
  const [nextPatients, historyData, compareData] = await Promise.all([
    therapistApi.patients(),
    therapistApi.assessmentHistory(selectedPatientId.value),
    therapistApi.assessmentCompare(selectedPatientId.value)
  ])
  patients.value = nextPatients.sort((left, right) => right.pending_review_count - left.pending_review_count)
  history.value = historyData
  compare.value = compareData
  selectedAssessmentId.value = assessmentId
  syncReviewForm()
}

function buildMetricPayload(): Record<string, number> | null {
  const metrics: Record<string, number> = {}
  for (const [key, rawValue] of Object.entries(metricEdits.value)) {
    const value = Number(rawValue)
    if (!Number.isFinite(value)) {
      formError.value = `${metricDefinition(key)?.label || key} 需要填写数字。`
      return null
    }
    metrics[key] = value
  }
  return metrics
}

function clearMessages() {
  formError.value = ''
  formSuccess.value = ''
}

function recordMetricLine(item: AssessmentSession) {
  const metrics = item.metrics
  const accuracy = metrics.script_accuracy == null ? '--' : `${valueOrDash(metrics.script_accuracy)}%`
  const errors = metrics.error_count == null ? '--' : `${valueOrDash(metrics.error_count)} 次`
  const rate = metrics.speech_rate == null ? '--' : `${valueOrDash(metrics.speech_rate)} 字/min`
  return `完成度 ${accuracy} / 错误 ${errors} / 语速 ${rate}`
}

function assessmentTypeLabel(value: AssessmentType) {
  return assessmentTypeOptions.find((item) => item.value === value)?.label || value
}

function reviewStatusLabel(value: AssessmentReviewStatus) {
  const labels: Record<AssessmentReviewStatus, string> = {
    auto_generated: '系统生成',
    pending_review: '待复核',
    confirmed: '已确认',
    adjusted: '已修正'
  }
  return labels[value]
}

function sourceLabel(value: EvaluationSource) {
  const labels: Record<EvaluationSource, string> = {
    mock_ai: '系统自动评估',
    system_rule: '系统规则评估',
    provider_ai: '外部模型评估',
    human: '人工记录',
    clinician: '治疗师记录'
  }
  return labels[value]
}

function metricTone(key: string, value: number) {
  if (isProcessMetricKey(key)) return processMetricTone(key, value)
  return 'neutral'
}

function metricBrief(key: string, value: number) {
  if (isProcessMetricKey(key)) return processMetricBrief(key, value)
  return '可作为阶段参考'
}

function summaryForAccuracy(value?: number) {
  if (value == null) return ''
  return value >= 90 ? '表达完整度较好' : '表达完整度仍需训练'
}

function summaryForErrors(value?: number) {
  if (value == null) return ''
  return value <= 1 ? '明显错误较少' : '错误次数需要留意'
}

function summaryForSpeechRate(value?: number) {
  if (value == null) return ''
  if (value < 180) return '说话节奏偏慢'
  if (value > 240) return '说话节奏偏快'
  return '说话节奏稳定'
}

function summaryForLoudness(value?: number) {
  if (value == null) return ''
  if (value < -35) return '声音偏轻'
  if (value > -12) return '声音偏响'
  return '声音状态稳定'
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function shortId(value: string) {
  return value.slice(0, 8)
}

function valueOrDash(value: number | null | undefined) {
  if (value == null) return '--'
  return formatMetricValue(value)
}
</script>
