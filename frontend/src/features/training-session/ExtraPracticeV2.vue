<template>
  <section class="v2-page patient-readable extra-session-page">
    <RouterLink class="v2-text-link" to="/training">← 返回训练</RouterLink>
    <header class="v2-page-header">
      <p class="v2-context">额外练习</p>
      <h1>为你准备的一组练习</h1>
      <p>按顺序完成下面的跟读和场景练习。想试试其他内容，可以换一批。</p>
    </header>

    <div v-if="loading" class="v2-state">正在准备练习组合…</div>
    <div v-else-if="error && !pool" class="v2-state v2-state-error">
      <strong>暂时无法准备额外练习</strong><span>{{ error }}</span>
      <button class="v2-button secondary" @click="load">重新加载</button>
    </div>
    <template v-else-if="pool">
      <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
      <section class="v2-section-block extra-session-plan" aria-label="本组练习安排">
        <div class="v2-section-heading">
          <div>
            <p class="v2-section-label">本组安排</p>
            <h2>{{ pool.session_items.length }} 项练习 · 约 {{ pool.estimated_duration_minutes }} 分钟</h2>
            <p>额外练习会单独记录，不改变今日练习的完成情况。</p>
          </div>
          <button class="v2-button secondary" :disabled="busy" @click="refreshPool">{{ busy && refreshing ? '正在更换…' : '换一批' }}</button>
        </div>
        <ol v-if="pool.session_items.length" class="exercise-agenda extra-session-agenda">
          <li v-for="(item, index) in pool.session_items" :key="item.id">
            <span class="agenda-number">{{ index + 1 }}</span>
            <div><strong>{{ item.exercise_type === 'repeat' ? item.target : item.title }}</strong><small>{{ item.exercise_type === 'repeat' ? `跟读 · ${difficultyLabel(item.difficulty)}` : '场景表达' }}</small></div>
          </li>
        </ol>
        <p v-else class="v2-quiet-copy">当前没有可执行的额外练习，请稍后再试。</p>
        <button class="v2-button primary extra-session-start" :disabled="busy || !pool.session_items.length" @click="start">
          {{ busy && !refreshing ? '正在准备…' : '开始这一组' }}
        </button>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { v2Api, type ExtraPracticePoolV2 } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'

const router = useRouter()
const pool = ref<ExtraPracticePoolV2 | null>(null)
const loading = ref(true)
const busy = ref(false)
const refreshing = ref(false)
const error = ref('')

function difficultyLabel(level: string) {
  return level === 'L1' || level === 'L2' ? '初级' : level === 'L3' ? '中级' : '高级'
}

async function load() {
  loading.value = true
  error.value = ''
  try { pool.value = await v2Api.extraPracticePool() }
  catch (err) { error.value = toUserMessage(err, '请稍后再试。') }
  finally { loading.value = false }
}

async function refreshPool() {
  if (busy.value) return
  busy.value = true
  refreshing.value = true
  error.value = ''
  try { pool.value = await v2Api.extraPracticePool(true) }
  catch (err) { error.value = toUserMessage(err, '暂时无法换一批练习。') }
  finally { busy.value = false; refreshing.value = false }
}

async function start() {
  if (!pool.value?.session_items.length || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const session = await v2Api.startOrResume('extra_practice', pool.value.id)
    await router.push(`/training/session/${session.id}`)
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法开始额外练习，请刷新组合后再试。')
  } finally { busy.value = false }
}

onMounted(load)
</script>
