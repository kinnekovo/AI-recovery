<template>
  <div class="audio-playback" :class="{ compact }">
    <audio v-if="objectUrl" ref="audioElement" :src="objectUrl" controls></audio>
    <span v-else>{{ loading ? '正在准备录音' : error || '暂无录音' }}</span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { http } from '@/api/http'
import { toUserMessage } from '@/utils/errors'

const props = defineProps<{ src: string | null | undefined; compact?: boolean }>()
const objectUrl = ref('')
const audioElement = ref<HTMLAudioElement | null>(null)
const loading = ref(false)
const error = ref('')

watch(
  () => props.src,
  async (src) => {
    revokeObjectUrl()
    error.value = ''
    if (!src) return
    loading.value = true
    try {
      const url = src.startsWith('/api') ? src.slice(4) : src
      const response = await http.get<Blob>(url, { responseType: 'blob' })
      objectUrl.value = URL.createObjectURL(response.data)
    } catch (err) {
      error.value = toUserMessage(err, '录音加载失败')
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

function revokeObjectUrl() {
  if (!objectUrl.value) return
  URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = ''
}

onBeforeUnmount(revokeObjectUrl)

function seek(seconds: number) {
  if (!audioElement.value || !Number.isFinite(seconds)) return
  audioElement.value.currentTime = Math.max(0, seconds)
  void audioElement.value.play()
}

defineExpose({ seek })
</script>
