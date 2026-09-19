<template>
  <section class="page-stack ability-page">
    <div class="page-heading split">
      <div>
        <span class="kicker">能力画像</span>
        <h1>了解现在适合怎么练</h1>
        <p>系统会结合最近训练和治疗师复核结果，整理出当前适合的练习方向。</p>
      </div>
      <RouterLink class="primary-link" to="/training">继续训练</RouterLink>
    </div>

    <p v-if="loading" class="success-text">正在整理能力画像。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="profile" class="ability-hero">
      <div>
        <span>当前建议</span>
        <strong>{{ patientLevelLabel }}</strong>
        <p>{{ profile.recommendation }}</p>
      </div>
      <div class="confidence-box">
        <strong>{{ confidencePercent }}%</strong>
        <span>画像可信度</span>
      </div>
    </section>

    <section v-if="profile" class="ability-grid">
      <article class="ability-panel">
        <div class="panel-heading">
          <div>
            <h2>最近状态</h2>
            <p>这些是系统整理后的练习状态。</p>
          </div>
        </div>
        <div class="ability-metrics">
          <div v-for="item in metricCards" :key="item.key" class="ability-metric">
            <span>{{ item.value }}</span>
            <p>{{ item.label }}</p>
          </div>
        </div>
      </article>

      <article class="ability-panel">
        <div class="panel-heading">
          <div>
            <h2>系统小结</h2>
            <p>用简单的话说明最近练习情况。</p>
          </div>
        </div>
        <div class="patient-advice">
          <strong>{{ summaryTitle }}</strong>
          <p>{{ profile.assessment_summary }}</p>
        </div>
      </article>
    </section>

    <section v-if="profile" class="ability-panel">
      <div class="panel-heading">
        <div>
          <h2>依据</h2>
          <p>画像会随着训练次数和治疗师复核逐渐稳定。</p>
        </div>
      </div>
      <div class="evidence-row">
        <span>最近训练 {{ profile.evidence.recent_attempt_count || 0 }} 次</span>
        <span>治疗师复核 {{ profile.evidence.reviewed_assessment_count || 0 }} 条</span>
        <span>更新于 {{ dateTimeLabel(profile.updated_at) }}</span>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { profilesApi } from '@/api/profiles'
import { loudnessBand } from '@/config/algorithmThresholds'
import type { AbilityProfile } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const profile = ref<AbilityProfile | null>(null)
const loading = ref(true)
const error = ref('')

const confidencePercent = computed(() => Math.round((profile.value?.confidence || 0) * 100))

const patientLevelLabel = computed(() => {
  if (!profile.value) return '--'
  const content = profile.value.current_content_level
  const autonomy = profile.value.current_autonomy_level
  if (content === 'L1') return '先练熟悉短句'
  if (content === 'L2') return '适合短句稳定表达'
  if (content === 'L3') return '可以增加连续表达'
  if (content === 'L4') return '可以尝试更长表达'
  return `${content} / ${autonomy}`
})

const summaryTitle = computed(() => {
  if (!profile.value) return '继续训练'
  if (profile.value.confidence < 0.45) return '还需要更多练习数据'
  return '已形成初步画像'
})

const metricCards = computed(() => {
  const data = profile.value
  return [
    {
      key: 'accuracy',
      label: '表达完整度',
      value: data?.avg_script_accuracy_recent == null ? '--' : `${formatNumber(data.avg_script_accuracy_recent)}%`
    },
    {
      key: 'errors',
      label: '需要留意',
      value: data?.avg_error_count_recent == null ? '--' : `${formatNumber(data.avg_error_count_recent)}次`
    },
    {
      key: 'pace',
      label: '说话节奏',
      value: data?.avg_speech_rate_recent == null ? '--' : paceLabel(data.avg_speech_rate_recent)
    },
    {
      key: 'voice',
      label: '声音状态',
      value: data?.avg_loudness_recent == null ? '--' : loudnessLabel(data.avg_loudness_recent)
    }
  ]
})

onMounted(loadProfile)

async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    profile.value = await profilesApi.ability()
  } catch (err) {
    error.value = toUserMessage(err, '能力画像加载失败')
  } finally {
    loading.value = false
  }
}

function paceLabel(value: number) {
  if (value < 180) return '偏慢'
  if (value > 240) return '偏快'
  return '稳定'
}

function loudnessLabel(value: number) {
  if (loudnessBand(value) === 'low') return '偏轻'
  if (loudnessBand(value) === 'high') return '偏响'
  return '稳定'
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
