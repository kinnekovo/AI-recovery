<template>
  <section class="avatar-coach-panel" :class="[`state-${snapshot.state}`, { compact, immersive }]">
    <div class="avatar-stage" aria-hidden="true">
      <div class="avatar-presence-ring"></div>
      <video
        v-show="snapshot.provider === 'external_streaming'"
        :id="cloudContainerId"
        class="avatar-video avatar-cloud-video"
        autoplay
        :muted="false"
        playsinline
      ></video>
      <video
        v-if="snapshot.videoUrl && snapshot.provider !== 'external_streaming'"
        class="avatar-video"
        :src="snapshot.videoUrl"
        autoplay
        muted
        playsinline
      ></video>
      <div v-else-if="avatarObjectUrl" class="avatar-photo-frame" :style="avatarMotionStyle">
        <img class="avatar-photo-base" :src="avatarObjectUrl" alt="" />
        <span v-if="hasPhotoMouth" class="avatar-photo-mouth-region">
          <img :src="avatarObjectUrl" alt="" />
        </span>
      </div>
      <div v-else class="avatar-head">
        <span class="avatar-hair"></span>
        <span class="avatar-face">
          <i class="avatar-eye left"></i>
          <i class="avatar-eye right"></i>
          <i class="avatar-mouth" :class="{ open: snapshot.mouthOpen }"></i>
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
      <p v-if="snapshot.videoStatus === 'queued' || snapshot.videoStatus === 'running'" class="avatar-video-progress">
        动态形象正在生成，已等待 {{ snapshot.videoElapsedSeconds }} 秒。视频完成后将与语音同步播放。
      </p>
      <p v-else-if="snapshot.videoStatus === 'fallback' || snapshot.videoStatus === 'failed'" class="avatar-video-fallback">
        动态形象暂未就绪，本次已使用语音示范。
      </p>
      <slot name="actions"></slot>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { http } from '@/api/http'
import type { AvatarRuntimeSnapshot } from '@/avatar/types'
import type { PortraitAnimationConfig } from '@/avatar/face/portrait'

const props = defineProps<{
  snapshot: AvatarRuntimeSnapshot
  title?: string
  compact?: boolean
  immersive?: boolean
  avatarUrl?: string | null
  avatarAnimationConfig?: Record<string, unknown> | null
  cloudContainerId?: string
}>()

const avatarObjectUrl = ref('')
const title = computed(() => props.title || '数字人陪练')
const hasPhotoMouth = computed(() => {
  const config = props.avatarAnimationConfig as Partial<PortraitAnimationConfig> | null
  return Boolean(validAnchor(config?.mouth) && validAnchor(config?.crop))
})
const avatarMotionStyle = computed(() => {
  const config = props.avatarAnimationConfig as Partial<PortraitAnimationConfig> | null
  const mouth = config?.mouth
  const crop = config?.crop
  const energy = Math.max(0, Math.min(1, props.snapshot.mouthEnergy))
  const style: Record<string, string> = {
    '--avatar-mouth-energy': String(energy),
  }
  if (!validAnchor(mouth) || !validAnchor(crop)) return style
  const mouthX = (mouth.x + mouth.width / 2 - crop.x) / crop.width
  const mouthY = (mouth.y + mouth.height / 2 - crop.y) / crop.height
  const regionWidth = Math.max(0.16, Math.min(0.32, mouth.width / crop.width * 1.45))
  const regionHeight = Math.max(0.065, Math.min(0.14, mouth.height / crop.height * 1.7))
  return {
    ...style,
    '--avatar-mouth-x': `${Math.max(0, Math.min(1, mouthX)) * 100}%`,
    '--avatar-mouth-y': `${Math.max(0, Math.min(1, mouthY)) * 100}%`,
    '--avatar-mouth-region-width': `${regionWidth * 100}%`,
    '--avatar-mouth-region-height': `${regionHeight * 100}%`,
    '--avatar-mouth-source-width': `${100 / regionWidth}%`,
    '--avatar-mouth-source-height': `${100 / regionHeight}%`,
    '--avatar-mouth-source-left': `${-((mouthX - regionWidth / 2) / regionWidth) * 100}%`,
    '--avatar-mouth-source-top': `${-((mouthY - regionHeight / 2) / regionHeight) * 100}%`,
  }
})

function validAnchor(anchor: PortraitAnimationConfig['mouth'] | undefined): anchor is PortraitAnimationConfig['mouth'] {
  return Boolean(
    anchor && Number.isFinite(anchor.x) && Number.isFinite(anchor.y) &&
    Number.isFinite(anchor.width) && Number.isFinite(anchor.height) && anchor.width > 0 && anchor.height > 0
  )
}
const providerLabel = computed(() => ({
  static_2d: '2.5D 动态陪练',
  external_streaming: '阿里云实时数字人',
  live2d: 'Live2D 陪练',
  three_d: '3D 陪练'
}[props.snapshot.provider]))
const capabilityLabel = computed(() => {
  if (!props.snapshot.canSpeak) return '文字引导'
  const labels = {
    none: '语音引导已启用',
    cloud_audio: '真实云端语音',
    browser_tts: '已切换设备语音',
    silent: '文字引导',
  } as const
  return labels[props.snapshot.speechSource]
})
const stateLabel = computed(() => {
  const labels: Record<AvatarRuntimeSnapshot['state'], string> = {
    idle: '等待开始',
    loading_speech: props.snapshot.videoStatus === 'queued' || props.snapshot.videoStatus === 'running' ? '正在生成形象' : '正在准备语音',
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
    loading_speech: props.snapshot.videoStatus === 'queued' || props.snapshot.videoStatus === 'running'
      ? '这一句的语音已经准备好，动态形象完成后会自动开始示范。'
      : '正在准备这一句示范，你也可以先看清文字。',
    speaking: '先听完这一句，结束后再跟着练。',
    listening: '现在轮到你说，慢慢来，把句子说完整。',
    thinking: '请稍等，系统正在整理这次训练结果。',
    encouraging: '这一小步已经完成，可以继续下一项。',
    error: '这一步没有成功，可以重试或刷新当前页面。'
  }
  return hints[props.snapshot.state]
})

watch(
  [() => props.avatarUrl, () => props.avatarAnimationConfig],
  async ([src]) => {
    revokeAvatarObjectUrl()
    if (!src) return
    try {
      const url = src.startsWith('/api') ? src.slice(4) : src
      const response = await http.get<Blob>(url, { responseType: 'blob' })
      avatarObjectUrl.value = await createAvatarCrop(response.data, props.avatarAnimationConfig as Partial<PortraitAnimationConfig> | null)
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

async function createAvatarCrop(source: Blob, config: Partial<PortraitAnimationConfig> | null): Promise<string> {
  const crop = config?.crop
  if (!crop || !Number.isFinite(crop.x) || !Number.isFinite(crop.y) || !Number.isFinite(crop.width) || !Number.isFinite(crop.height) || !crop.width || !crop.height) {
    return URL.createObjectURL(source)
  }
  const sourceUrl = URL.createObjectURL(source)
  let usesSourceUrl = false
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error('avatar_crop_load_failed'))
      element.src = sourceUrl
    })
    const canvas = document.createElement('canvas')
    const size = 360
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d')
    if (!context) throw new Error('avatar_crop_canvas_unavailable')
    context.drawImage(
      image,
      crop.x * image.naturalWidth,
      crop.y * image.naturalHeight,
      crop.width * image.naturalWidth,
      crop.height * image.naturalHeight,
      0,
      0,
      size,
      size,
    )
    const result = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    if (result) return URL.createObjectURL(result)
    usesSourceUrl = true
    return sourceUrl
  } catch {
    usesSourceUrl = true
    return sourceUrl
  } finally {
    if (!usesSourceUrl) URL.revokeObjectURL(sourceUrl)
  }
}
</script>
