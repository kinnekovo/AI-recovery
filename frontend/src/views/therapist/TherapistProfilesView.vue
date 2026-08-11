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
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { therapistApi } from '@/api/therapist'
import type { AbilityProfile, TherapistPatient } from '@/types/api'

const patients = ref<TherapistPatient[]>([])
const selectedPatientId = ref('')
const ability = ref<AbilityProfile | null>(null)
const loading = ref(true)
const loadingProfile = ref(false)
const pageError = ref('')

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
  pageError.value = ''
  try {
    ability.value = await therapistApi.abilityProfile(selectedPatientId.value)
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '能力画像加载失败'
  } finally {
    loadingProfile.value = false
  }
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
