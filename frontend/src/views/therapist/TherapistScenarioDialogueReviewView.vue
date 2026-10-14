<template>
  <section class="page-stack therapist-dialogue-review">
    <div class="page-heading">
      <span class="kicker">场景表达复核</span>
      <h1>逐轮确认沟通证据</h1>
      <p>{{ dialogue?.communication_goal || '加载本次沟通目标中。' }}</p>
    </div>
    <p v-if="loading" class="success-text">正在加载完整对话。</p><p v-if="error" class="error-text">{{ error }}</p>
    <template v-if="dialogue">
      <section class="therapist-dialogue-transcript" aria-label="完整对话">
        <article v-for="turn in dialogue.turns" :key="turn.turn_index" :class="['dialogue-turn', turn.speaker]">
          <strong>{{ turn.speaker === 'agent' ? '数字人' : '患者' }} · 第 {{ turn.turn_index }} 轮</strong>
          <p>{{ turn.text }}</p>
          <AudioPlayback v-if="turn.audio_file_id" :src="`/api/files/${turn.audio_file_id}/content`" compact />
        </article>
      </section>
      <section class="legacy-review-notice" aria-label="旧复核入口迁移提示">
        <div><strong>此处仅保留历史对话查看</strong><p>人工确认、证据修正与阶段决定已统一到待复核工作流，不再通过手写 JSON 修改旧评估记录。</p></div>
        <RouterLink class="v2-button primary" to="/therapist/reviews">打开待复核队列</RouterLink>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import { therapistApi } from '@/api/therapist'
import type { TherapistScenarioDialogue } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute(); const dialogue = ref<TherapistScenarioDialogue | null>(null); const loading = ref(true); const error = ref('')
onMounted(async () => { try { dialogue.value = await therapistApi.scenarioDialogue(String(route.params.dialogueId)) } catch (err) { error.value = toUserMessage(err, '无法读取场景对话') } finally { loading.value = false } })
</script>
