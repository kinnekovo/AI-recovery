<template>
  <article class="agent-card">
    <div class="avatar-mark">{{ agent.name.slice(0, 1) }}</div>
    <div>
      <h3>{{ agent.name }}</h3>
      <p>{{ agent.relationship }} · {{ styleText }}</p>
      <div class="chip-row">
        <span class="chip" :class="{ ok: agent.tencent_avatar_status === 'ready' }">{{ avatarStatusText }}</span>
        <span v-if="agent.voice_external_id" class="chip ok">专属声音已就绪</span>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Agent } from '@/types/api'

const props = defineProps<{ agent: Agent }>()
const styleText = computed(() => props.agent.personality_style || '温柔鼓励')
const avatarStatusText = computed(() => ({
  pending: '照片数字人未提交',
  detecting: '正在检测照片',
  training: '正在生成数字人',
  ready: '照片数字人已就绪',
  failed: '照片数字人生成失败',
}[props.agent.tencent_avatar_status] || '照片形象已保存'))
</script>
