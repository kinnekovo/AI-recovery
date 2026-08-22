<template>
  <section class="avatar-coach-panel" :class="[`state-${snapshot.state}`, { compact }]">
    <div class="avatar-stage" aria-hidden="true">
      <div class="avatar-presence-ring"></div>
      <div class="avatar-head">
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

    <div class="avatar-copy">
      <span class="avatar-kicker">{{ providerLabel }}</span>
      <h2>{{ title }}</h2>
      <p>{{ snapshot.line }}</p>
      <div class="avatar-status-row">
        <span>{{ stateLabel }}</span>
        <span>{{ capabilityLabel }}</span>
      </div>
      <slot name="actions"></slot>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AvatarRuntimeSnapshot } from '@/avatar/types'

const props = defineProps<{
  snapshot: AvatarRuntimeSnapshot
  title?: string
  compact?: boolean
}>()

const title = computed(() => props.title || '数字人陪练')
const providerLabel = computed(() => (props.snapshot.provider === 'static_2d' ? '2D Avatar Runtime' : props.snapshot.provider))
const capabilityLabel = computed(() => (props.snapshot.canSpeak ? '语音引导已启用' : '文字引导'))
const stateLabel = computed(() => {
  const labels: Record<AvatarRuntimeSnapshot['state'], string> = {
    idle: '准备中',
    speaking: '正在示范',
    listening: '正在听你说',
    thinking: '正在分析',
    encouraging: '鼓励陪练',
    error: '需要重试'
  }
  return labels[props.snapshot.state]
})
</script>
