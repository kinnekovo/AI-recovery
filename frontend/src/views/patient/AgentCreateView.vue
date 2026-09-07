<template>
  <section class="page-stack narrow">
    <div class="page-heading">
      <span class="kicker">创建陪伴者</span>
      <h1>上传熟悉的人物形象和声音样本</h1>
      <p>第一阶段会记录轻量授权确认，并使用 Mock 服务生成 voice_id 与欢迎语音。</p>
    </div>
    <form class="form-panel" @submit.prevent="submit">
      <label>名称<input v-model="form.name" placeholder="妈妈" /></label>
      <label>关系<input v-model="form.relationship" placeholder="母亲" /></label>
      <label>陪伴风格<input v-model="form.personality_style" placeholder="温柔鼓励" /></label>
      <label>头像文件<input type="file" accept="image/*" @change="avatar = pickFile($event)" /></label>
      <label>声音样本<input type="file" accept="audio/*" @change="voice = pickFile($event)" /></label>
      <label class="check-line">
        <input v-model="consent" type="checkbox" />
        已确认形象和声音样本获得授权，仅用于康复训练
      </label>
      <p v-if="error" class="error-text">{{ error }}</p>
      <p v-if="welcomeUrl" class="success-text">欢迎语音已生成：{{ welcomeUrl }}</p>
      <AppButton variant="primary" :loading="loading">创建并生成</AppButton>
    </form>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import { agentsApi } from '@/api/agents'
import { toUserMessage } from '@/utils/errors'

const router = useRouter()
const form = ref({ name: '', relationship: '', personality_style: '温柔鼓励' })
const avatar = ref<File | null>(null)
const voice = ref<File | null>(null)
const consent = ref(true)
const loading = ref(false)
const error = ref('')
const welcomeUrl = ref('')

function pickFile(event: Event): File | null {
  const input = event.target as HTMLInputElement
  return input.files?.[0] || null
}

async function submit() {
  error.value = ''
  if (!consent.value) {
    error.value = '请先确认授权'
    return
  }
  loading.value = true
  try {
    const agent = await agentsApi.create({
      ...form.value,
      image_consent_confirmed: true,
      voice_consent_confirmed: true
    })
    if (avatar.value) await agentsApi.uploadAvatar(agent.id, avatar.value)
    if (voice.value) await agentsApi.uploadVoice(agent.id, voice.value)
    const welcome = await agentsApi.generateWelcome(agent.id)
    welcomeUrl.value = welcome.audio_url
    await agentsApi.setCurrent(agent.id)
    router.push('/agent/list')
  } catch (err) {
    error.value = toUserMessage(err, '创建失败')
  } finally {
    loading.value = false
  }
}
</script>
