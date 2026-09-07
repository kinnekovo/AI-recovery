<template>
  <section class="avatar-coach-panel" :class="[`state-${snapshot.state}`, { compact }]">
    <div class="avatar-stage" aria-hidden="true">
      <div class="avatar-presence-ring"></div>
      <div v-if="avatarObjectUrl" class="avatar-photo-frame">
        <img :src="avatarObjectUrl" alt="" />
        <i class="avatar-photo-mouth" :class="{ open: snapshot.mouthOpen || snapshot.state === 'speaking' }"></i>
      </div>
      <div v-else class="avatar-head">
        <span class="avatar-hair"></span>
        <span class="avatar-face">
          <i class="avatar-eye left"></i>
          <i class="avatar-eye right"></i>
          <i class="avatar-mouth" :class="{ open: snapshot.mouthOpen || snapshot.state === 'speaking' }"></i>
        </span>
        <span class="avatar-shoulder"></span>
      </div>
      <div class="avatar-state-bars">
        <i></i>
        <i></i>
        <i></i>
      </div>
    </div>

    <div class="avatar-copy" aria-live="polite">
      <span class="avatar-kicker">{{ providerLabel }}</span>
      <h2>{{ title }}</h2>
      <p>{{ snapshot.line }}</p>
      <p class="avatar-action-hint">{{ actionHint }}</p>
      <div class="avatar-status-row">
        <span :class="`status-${snapshot.state}`">{{ stateLabel }}</span>
        <span>{{ capabilityLabel }}</span>
      </div>
      <slot name="actions"></slot>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { http } from '@/api/http'
import type { AvatarRuntimeSnapshot } from '@/avatar/types'

const props = defineProps<{
  snapshot: AvatarRuntimeSnapshot
  title?: string
  compact?: boolean
  avatarUrl?: string | null
}>()

const avatarObjectUrl = ref('')
const title = computed(() => props.title || '数字人陪练')
const providerLabel = computed(() => (props.snapshot.provider === 'static_2d' ? '2D Avatar Runtime' : props.snapshot.provider))
const capabilityLabel = computed(() => (props.snapshot.canSpeak ? '语音引导已启用' : '文字引导'))
const stateLabel = computed(() => {
  const labels: Record<AvatarRuntimeSnapshot['state'], string> = {
    idle: '等待开始',
    speaking: '正在示范',
    listening: '正在听你说',
    thinking: '正在分析',
    encouraging: '鼓励陪练',
    error: '需要重试'
  }
  return labels[props.snapshot.state]
})
const actionHint = computed(() => {
  const hints: Record<AvatarRuntimeSnapshot['state'], string> = {
    idle: '可以点击说明或示范，准备好后再开始录音。',
    speaking: '先听完这一句，结束后再跟着练。',
    listening: '现在轮到你说，慢慢来，把句子说完整。',
    thinking: '请稍等，系统正在整理这次训练结果。',
    encouraging: '这一小步已经完成，可以继续下一项。',
    error: '这一步没有成功，可以重试或刷新当前页面。'
  }
  return hints[props.snapshot.state]
})

watch(
  () => props.avatarUrl,
  async (src) => {
    revokeAvatarObjectUrl()
    if (!src) return
    try {
      const url = src.startsWith('/api') ? src.slice(4) : src
      const response = await http.get<Blob>(url, { responseType: 'blob' })
      avatarObjectUrl.value = URL.createObjectURL(response.data)
    } catch {
      avatarObjectUrl.value = ''
    }
  },
  { immediate: true }
)

function revokeAvatarObjectUrl() {
  if (!avatarObjectUrl.value) return
  URL.revokeObjectURL(avatarObjectUrl.value)
  avatarObjectUrl.value = ''
}

onBeforeUnmount(revokeAvatarObjectUrl)
</script>
