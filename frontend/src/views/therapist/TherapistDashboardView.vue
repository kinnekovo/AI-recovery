<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">治疗师端</span>
      <h1>试用质控看板</h1>
      <p>先看训练完成、录音和外部服务是否稳定，再进入患者记录做复核。</p>
    </div>

    <p v-if="loading" class="success-text">正在加载试用质控数据。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="quality" class="therapist-panel trial-quality-panel">
      <div class="panel-heading">
        <div>
          <h2>整体运行情况</h2>
          <p>{{ qualitySummary }}</p>
        </div>
      </div>
      <div class="trial-quality-grid">
        <div v-for="item in qualityCards" :key="item.label" class="trial-quality-card" :class="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.hint }}</p>
        </div>
      </div>
    </section>

    <section class="role-boundary-panel">
      <h2>治疗师端职责</h2>
      <div class="boundary-list">
        <RouterLink to="/therapist/profiles">查看患者训练记录</RouterLink>
        <RouterLink to="/therapist/assessments">复核阶段评估</RouterLink>
        <span>维护训练建议</span>
      </div>
      <p>患者端只展示简化练习反馈；治疗师端保留完整过程指标、质控信息和阶段评估。</p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { therapistApi } from '@/api/therapist'
import type { TherapistTrialQuality } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const quality = ref<TherapistTrialQuality | null>(null)
const loading = ref(true)
const error = ref('')

const qualitySummary = computed(() => {
  if (!quality.value) return ''
  if (quality.value.training_session_count === 0) return '还没有训练会话，先完成患者端试用后再观察质量。'
  if (quality.value.low_quality_rate >= 0.25 || quality.value.missing_audio_rate >= 0.15) return '当前试用主要风险来自录音完成度或录音质量。'
  if (quality.value.provider_failure_count > 0) return '外部服务出现过失败，建议检查 ASR/TTS 等 provider 配置。'
  return '训练、录音和分析流程整体稳定，可以继续扩大试用样本。'
})

const qualityCards = computed(() => {
  if (!quality.value) return []
  return [
    {
      label: '患者数',
      value: String(quality.value.patient_count),
      hint: '已进入系统的患者账号。',
      tone: 'neutral'
    },
    {
      label: '训练完成率',
      value: percent(quality.value.completion_rate),
      hint: `${quality.value.completed_session_count}/${quality.value.training_session_count} 组训练已完成。`,
      tone: quality.value.completion_rate >= 0.75 ? 'good' : 'watch'
    },
    {
      label: '录音缺失率',
      value: percent(quality.value.missing_audio_rate),
      hint: `${quality.value.missing_audio_count}/${quality.value.attempt_count} 次尝试缺少录音。`,
      tone: quality.value.missing_audio_rate <= 0.1 ? 'good' : 'watch'
    },
    {
      label: '低质量录音',
      value: percent(quality.value.low_quality_rate),
      hint: `${quality.value.low_quality_attempt_count} 次录音过短或过轻。`,
      tone: quality.value.low_quality_rate <= 0.2 ? 'good' : 'watch'
    },
    {
      label: '分析失败',
      value: String(quality.value.failed_analysis_count),
      hint: '评分流程未完成的次数。',
      tone: quality.value.failed_analysis_count === 0 ? 'good' : 'watch'
    },
    {
      label: '外部服务失败',
      value: String(quality.value.provider_failure_count),
      hint: 'ASR 等 provider fallback 或异常次数。',
      tone: quality.value.provider_failure_count === 0 ? 'good' : 'watch'
    }
  ]
})

onMounted(async () => {
  try {
    quality.value = await therapistApi.trialQuality()
  } catch (err) {
    error.value = toUserMessage(err, '试用质控数据加载失败')
  } finally {
    loading.value = false
  }
})

function percent(value: number) {
  return `${Math.round(value * 1000) / 10}%`
}
</script>
