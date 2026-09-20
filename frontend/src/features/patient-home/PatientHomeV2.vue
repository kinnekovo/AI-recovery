<!--
THESIS: one calm daily action replaces the old dashboard and recommendation sprawl.
OWN-WORLD: daylight clinic surface, deep ink, therapeutic teal, precise dividers.
STORY: understand today's purpose, duration, and next action in one glance.
FIRST VIEWPORT: goal context above a dominant training sheet and a single large CTA.
FORM: Operate-mode patient surface extending the committed Product Reset design system.
-->
<template>
  <section class="v2-page patient-readable" aria-labelledby="patient-home-title">
    <header class="v2-page-header">
      <p class="v2-context">{{ home?.greeting || '你好' }}</p>
      <h1 id="patient-home-title">今天，我们一步一步来</h1>
      <p>先完成治疗师为你安排的练习。累了可以暂停，刷新页面也不会丢失进度。</p>
    </header>

    <div v-if="loading" class="v2-state" role="status">正在准备今天的训练…</div>
    <div v-else-if="error" class="v2-state v2-state-error" role="alert">
      <strong>今天的训练暂时没有加载出来</strong><span>{{ error }}</span><button class="v2-button secondary" @click="load">重新加载</button>
    </div>

    <template v-else-if="home">
      <aside v-if="home.plan_update_announcement" class="v2-inline-success" role="status">{{ home.plan_update_announcement }}</aside>
      <section v-if="home.state === 'onboarding_required'" class="v2-action-sheet">
        <div><p class="v2-section-label">开始前</p><h2>先完成陪伴设置</h2><p>选择声音和陪伴形象后，就可以开始正式训练。</p></div>
        <RouterLink class="v2-button primary" to="/me">去设置</RouterLink>
      </section>

      <section v-else-if="home.state === 'waiting_for_plan'" class="v2-action-sheet">
        <div><p class="v2-section-label">今日状态</p><h2>治疗师正在准备训练方案</h2><p>暂时不需要自行选择训练。方案发布后会出现在这里。</p></div>
      </section>

      <section v-else-if="home.state === 'temporarily_unavailable'" class="v2-action-sheet">
        <div><p class="v2-section-label">暂时不可用</p><h2>今天的训练还没有准备好</h2><p>你的历史记录不会丢失，请稍后重试或联系治疗师。</p></div><button class="v2-button secondary" @click="load">重新加载</button>
      </section>

      <section v-else class="v2-action-sheet today-sheet">
        <div class="today-copy">
          <p class="v2-section-label">今天练什么</p>
          <h2>{{ home.stage_focus || '按当前康复目标完成练习' }}</h2>
          <p class="goal-reason"><strong>为什么练：</strong>{{ home.active_rehabilitation_goal?.description || '帮助你在日常交流中表达得更完整。' }}</p>
          <div class="today-facts" aria-label="今日训练信息">
            <span><Clock3 :size="19" aria-hidden="true" />约 {{ home.estimated_duration || 15 }} 分钟</span>
            <span><ListChecks :size="19" aria-hidden="true" />{{ home.today_training_structure.length }} 项练习</span>
            <span><ShieldCheck :size="19" aria-hidden="true" />自动保存</span>
          </div>
        </div>
        <button class="v2-button primary patient-primary-action" :disabled="starting" @click="begin">
          <Play v-if="home.state === 'ready_to_train' || !home.today_session" :size="22" aria-hidden="true" />
          <RotateCcw v-else-if="home.state === 'in_progress' || home.state === 'paused' || home.state === 'plan_updated'" :size="22" aria-hidden="true" />
          <ClipboardCheck v-else :size="22" aria-hidden="true" />
          {{ starting ? '正在准备…' : home.primary_action?.label || '开始今天的训练' }}
        </button>
      </section>

      <section class="v2-section-block" aria-labelledby="today-structure-title">
        <div class="v2-section-heading"><div><p class="v2-section-label">训练顺序</p><h2 id="today-structure-title">今天会这样进行</h2></div></div>
        <ol class="exercise-agenda">
          <li v-for="(item, index) in home.today_training_structure" :key="item.id">
            <span class="agenda-number">{{ index + 1 }}</span>
            <div><strong>{{ item.title || (item.exercise_type === 'repeat' ? '跟读练习' : '场景表达') }}</strong><small>{{ item.exercise_type === 'repeat' ? '听示范，再完整说一遍' : '在真实场景里用自己的话表达' }}</small></div>
          </li>
        </ol>
      </section>

      <section class="v2-section-block" aria-labelledby="recent-change-title">
        <div class="v2-section-heading"><div><p class="v2-section-label">最近变化</p><h2 id="recent-change-title">只比较真正可比的记录</h2></div><RouterLink to="/progress" class="v2-text-link">查看我的进展</RouterLink></div>
        <p v-if="!home.recent_comparable_changes.length" class="v2-quiet-copy">还需要完成更多相同条件下的练习，才能判断变化。</p>
        <div v-else class="change-lines"><article v-for="item in home.recent_comparable_changes" :key="item.code"><strong>{{ item.label }}</strong><p>{{ item.explanation }}</p></article></div>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ClipboardCheck, Clock3, ListChecks, Play, RotateCcw, ShieldCheck } from 'lucide-vue-next'
import { v2Api, type PatientHomeV2 } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'

const router = useRouter()
const home = ref<PatientHomeV2 | null>(null)
const loading = ref(true)
const starting = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { home.value = await v2Api.patientHome() } catch (err) { error.value = toUserMessage(err, '请稍后再试。') } finally { loading.value = false }
}

async function begin() {
  if (!home.value) return
  if (home.value.state === 'completed' && home.value.today_session) {
    await router.push(`/training/session/${home.value.today_session.id}/summary`)
    return
  }
  starting.value = true
  try {
    const session = await v2Api.startOrResume('formal')
    await router.push(`/training/session/${session.id}`)
  } catch (err) { error.value = toUserMessage(err, '暂时无法开始训练。') } finally { starting.value = false }
}

onMounted(load)
</script>
