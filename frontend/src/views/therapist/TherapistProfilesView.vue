<template>
  <section class="page-stack therapist-assessment-page therapist-workbench-page">
    <div class="page-heading therapist-review-heading">
      <div>
        <span class="kicker">治疗师工作台</span>
        <h1>看训练，看趋势，必要时调整建议</h1>
        <p>算法继续负责生成训练推荐；治疗师主要观察患者表现，并用自然语言补充下一次训练重点。</p>
      </div>
      <button class="app-button secondary" type="button" :disabled="loadingPatientData" @click="reloadSelected">
        刷新数据
      </button>
    </div>

    <p v-if="loading" class="success-text">正在加载患者列表。</p>
    <p v-if="pageError" class="error-text">{{ pageError }}</p>

    <section class="therapist-workbench-grid">
      <article class="therapist-panel patient-queue-panel">
        <div class="panel-heading">
          <div>
            <h2>患者</h2>
            <p>选择后查看训练记录与趋势。</p>
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
            <span>{{ patient.training_status || '训练状态待更新' }}</span>
            <small>{{ patient.latest_assessment_at ? `最近评估：${dateLabel(patient.latest_assessment_at)}` : '暂无阶段评估' }}</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <p>暂时没有患者账号。</p>
        </div>
      </article>

      <div class="therapist-main-flow">
        <article class="therapist-panel training-records-panel">
          <div class="panel-heading">
            <div>
              <h2>每次训练记录与评分</h2>
              <p>{{ selectedPatient ? `${selectedPatient.username} 最近 ${records.length} 次训练反馈` : '选择患者后显示' }}</p>
            </div>
          </div>

          <div v-if="loadingPatientData" class="success-text">正在汇总训练记录。</div>
          <div v-else-if="records.length" class="therapist-record-list">
            <article v-for="record in records" :key="record.attempt_id" class="training-record-row">
              <div class="record-score-block" :class="{ empty: record.overall_score == null }">
                <strong>{{ record.overall_score ?? '--' }}</strong>
                <span>总分</span>
              </div>
              <div class="record-main">
                <div class="record-topline">
                  <strong>{{ record.task_title }}</strong>
                  <span>{{ dateTimeLabel(record.created_at) }}</span>
                </div>
                <p>{{ record.target_text }}</p>
                <small>{{ record.feedback_summary }}</small>
                <div class="record-tags">
                  <span>{{ trainingTypeLabel(record.training_type) }}</span>
                  <span>{{ analysisStatusLabel(record.analysis_status) }}</span>
                  <span v-if="record.recommendation_source">{{ record.recommendation_matched ? '符合推荐' : '未按推荐' }}</span>
                </div>
              </div>
              <div class="record-metric-strip">
                <span>完整度 {{ metricValue(record.process_metrics.script_accuracy, '%') }}</span>
                <span>错误 {{ metricValue(record.process_metrics.error_count, '次') }}</span>
                <span>语速 {{ metricValue(record.process_metrics.speech_rate, '字/min') }}</span>
                <span>音量 {{ metricValue(record.process_metrics.loudness, 'dBA') }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">
            <p>暂无训练记录。患者完成一次训练并生成评分后，这里会自动出现。</p>
          </div>
        </article>

        <article class="therapist-panel">
          <div class="panel-heading">
            <div>
              <h2>训练得分趋势</h2>
              <p>{{ trends?.overall_summary || '按上次、三天、七天、三十天自动汇总。' }}</p>
            </div>
          </div>

          <div v-if="loadingPatientData" class="success-text">正在计算趋势。</div>
          <div v-else-if="trends" class="trend-window-grid">
            <section v-for="bucket in trends.buckets" :key="bucket.key" class="trend-window-card">
              <div>
                <span>{{ bucket.label }}</span>
                <strong>{{ scoreLabel(bucket.avg_overall_score) }}</strong>
              </div>
              <p>{{ bucket.summary }}</p>
              <div class="record-tags">
                <span>{{ bucket.attempt_count }} 次</span>
                <span>完整度 {{ metricValue(bucket.avg_script_accuracy, '%') }}</span>
                <span>错误 {{ metricValue(bucket.avg_error_count, '次') }}</span>
              </div>
            </section>
          </div>
          <div v-else class="empty-state">
            <p>暂无趋势数据。</p>
          </div>
        </article>
      </div>

      <aside class="therapist-side-flow">
        <article class="therapist-panel recommendation-note-panel">
          <div class="panel-heading">
            <div>
              <h2>自然语言调整推荐</h2>
              <p>这里不是复核算法，只是在必要时补充训练方向。</p>
            </div>
          </div>

          <div v-if="recommendation" class="algorithm-recommendation-box">
            <span>算法当前建议</span>
            <strong>{{ recommendation.headline }}</strong>
            <p>{{ recommendation.reason }}</p>
            <div class="record-tags">
              <span>{{ trainingTypeLabel(recommendation.recommended_type) }}</span>
              <span>{{ recommendation.suggested_minutes }} 分钟</span>
              <span>置信度 {{ Math.round(recommendation.confidence * 100) }}%</span>
            </div>
          </div>

          <form class="recommendation-note-form" @submit.prevent="saveNote">
            <label>
              给算法和患者端的补充说明
              <textarea
                v-model="noteText"
                maxlength="300"
                rows="7"
                placeholder="例如：这周先降低句子长度，重点练习慢一点说完整；如果连续两次错误少于 1 次，再切到场景表达。"
              ></textarea>
            </label>
            <div class="form-actions">
              <button class="app-button primary" type="submit" :disabled="savingNote || !selectedPatientId">
                {{ savingNote ? '保存中' : '保存调整说明' }}
              </button>
              <button class="app-button secondary" type="button" :disabled="savingNote" @click="clearNote">
                清空
              </button>
            </div>
            <p v-if="noteSaved" class="success-text">{{ noteSaved }}</p>
          </form>
        </article>

        <article class="therapist-panel compact-profile-panel">
          <div class="panel-heading">
            <div>
              <h2>能力概览</h2>
              <p>{{ ability ? `更新于 ${dateTimeLabel(ability.updated_at)}` : '选择患者后显示' }}</p>
            </div>
          </div>
          <div v-if="ability" class="compact-profile-grid">
            <div>
              <span>内容</span>
              <strong>{{ ability.current_content_level }}</strong>
            </div>
            <div>
              <span>自主</span>
              <strong>{{ ability.current_autonomy_level }}</strong>
            </div>
            <div>
              <span>置信</span>
              <strong>{{ Math.round(ability.confidence * 100) }}%</strong>
            </div>
          </div>
          <p v-if="ability" class="compact-profile-summary">{{ ability.assessment_summary }}</p>
        </article>
      </aside>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { therapistApi } from '@/api/therapist'
import type {
  AbilityProfile,
  TherapistPatient,
  TherapistTrainingRecord,
  TherapistTrainingTrends,
  TrainingRecommendation
} from '@/types/api'

const patients = ref<TherapistPatient[]>([])
const selectedPatientId = ref('')
const ability = ref<AbilityProfile | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const records = ref<TherapistTrainingRecord[]>([])
const trends = ref<TherapistTrainingTrends | null>(null)
const noteText = ref('')
const loading = ref(true)
const loadingPatientData = ref(false)
const savingNote = ref(false)
const pageError = ref('')
const noteSaved = ref('')

const selectedPatient = computed(() => patients.value.find((item) => item.user_id === selectedPatientId.value))

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
  loadingPatientData.value = true
  pageError.value = ''
  noteSaved.value = ''
  try {
    const [abilityResult, recommendationResult, recordsResult, trendsResult, noteResult] = await Promise.all([
      therapistApi.abilityProfile(selectedPatientId.value),
      therapistApi.trainingRecommendation(selectedPatientId.value),
      therapistApi.trainingRecords(selectedPatientId.value),
      therapistApi.trainingTrends(selectedPatientId.value),
      therapistApi.recommendationNote(selectedPatientId.value)
    ])
    ability.value = abilityResult
    recommendation.value = recommendationResult
    records.value = recordsResult
    trends.value = trendsResult
    noteText.value = noteResult.note || recommendationResult.therapist_notes || ''
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '患者训练数据加载失败'
  } finally {
    loadingPatientData.value = false
  }
}

async function saveNote() {
  if (!selectedPatientId.value) return
  savingNote.value = true
  noteSaved.value = ''
  pageError.value = ''
  try {
    const note = await therapistApi.saveRecommendationNote(selectedPatientId.value, {
      note: noteText.value.trim() || null
    })
    noteText.value = note.note || ''
    recommendation.value = await therapistApi.trainingRecommendation(selectedPatientId.value)
    noteSaved.value = note.note ? '调整说明已保存，后续推荐会带上这条治疗师提示。' : '调整说明已清空。'
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '调整说明保存失败'
  } finally {
    savingNote.value = false
  }
}

function clearNote() {
  noteText.value = ''
}

function trainingTypeLabel(type: string) {
  return type === 'scenario' ? '场景表达' : '跟读训练'
}

function analysisStatusLabel(status: string) {
  if (status === 'completed') return '已评分'
  if (status === 'failed') return '分析失败'
  return '分析中'
}

function metricValue(value: number | null | undefined, unit: string) {
  if (value == null) return '--'
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1)
  return `${text}${unit}`
}

function scoreLabel(value: number | null | undefined) {
  return value == null ? '--' : `${metricValue(value, '')} 分`
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
