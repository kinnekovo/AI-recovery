<template>
  <section class="page-stack narrow">
    <div class="page-heading">
      <span class="kicker">创建陪伴者</span>
      <h1>用一张照片创建陪伴者</h1>
      <p>照片会先在本地完成清晰度检查，并自动调整为腾讯云支持的尺寸；只有在你确认后，才会提交生成实时数字人。</p>
    </div>
    <form v-if="!createdAgent" class="form-panel" @submit.prevent="createPortraitAgent">
      <label>名称<input v-model="form.name" placeholder="妈妈" /></label>
      <label>关系<input v-model="form.relationship" placeholder="母亲" /></label>
      <label>陪伴风格<input v-model="form.personality_style" placeholder="温柔鼓励" /></label>
      <label>
        形象性别
        <select v-model="form.avatar_gender">
          <option value="FEMALE">女性</option>
          <option value="MALE">男性</option>
        </select>
      </label>
      <label>
        陪伴者正面照
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="pickAvatar" />
        <small>单人、正面、面部清晰、无遮挡，建议上传胸部以上照片。</small>
      </label>
      <p v-if="avatarChecking" class="success-text">正在本地校验照片…</p>
      <p v-else-if="avatarMessage" class="error-text">{{ avatarMessage }}</p>
      <figure v-if="avatarPreview" class="avatar-upload-preview-wrap">
        <img class="avatar-upload-preview" :src="avatarPreview" alt="陪伴者头像裁剪预览" />
        <figcaption>将以此构图显示在动态陪练中</figcaption>
      </figure>
      <label class="check-line">
        <input v-model="consent" type="checkbox" />
        已确认该形象获得本人授权，仅用于康复训练；下一步确认后，照片会提交至腾讯云生成实时形象
      </label>
      <p v-if="error" class="error-text">{{ error }}</p>
      <AppButton variant="primary" :loading="loading">保存照片并继续</AppButton>
    </form>
    <section v-else class="form-panel tencent-photo-flow" aria-live="polite">
      <div class="tencent-photo-layout">
        <figure class="tencent-photo-preview">
          <img v-if="avatarPreview" :src="avatarPreview" :alt="`${createdAgent.name} 的照片预览`" />
          <div v-else class="tencent-photo-placeholder">照片已保存</div>
          <figcaption>{{ createdAgent.name }} · {{ createdAgent.relationship }}</figcaption>
        </figure>
        <div class="tencent-photo-content">
          <span class="kicker">第二步：生成实时数字人</span>
          <h2>{{ tencentStatusTitle }}</h2>
          <p>{{ tencentStatusDescription }}</p>

          <ol class="avatar-build-progress" aria-label="照片数字人生成进度">
            <li class="done"><span>1</span><strong>照片已保存</strong></li>
            <li :class="{ active: createdAgent.tencent_avatar_status === 'detecting', done: ['training', 'ready'].includes(createdAgent.tencent_avatar_status) }">
              <span>2</span><strong>腾讯云检测照片</strong>
            </li>
            <li :class="{ active: createdAgent.tencent_avatar_status === 'training', done: createdAgent.tencent_avatar_status === 'ready' }">
              <span>3</span><strong>生成实时形象</strong>
            </li>
          </ol>

          <template v-if="['pending', 'failed'].includes(createdAgent.tencent_avatar_status)">
            <fieldset class="photo-version-options">
              <legend>本次测试版本</legend>
              <label><input v-model="photoVersion" type="radio" :value="0" /><span><strong>快速版</strong><small>约 10 分钟，仅头部轻微动态，适合先验证链路。</small></span></label>
              <label><input v-model="photoVersion" type="radio" :value="1" /><span><strong>优享版</strong><small>约 1 小时，头部和身体有轻微动态。</small></span></label>
            </fieldset>
            <label class="check-line quota-confirmation">
              <input v-model="avatarSubmitConfirmed" type="checkbox" />
              我确认提交后会消耗 1 个腾讯云“2D 小样本照片”定制额度，任务生成后该额度不能退回
            </label>
          </template>

          <p v-if="customizationMessage" class="success-text">{{ customizationMessage }}</p>
          <p v-if="createdAgent.tencent_avatar_error" class="error-text">{{ createdAgent.tencent_avatar_error }}</p>
          <p v-if="error" class="error-text">{{ error }}</p>

          <div class="button-row">
            <AppButton
              v-if="['pending', 'failed'].includes(createdAgent.tencent_avatar_status)"
              variant="primary"
              :loading="loading"
              :disabled="!avatarSubmitConfirmed"
              @click="submitTencentAvatar"
            >
              提交照片并开始检测
            </AppButton>
            <AppButton
              v-else-if="['detecting', 'training'].includes(createdAgent.tencent_avatar_status)"
              variant="secondary"
              :loading="loading"
              @click="refreshTencentAvatar"
            >
              查询最新进度
            </AppButton>
            <AppButton v-else variant="primary" @click="finish">使用这个数字人</AppButton>
            <AppButton variant="quiet" :disabled="loading" @click="finish">
              {{ createdAgent.tencent_avatar_status === 'ready' ? '返回陪伴者列表' : '稍后再继续' }}
            </AppButton>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import { agentsApi } from '@/api/agents'
import { toUserMessage } from '@/utils/errors'
import { type PortraitAnimationConfig, validatePortrait } from '@/avatar/face/portrait'
import type { Agent } from '@/types/api'

const router = useRouter()
const route = useRoute()
const form = ref<{ name: string; relationship: string; personality_style: string; avatar_gender: 'MALE' | 'FEMALE' }>({
  name: '', relationship: '', personality_style: '温柔鼓励', avatar_gender: 'FEMALE'
})
const avatar = ref<File | null>(null)
const avatarConfig = ref<PortraitAnimationConfig | null>(null)
const avatarPreview = ref('')
const avatarChecking = ref(false)
const avatarMessage = ref('')
const consent = ref(true)
const loading = ref(false)
const error = ref('')
const createdAgent = ref<Agent | null>(null)
const photoVersion = ref<0 | 1>(0)
const avatarSubmitConfirmed = ref(false)
const customizationMessage = ref('')
let customizationTimer: number | null = null

const tencentStatusTitle = computed(() => {
  const status = createdAgent.value?.tencent_avatar_status
  if (status === 'detecting') return '正在检查这张照片'
  if (status === 'training') return '正在生成实时数字人'
  if (status === 'ready') return '照片数字人已经准备好了'
  if (status === 'failed') return '这次没有生成成功'
  return '准备提交腾讯云测试'
})

const tencentStatusDescription = computed(() => {
  const status = createdAgent.value?.tencent_avatar_status
  if (status === 'detecting') return '腾讯云正在确认照片中只有一张清晰正脸。页面会自动查询结果。'
  if (status === 'training') return photoVersion.value === 0 ? '快速版通常约 10 分钟完成，你可以离开页面后再回来查看。' : '优享版通常约 1 小时完成，你可以离开页面后再回来查看。'
  if (status === 'ready') return '后续进入跟读训练时，会优先使用这个专属形象。'
  if (status === 'failed') return '请查看下方原因。你可以修正配置后再次提交，或者暂时使用本地形象。'
  return '我们会先做人脸检测；检测通过后才正式开始照片数字人训练。'
})

function pickFile(event: Event): File | null {
  const input = event.target as HTMLInputElement
  return input.files?.[0] || null
}

async function pickAvatar(event: Event) {
  const file = pickFile(event)
  avatar.value = null
  avatarConfig.value = null
  avatarMessage.value = ''
  if (avatarPreview.value) URL.revokeObjectURL(avatarPreview.value)
  avatarPreview.value = ''
  if (!file) return
  avatarChecking.value = true
  const validation = await validatePortrait(file)
  avatarChecking.value = false
  if (!validation.config) {
    avatarMessage.value = validation.message || '这张照片暂时不能用于动态陪练。'
    return
  }
  avatar.value = file
  avatarConfig.value = validation.config
  avatarPreview.value = await createCropPreview(file, validation.config.crop)
}

async function createCropPreview(file: File, crop: PortraitAnimationConfig['crop']): Promise<string> {
  const sourceUrl = URL.createObjectURL(file)
  let usesSourceUrl = false
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error('preview_image_load_failed'))
      element.src = sourceUrl
    })
    const canvas = document.createElement('canvas')
    const size = 360
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d')
    if (!context) throw new Error('preview_canvas_unavailable')
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
    const preview = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    if (preview) return URL.createObjectURL(preview)
    usesSourceUrl = true
    return sourceUrl
  } catch {
    usesSourceUrl = true
    return sourceUrl
  } finally {
    // 成功分支已把位图绘制进 Canvas；失败分支仍需要保留原图 URL。
    if (!usesSourceUrl) URL.revokeObjectURL(sourceUrl)
  }
}

async function createPortraitAgent() {
  error.value = ''
  if (!consent.value) {
    error.value = '请先确认授权'
    return
  }
  if (!avatar.value || !avatarConfig.value) {
    error.value = '请先上传一张通过校验的正面人物照片。'
    return
  }
  loading.value = true
  try {
    const agent = await agentsApi.create({
      ...form.value,
      image_consent_confirmed: true,
      voice_consent_confirmed: false
    })
    createdAgent.value = await agentsApi.uploadAvatar(agent.id, avatar.value, avatarConfig.value)
    await router.replace({ path: '/agent/create', query: { agent: createdAgent.value.id } })
    customizationMessage.value = '照片已经安全保存。确认额度后，即可开始腾讯云照片数字人测试。'
  } catch (err) {
    error.value = toUserMessage(err, '创建失败')
  } finally {
    loading.value = false
  }
}

async function submitTencentAvatar() {
  if (!createdAgent.value) return
  error.value = ''
  customizationMessage.value = ''
  if (!avatarSubmitConfirmed.value) {
    error.value = '请先确认本次提交会消耗 1 个照片数字人定制额度。'
    return
  }
  loading.value = true
  try {
    createdAgent.value = await agentsApi.submitTencentAvatar(createdAgent.value.id, photoVersion.value)
    customizationMessage.value = '照片已上传，腾讯云正在进行人脸检测。'
    scheduleCustomizationRefresh()
  } catch (err) {
    error.value = toUserMessage(err, '照片数字人任务提交失败')
  } finally {
    loading.value = false
  }
}

async function refreshTencentAvatar() {
  if (!createdAgent.value || !['detecting', 'training'].includes(createdAgent.value.tencent_avatar_status)) return
  error.value = ''
  loading.value = true
  try {
    createdAgent.value = await agentsApi.refreshTencentAvatar(createdAgent.value.id)
    if (createdAgent.value.tencent_avatar_status === 'training') {
      customizationMessage.value = '照片已通过检测，腾讯云正在生成实时数字人。'
    } else if (createdAgent.value.tencent_avatar_status === 'ready') {
      customizationMessage.value = '专属形象已经生成，训练页面会自动使用它。'
    }
    scheduleCustomizationRefresh()
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法查询生成进度')
    scheduleCustomizationRefresh(15000)
  } finally {
    loading.value = false
  }
}

function scheduleCustomizationRefresh(delay = 8000) {
  if (customizationTimer !== null) window.clearTimeout(customizationTimer)
  customizationTimer = null
  if (!createdAgent.value || !['detecting', 'training'].includes(createdAgent.value.tencent_avatar_status)) return
  customizationTimer = window.setTimeout(() => {
    customizationTimer = null
    void refreshTencentAvatar()
  }, delay)
}

async function finish() {
  if (!createdAgent.value) return
  await agentsApi.setCurrent(createdAgent.value.id)
  router.push('/agent/list')
}

onMounted(async () => {
  const agentId = typeof route.query.agent === 'string' ? route.query.agent : ''
  if (!agentId) return
  loading.value = true
  try {
    const existing = (await agentsApi.list()).find((item) => item.id === agentId)
    if (!existing) {
      error.value = '没有找到这个陪伴者，请从陪伴者列表重新进入。'
      return
    }
    createdAgent.value = existing
    photoVersion.value = existing.tencent_avatar_photo_version
    if (['detecting', 'training'].includes(existing.tencent_avatar_status)) scheduleCustomizationRefresh(1000)
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法恢复照片数字人创建进度')
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (avatarPreview.value) URL.revokeObjectURL(avatarPreview.value)
  if (customizationTimer !== null) window.clearTimeout(customizationTimer)
})
</script>
