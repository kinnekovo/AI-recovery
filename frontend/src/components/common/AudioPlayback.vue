<template>
  <div class="audio-playback" :class="{ compact }">
    <audio v-if="objectUrl" :src="objectUrl" controls></audio>
    <span v-else>{{ loading ? '正在准备录音' : error || '暂无录音' }}</span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { http } from '@/api/http'

const props = defineProps<{ src: string | null | undefined; compact?: boolean }>()
const objectUrl = ref('')
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
      error.value = err instanceof Error ? err.message : '录音加载失败'
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
</script>
