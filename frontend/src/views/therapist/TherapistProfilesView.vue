<template>
  <section class="page-stack therapist-assessment-page">
    <div class="page-heading therapist-review-heading">
      <div>
        <span class="kicker">能力画像</span>
        <h1>患者当前能力状态</h1>
        <p>画像基于近期过程指标、自动评估和治疗师复核结果生成，用于后续训练推荐。</p>
      </div>
      <button class="app-button secondary" type="button" :disabled="loadingProfile" @click="reloadSelected">
        刷新画像
      </button>
    </div>

    <p v-if="loading" class="success-text">正在加载患者列表。</p>
    <p v-if="pageError" class="error-text">{{ pageError }}</p>

    <section class="therapist-profile-grid">
      <article class="therapist-panel patient-queue-panel">
        <div class="panel-heading">
          <div>
            <h2>患者</h2>
            <p>选择患者查看当前画像。</p>
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
            <span>{{ patient.pending_review_count ? '仍有评估待复核' : '复核状态稳定' }}</span>
            <small>{{ patient.latest_assessment_at ? `最近评估：${dateLabel(patient.latest_assessment_at)}` : '暂无自动评估' }}</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <p>暂时没有患者账号。</p>
        </div>
      </article>

      <article class="therapist-panel">
        <div class="panel-heading">
          <div>
            <h2>{{ selectedPatient?.username || '未选择患者' }}</h2>
            <p>{{ ability ? `更新于 ${dateTimeLabel(ability.updated_at)}` : '选择患者后显示画像' }}</p>
          </div>
        </div>

        <div v-if="loadingProfile" class="success-text">正在刷新能力画像。</div>
        <div v-else-if="ability" class="therapist-ability-detail">
          <div class="ability-level-row">
            <div>
              <span>内容难度</span>
              <strong>{{ ability.current_content_level }}</strong>
            </div>
            <div>
              <span>自主程度</span>
              <strong>{{ ability.current_autonomy_level }}</strong>
            </div>
            <div>
              <span>置信度</span>
              <strong>{{ Math.round(ability.confidence * 100) }}%</strong>
            </div>
          </div>

          <div class="metric-summary-grid">
            <div v-for="item in metricCards" :key="item.key" class="metric-summary-card" :class="item.tone">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}<small>{{ item.unit }}</small></strong>
              <p>{{ item.brief }}</p>
            </div>
          </div>

          <div class="system-note-box">
            <strong>画像摘要</strong>
            <p>{{ ability.assessment_summary }}</p>
          </div>

          <div class="auto-summary">
            <strong>下一步建议</strong>
            <p>{{ ability.recommendation }}</p>
          </div>

          <div class="evidence-row">
            <span>近期训练 {{ ability.evidence.recent_attempt_count || 0 }} 次</span>
            <span>已复核评估 {{ ability.evidence.reviewed_assessment_count || 0 }} 条</span>
            <span>{{ ability.evidence.latest_review_status || '暂无复核状态' }}</span>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>选择患者后会生成或刷新能力画像。</p>
        </div>
      </article>

      <article class="therapist-panel recommendation-review-panel">
        <div class="panel-heading">
          <div>
            <h2>推荐复核</h2>
            <p>{{ recommendation ? sourceLabel(recommendation.source, recommendation.review_status) : '选择患者后显示系统建议' }}</p>
          </div>
        </div>

        <div v-if="loadingRecommendation" class="success-text">正在生成训练推荐。</div>
        <form v-else-if="recommendation" class="recommendation-review-form" @submit.prevent="saveRecommendation">
          <label>
            推荐训练
            <select v-model="reviewForm.recommended_type">
              <option value="repeat">跟读训练</option>
              <option value="scenario">场景表达</option>
            </select>
          </label>
          <label>
            推荐标题
            <input v-model="reviewForm.headline" maxlength="80" />
          </label>
          <label>
            推荐原因
            <textarea v-model="reviewForm.reason" rows="4" maxlength="300"></textarea>
          </label>
          <label>
            今日关注点
            <textarea v-model="focusText" rows="4" maxlength="240"></textarea>
          </label>
          <label>
            建议时长
            <input v-model.number="reviewForm.suggested_minutes" type="number" min="5" max="30" />
          </label>
          <label>
            治疗师备注
            <textarea v-model="reviewForm.therapist_notes" rows="4" maxlength="300"></textarea>
          </label>

          <div class="recommendation-evidence">
            <span>画像等级 {{ recommendation.content_level }} / {{ recommendation.autonomy_level }}</span>
            <span>置信度 {{ Math.round(recommendation.confidence * 100) }}%</span>
            <span>{{ recommendation.task_template?.title || '暂无匹配模板' }}</span>
          </div>

          <div class="form-actions">
            <button class="app-button primary" type="submit" :disabled="savingRecommendation">
              {{ savingRecommendation ? '保存中' : '保存复核建议' }}
            </button>
            <button class="app-button secondary" type="button" :disabled="savingRecommendation" @click="resetRecommendationForm">
              恢复系统建议
            </button>
          </div>
          <p v-if="recommendationSaved" class="success-text">{{ recommendationSaved }}</p>
        </form>
        <div v-else class="empty-state">
          <p>选择患者后会显示系统推荐，并允许治疗师确认或调整。</p>
        </div>
      </article>

      <article class="therapist-panel recommendation-review-panel">
        <div class="panel-heading">
          <div>
            <h2>推荐后表现</h2>
            <p>查看患者从推荐入口开始训练后的完成情况和过程指标。</p>
          </div>
        </div>

        <div v-if="loadingEffects" class="success-text">正在加载推荐效果。</div>
        <div v-else-if="effects && effects.latest.length" class="recommendation-effect-list">
          <div class="recommendation-effect-summary">
            <span>推荐入口 {{ effects.total_recommended_sessions }} 次</span>
            <span>已完成 {{ effects.completed_recommended_sessions }} 次</span>
            <span>按建议类型 {{ effects.matched_sessions }} 次</span>
          </div>
          <div v-for="item in effects.latest" :key="item.session_id" class="recommendation-effect-row">
            <div>
              <strong>{{ item.recommendation_headline || trainingTypeLabel(item.training_type) }}</strong>
              <p>{{ item.summary }}</p>
              <small>{{ dateTimeLabel(item.created_at) }} · {{ sourceText(item.recommendation_source) }}</small>
            </div>
            <div class="recommendation-effect-metrics">
              <span>{{ item.recommendation_matched ? '按建议' : '改练其他' }}</span>
              <span>{{ item.status === 'completed' ? '已完成' : '未完成' }}</span>
              <span v-if="item.metrics.script_accuracy != null">完整度 {{ formatNumber(item.metrics.script_accuracy) }}%</span>
              <span v-if="item.metrics.error_count != null">错误 {{ formatNumber(item.metrics.error_count) }} 次</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>患者还没有从推荐入口开始训练。</p>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { therapistApi } from '@/api/therapist'
import type {
  AbilityProfile,
  RecommendationEffectSummary,
  TherapistPatient,
  TrainingRecommendation,
  TrainingRecommendationReviewPayload
} from '@/types/api'

const patients = ref<TherapistPatient[]>([])
const selectedPatientId = ref('')
const ability = ref<AbilityProfile | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const effects = ref<RecommendationEffectSummary | null>(null)
const loading = ref(true)
const loadingProfile = ref(false)
const loadingRecommendation = ref(false)
const loadingEffects = ref(false)
const savingRecommendation = ref(false)
const pageError = ref('')
const recommendationSaved = ref('')
const focusText = ref('')
const reviewForm = ref<TrainingRecommendationReviewPayload>({
  recommended_type: 'repeat',
  headline: '',
  reason: '',
  focus_points: [],
  suggested_minutes: 10,
  therapist_notes: ''
})

const selectedPatient = computed(() => patients.value.find((item) => item.user_id === selectedPatientId.value))

const metricCards = computed(() => {
  const data = ability.value
  return [
    metricCard('script_accuracy', '脚本完成度', data?.avg_script_accuracy_recent, '%'),
    metricCard('error_count', '错误次数', data?.avg_error_count_recent, '次'),
    metricCard('speech_rate', '说话速度', data?.avg_speech_rate_recent, '字/min'),
    metricCard('loudness', '声音响度', data?.avg_loudness_recent, 'dBA')
  ]
})

onMounted(async () => {
  try {
    patients.value = await therapistApi.patients()
    patients.value.sort((left, right) => right.pending_review_count - left.pending_review_count)
    if (patients.value[0]) await selectPatient(patients.value[0].user_id)
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '患者列表加载失败'
  } finally {
    loading.value = false
  }
})

async function selectPatient(patientUserId: string) {
  selectedPatientId.value = patientUserId
  await reloadSelected()
}

async function reloadSelected() {
  if (!selectedPatientId.value) return
  loadingProfile.value = true
  loadingRecommendation.value = true
  loadingEffects.value = true
  pageError.value = ''
  recommendationSaved.value = ''
  try {
    const [abilityResult, recommendationResult, effectsResult] = await Promise.all([
      therapistApi.abilityProfile(selectedPatientId.value),
      therapistApi.trainingRecommendation(selectedPatientId.value),
      therapistApi.recommendationEffects(selectedPatientId.value)
    ])
    ability.value = abilityResult
    recommendation.value = recommendationResult
    effects.value = effectsResult
    syncRecommendationForm(recommendationResult)
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '能力画像或训练推荐加载失败'
  } finally {
    loadingProfile.value = false
    loadingRecommendation.value = false
    loadingEffects.value = false
  }
}

async function saveRecommendation() {
  if (!selectedPatientId.value || !recommendation.value) return
  savingRecommendation.value = true
  pageError.value = ''
  recommendationSaved.value = ''
  try {
    const payload: TrainingRecommendationReviewPayload = {
      ...reviewForm.value,
      headline: reviewForm.value.headline.trim() || recommendation.value.headline,
      reason: reviewForm.value.reason.trim() || recommendation.value.reason,
      focus_points: focusText.value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean)
        .slice(0, 5),
      suggested_minutes: Math.max(5, Math.min(Number(reviewForm.value.suggested_minutes) || 10, 30)),
      therapist_notes: reviewForm.value.therapist_notes?.trim() || null
    }
    recommendation.value = await therapistApi.reviewTrainingRecommendation(selectedPatientId.value, payload)
    syncRecommendationForm(recommendation.value)
    recommendationSaved.value = '复核建议已保存，患者端会优先显示治疗师建议。'
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '训练推荐保存失败'
  } finally {
    savingRecommendation.value = false
  }
}

function resetRecommendationForm() {
  if (!selectedPatientId.value) return
  loadingRecommendation.value = true
  recommendationSaved.value = ''
  therapistApi
    .trainingRecommendation(selectedPatientId.value)
    .then((data) => {
      recommendation.value = data
      syncRecommendationForm(data)
    })
    .catch((err) => {
      pageError.value = err instanceof Error ? err.message : '系统推荐加载失败'
    })
    .finally(() => {
      loadingRecommendation.value = false
    })
}

function syncRecommendationForm(data: TrainingRecommendation) {
  reviewForm.value = {
    recommended_type: data.recommended_type,
    headline: data.headline,
    reason: data.reason,
    focus_points: data.focus_points,
    suggested_minutes: data.suggested_minutes,
    therapist_notes: data.therapist_notes || ''
  }
  focusText.value = data.focus_points.join('\n')
}

function sourceLabel(source: string, status: string) {
  if (source === 'therapist') return status === 'adjusted' ? '治疗师已调整，患者端正在使用此建议。' : '治疗师已确认，患者端正在使用此建议。'
  return '系统自动生成，等待治疗师确认或调整。'
}

function sourceText(source: string | null) {
  if (source === 'therapist') return '治疗师建议'
  if (source === 'system') return '系统建议'
  return '推荐入口'
}

function trainingTypeLabel(type: string) {
  return type === 'scenario' ? '场景表达' : '跟读训练'
}

function metricCard(key: string, label: string, value: number | null | undefined, unit: string) {
  return {
    key,
    label,
    value: value == null ? '--' : formatNumber(value),
    unit: value == null ? '' : unit,
    tone: value == null ? 'neutral' : metricTone(key, value),
    brief: value == null ? '暂无数据' : metricBrief(key, value)
  }
}

function metricTone(key: string, value: number) {
  if (key === 'script_accuracy') return value >= 90 ? 'good' : 'watch'
  if (key === 'error_count') return value <= 1 ? 'good' : 'watch'
  if (key === 'speech_rate') return value >= 180 && value <= 240 ? 'good' : 'watch'
  if (key === 'loudness') return value >= 60 && value <= 78 ? 'good' : 'watch'
  return 'neutral'
}

function metricBrief(key: string, value: number) {
  if (key === 'script_accuracy') return value >= 90 ? '完整度较好' : '完整度需关注'
  if (key === 'error_count') return value <= 1 ? '错误较少' : '错误偏多'
  if (key === 'speech_rate') return value < 180 ? '节奏偏慢' : value > 240 ? '节奏偏快' : '节奏稳定'
  if (key === 'loudness') return value < 60 ? '声音偏轻' : value > 78 ? '声音偏响' : '音量稳定'
  return '可作为参考'
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
