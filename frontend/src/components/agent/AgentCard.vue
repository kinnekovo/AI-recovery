<template>
  <article class="agent-card">
    <div class="avatar-mark">{{ agent.name.slice(0, 1) }}</div>
    <div>
      <h3>{{ agent.name }}</h3>
      <p>{{ agent.relationship }} · {{ styleText }}</p>
      <div class="chip-row">
        <span class="chip" :class="{ ok: agent.voice_external_id }">voice_id</span>
        <span class="chip" :class="{ ok: agent.generation_status === 'ready' }">{{ agent.generation_status }}</span>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Agent } from '@/types/api'

const props = defineProps<{ agent: Agent }>()
const styleText = computed(() => props.agent.personality_style || '温柔鼓励')
</script>
