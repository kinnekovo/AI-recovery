<template>
  <section class="page-stack system-status-page">
    <div class="page-heading therapist-review-heading">
      <span class="kicker">系统状态</span>
      <h1>上线前先看这一屏</h1>
      <p>数据库、文件目录和 AI provider 的当前模式集中展示，便于管理员判断系统是否可以接收试用。</p>
    </div>

    <p v-if="loading" class="success-text">正在读取系统状态。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="status" class="system-status-grid" aria-label="系统状态">
      <article class="therapist-panel system-status-card" :class="toneFor(status.database.status)">
        <div class="system-status-icon">
          <Database :size="24" aria-hidden="true" />
        </div>
        <div>
          <span>数据库</span>
          <strong>{{ statusLabel(status.database.status) }}</strong>
          <p>{{ status.database.status === 'ok' ? '数据库连接可用，核心接口可以读写数据。' : '数据库暂不可用，请检查 PostgreSQL 和 DATABASE_URL。' }}</p>
        </div>
      </article>

      <article class="therapist-panel system-status-card" :class="toneFor(status.storage.status)">
        <div class="system-status-icon">
          <HardDrive :size="24" aria-hidden="true" />
        </div>
        <div>
          <span>文件存储</span>
          <strong>{{ storageLabel }}</strong>
          <p>{{ status.storage.root }}</p>
        </div>
      </article>

      <article class="therapist-panel system-status-card system-status-wide">
        <div class="system-status-icon">
          <Activity :size="24" aria-hidden="true" />
        </div>
        <div>
          <span>总体状态</span>
          <strong>{{ overallReady ? '可进入试用' : '需要处理配置' }}</strong>
          <p>{{ overallReady ? '基础服务状态正常，真实 provider 仍建议通过训练 smoke 再确认。' : '存在不可用配置，请先处理数据库、存储或 provider 缺失项。' }}</p>
        </div>
      </article>
    </section>

    <section v-if="status" class="therapist-panel provider-status-panel">
      <div class="panel-heading">
        <div>
          <span>Provider 模式</span>
          <h2>外部能力状态</h2>
        </div>
        <button type="button" @click="loadStatus">
          <RefreshCw :size="16" aria-hidden="true" />
          刷新
        </button>
      </div>

      <div class="provider-status-list">
        <article v-for="provider in providerItems" :key="provider.name" class="provider-status-row" :class="provider.status">
          <div class="provider-status-mark">
            <CheckCircle2 v-if="provider.ready" :size="20" aria-hidden="true" />
            <ShieldAlert v-else :size="20" aria-hidden="true" />
          </div>
          <div>
            <strong>{{ providerName(provider.name) }}</strong>
            <p>{{ provider.message }}</p>
            <small v-if="provider.missing_env.length">缺失：{{ provider.missing_env.join('、') }}</small>
          </div>
          <span>{{ provider.provider }} · {{ providerStatusLabel(provider.status) }}</span>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, CheckCircle2, Database, HardDrive, RefreshCw, ShieldAlert } from 'lucide-vue-next'
import { healthApi } from '@/api/health'
import type { HealthStatus, ProviderHealthStatus } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const status = ref<HealthStatus | null>(null)
const loading = ref(true)
const error = ref('')

const providerItems = computed<ProviderHealthStatus[]>(() => Object.values(status.value?.providers || {}))
const storageLabel = computed(() => {
  if (!status.value) return ''
  if (!status.value.storage.exists) return '目录缺失'
  if (!status.value.storage.is_dir) return '路径异常'
  return '目录可用'
})
const overallReady = computed(() => {
  if (!status.value) return false
  return (
    status.value.database.status === 'ok' &&
    status.value.storage.status === 'ok' &&
    providerItems.value.every((item) => item.ready)
  )
})

onMounted(loadStatus)

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    status.value = await healthApi.status()
  } catch (err) {
    error.value = toUserMessage(err, '系统状态读取失败')
  } finally {
    loading.value = false
  }
}

function toneFor(value: string) {
  return value === 'ok' || value === 'configured' ? 'ok' : 'warn'
}

function statusLabel(value: string) {
  if (value === 'ok') return '连接正常'
  if (value === 'missing') return '目录缺失'
  return '暂不可用'
}

function providerStatusLabel(value: string) {
  if (value === 'ok') return 'mock 可用'
  if (value === 'configured') return '已配置'
  if (value === 'config_missing') return '配置缺失'
  return value
}

function providerName(value: string) {
  const names: Record<string, string> = {
    speech_eval: '训练评分',
    asr: '语音识别',
    acoustic: '声学分析',
    tts: '数字人口播',
    llm_feedback: '语言反馈'
  }
  return names[value] || value
}
</script>
