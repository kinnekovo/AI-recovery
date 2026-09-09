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
      <section class="form-panel">
        <h2>修正自动证据</h2>
        <p>只填写确有原话或音频依据的更正；保存后会留下复核人和时间。</p>
        <label>证据修正（JSON）<textarea v-model="overridesText" aria-describedby="override-help" /></label>
        <small id="override-help">示例：{&quot;request&quot;: {&quot;status&quot;: &quot;supported&quot;, &quot;turn_index&quot;: 3}}</small>
        <label>治疗师备注<textarea v-model="notes" placeholder="记录漏识别、误识别或下一轮训练重点。" /></label>
        <AppButton variant="primary" :loading="saving" @click="save">保存复核</AppButton>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import { therapistApi } from '@/api/therapist'
import type { TherapistScenarioDialogue } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute(); const dialogue = ref<TherapistScenarioDialogue | null>(null); const loading = ref(true); const saving = ref(false); const error = ref(''); const notes = ref(''); const overridesText = ref('{}')
onMounted(async () => { try { dialogue.value = await therapistApi.scenarioDialogue(String(route.params.dialogueId)) } catch (err) { error.value = toUserMessage(err, '无法读取场景对话') } finally { loading.value = false } })
async function save() { try { const evidence_overrides = JSON.parse(overridesText.value); saving.value = true; await therapistApi.saveScenarioDialogueReview(String(route.params.dialogueId), { evidence_overrides, review_notes: notes.value || null, review_status: 'confirmed' }) } catch (err) { error.value = err instanceof SyntaxError ? '证据修正必须是有效的 JSON。' : toUserMessage(err, '复核保存失败') } finally { saving.value = false } }
</script>
