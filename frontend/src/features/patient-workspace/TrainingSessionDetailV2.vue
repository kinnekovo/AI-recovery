<template>
  <section class="v2-page therapist-v2-page training-detail-page">
    <div v-if="loading" class="v2-state">正在读取训练详情…</div>
    <div v-else-if="error" class="v2-state v2-state-error">{{ error }}</div>
    <template v-else-if="detail">
      <header class="v2-page-header">
        <p class="v2-context">单次 TrainingSession</p>
        <h1>{{ formatDate(detail.overview.started_at) }}</h1>
        <p>{{ detail.overview.session_kind === 'formal' ? '正式计划训练' : '额外练习' }} · {{ detail.overview.status }}</p>
      </header>

      <nav class="workspace-anchor-nav" aria-label="训练详情章节">
        <a href="#overview">概览</a>
        <a href="#attempts">练习</a>
        <a href="#facts">专业指标入口</a>
        <a href="#evidence">证据</a>
      </nav>

      <section id="overview" class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Overview</p>
            <h2>这次发生了什么</h2>
          </div>
        </div>
        <div class="session-overview-strip">
          <div><strong>{{ detail.overview.exercises.length }}</strong><span>练习</span></div>
          <div><strong>{{ completedCount }}</strong><span>完成</span></div>
          <div><strong>{{ technicalCount }}</strong><span>技术原因未评分</span></div>
        </div>
      </section>

      <section id="attempts" class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Exercises / Attempts</p>
            <h2>练习与作答</h2>
          </div>
          <p>点击某一道练习，进入对应的专业指标页面。</p>
        </div>
        <div class="exercise-detail-list">
          <article v-for="exercise in detail.overview.exercises" :key="exercise.id">
            <div class="exercise-row-heading">
              <div>
                <strong>{{ exercise.order_index + 1 }}. {{ exercise.title }}</strong>
                <span>{{ exerciseTypeLabel(exercise.exercise_type) }} · {{ statusLabel(exercise.status) }}</span>
              </div>
              <RouterLink class="exercise-metric-link" :to="exercisePath(exercise.id)">查看专业指标 →</RouterLink>
            </div>
            <p>{{ exercise.target }}</p>
            <small>提示等级 {{ exercise.prompt_level }} · {{ exercise.attempts.length }} 次作答</small>
          </article>
        </div>
      </section>

      <section id="facts" class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Measurements</p>
            <h2>按练习查看专业指标</h2>
          </div>
          <p>跟读和场景表达使用不同的评估契约，不在训练总览中混合展示。</p>
        </div>
        <div class="exercise-metric-entry-grid">
          <RouterLink v-for="exercise in detail.overview.exercises" :key="exercise.id" class="exercise-metric-entry" :to="exercisePath(exercise.id)">
            <span>{{ exerciseTypeLabel(exercise.exercise_type) }}</span>
            <strong>{{ exercise.title }}</strong>
            <p>{{ exerciseMetricDescription(exercise.exercise_type) }}</p>
            <b>打开专业指标页 →</b>
          </RouterLink>
        </div>
      </section>

      <section id="evidence" class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Evidence & Quality</p>
            <h2>证据与数据来源</h2>
          </div>
        </div>
        <p v-if="!detail.evidence.length" class="v2-quiet-copy">当前没有可展示的证据投影。</p>
        <details v-for="item in detail.evidence" :key="String(item.id)" class="evidence-row">
          <summary><strong>{{ item.type }}</strong><span>{{ item.quality_status }} · {{ item.source_status }}</span></summary>
          <pre>{{ JSON.stringify(item, null, 2) }}</pre>
        </details>
      </section>

      <section id="interpretation" class="semantic-layers">
        <article class="layer facts"><p class="v2-section-label">FACTS</p><h2>测量结果</h2><p>专业指标已按练习拆分，详情页会显示对应来源和质量。</p></article>
        <article class="layer observations"><p class="v2-section-label">SYSTEM OBSERVATIONS</p><h2>系统观察</h2><p v-if="!detail.observations.length">目前没有满足规则的长期观察。</p><p v-for="item in detail.observations" :key="String(item.id)">{{ item.statement }}</p></article>
        <article class="layer recommendations"><p class="v2-section-label">CANDIDATE RECOMMENDATIONS</p><h2>系统建议</h2><p v-if="!detail.recommendations.length">目前没有候选建议。</p><p v-for="item in detail.recommendations" :key="String(item.id)">{{ item.candidate_action }}</p></article>
        <article class="layer decision"><p class="v2-section-label">THERAPIST ACTION</p><h2>治疗师决定</h2><p>系统建议不会自动修改正式训练方案。请从患者工作区发起 Stage Review。</p></article>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { v2Api, type SessionDetailV2 } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const detail = ref<SessionDetailV2 | null>(null)
const loading = ref(true)
const error = ref('')
const sessionId = computed(() => String(route.params.sessionId))
const completedCount = computed(() => detail.value?.overview.exercises.filter(item => item.status === 'completed').length || 0)
const technicalCount = computed(() => detail.value?.overview.exercises.filter(item => item.status === 'technical_invalid').length || 0)

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(value)) : '训练记录'
}

function exercisePath(taskId: string) {
  return `/therapist/training-sessions/${sessionId.value}/exercises/${taskId}`
}

function exerciseTypeLabel(type: 'repeat' | 'scenario') {
  return type === 'scenario' ? '场景表达' : '跟读训练'
}

function exerciseMetricDescription(type: 'repeat' | 'scenario') {
  return type === 'scenario' ? '目标完成、信息完整、回应能力、修复与场景独立完成度。' : '错误、完整度、语速、发音、音素和声调等固定文本指标。'
}

function statusLabel(value: string) {
  return ({ planned: '待开始', in_progress: '进行中', completed: '已完成', skipped: '已跳过', technical_invalid: '技术原因未评分' } as Record<string, string>)[value] || value
}

async function load() {
  try {
    detail.value = await v2Api.therapistSession(sessionId.value)
  } catch (err) {
    error.value = toUserMessage(err, '训练详情加载失败。')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.training-detail-page { max-width: 1180px; }
.exercise-row-heading { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.exercise-row-heading > div { display: grid; gap: 7px; }
.exercise-metric-link { flex: 0 0 auto; color: var(--pr-blue); font-weight: 750; }
.exercise-metric-entry-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.exercise-metric-entry { display: grid; gap: 9px; padding: 19px; border: 1px solid var(--pr-line); border-radius: 12px; background: #fff; transition: border-color .18s ease, transform .18s ease; }
.exercise-metric-entry:hover { border-color: var(--pr-blue); transform: translateY(-1px); }
.exercise-metric-entry > span { color: var(--pr-muted); font-size: .86rem; font-weight: 750; }
.exercise-metric-entry strong { font-size: 1.12rem; }
.exercise-metric-entry p { margin: 0; color: var(--pr-muted); line-height: 1.55; }
.exercise-metric-entry b { color: var(--pr-blue); font-size: .92rem; }
@media (max-width: 640px) {
  .exercise-row-heading { display: grid; }
  .exercise-metric-entry-grid { grid-template-columns: 1fr; }
}
</style>
