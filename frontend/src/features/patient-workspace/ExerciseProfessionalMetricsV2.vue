<template>
  <section class="v2-page therapist-v2-page exercise-detail-page">
    <div v-if="loading" class="v2-state">正在读取本练习的专业指标…</div>
    <div v-else-if="error" class="v2-state v2-state-error">{{ error }}</div>
    <template v-else-if="detail">
      <header class="v2-page-header">
        <RouterLink :to="`/therapist/training-sessions/${detail.session_id}#attempts`" class="v2-text-link">← 返回训练详情</RouterLink>
        <p class="v2-context">{{ isScenario ? '场景沟通专业指标' : '跟读专业指标' }}</p>
        <h1>{{ detail.exercise.title }}</h1>
        <p>{{ isScenario ? `场景：${detail.exercise.target}` : `目标句：${detail.exercise.target}` }}</p>
      </header>

      <section class="workspace-band exercise-contract-band">
        <div>
          <p class="v2-section-label">Exercise contract</p>
          <h2>{{ isScenario ? `${detail.exercise.title} · 功能性沟通` : '固定文本复现 · 发音与过程' }}</h2>
          <p>{{ detail.exercise.instruction }}</p>
        </div>
        <div class="exercise-status-note">
          <span>状态</span>
          <strong>{{ statusLabel(detail.exercise.status) }}</strong>
          <small>本页只展示这一道练习的证据与指标。</small>
        </div>
      </section>

      <section class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Measurements</p>
            <h2>{{ isScenario ? '场景沟通指标' : '跟读复现指标' }}</h2>
          </div>
          <p>{{ isScenario ? '评价患者是否完成真实沟通，而不是是否复述了某个标准句。' : '评价固定目标句的复现、发音和声学过程。' }}</p>
        </div>
        <div class="metric-grid">
          <MetricPanel v-for="metric in detail.professional_metrics" :key="metric.code" :metric="metric" />
        </div>
      </section>

      <section v-if="isScenario" class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Dialogue evidence</p>
            <h2>{{ detail.exercise.title }}对话过程</h2>
          </div>
          <p>先看患者说了什么，再看系统如何判断信息单元和回应。</p>
        </div>
        <ol v-if="dialogueTurns.length" class="exercise-dialogue-log" aria-label="医院看病场景对话">
          <li v-for="turn in dialogueTurns" :key="turn.turn_index" :class="turn.speaker">
            <span>{{ turn.speaker === 'agent' ? '工作人员' : '患者' }}</span>
            <p>{{ turn.text }}</p>
          </li>
        </ol>
        <p v-else class="v2-quiet-copy">本场景还没有可展示的对话回合。</p>
      </section>

      <section class="workspace-band">
        <div class="workspace-band-heading">
          <div>
            <p class="v2-section-label">Evidence & Quality</p>
            <h2>本练习证据</h2>
          </div>
        </div>
        <p v-if="!detail.evidence.length" class="v2-quiet-copy">本练习尚未形成可展示的证据。</p>
        <details v-for="item in detail.evidence" :key="String(item.id)" class="evidence-row">
          <summary><strong>{{ String(item.type || '训练证据') }}</strong><span>{{ String(item.quality_status || 'unknown') }} · {{ String(item.source_status || 'unknown') }}</span></summary>
          <pre>{{ JSON.stringify(item, null, 2) }}</pre>
        </details>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import MetricPanel from '@/domain-ui/MetricPanel.vue'
import { v2Api, type ExerciseProfessionalDetailV2 } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'

type DialogueTurn = { turn_index: number; speaker: string; text: string }

const route = useRoute()
const detail = ref<ExerciseProfessionalDetailV2 | null>(null)
const loading = ref(true)
const error = ref('')
const isScenario = computed(() => detail.value?.exercise_type === 'scenario')
const dialogueTurns = computed<DialogueTurn[]>(() => {
  const turns = detail.value?.scenario_dialogue?.turns
  return Array.isArray(turns) ? turns as DialogueTurn[] : []
})

function statusLabel(value: string) {
  return ({ planned: '待开始', in_progress: '进行中', completed: '已完成', skipped: '已跳过', technical_invalid: '技术原因未评分' } as Record<string, string>)[value] || value
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await v2Api.therapistExercise(String(route.params.sessionId), String(route.params.taskId))
  } catch (err) {
    error.value = toUserMessage(err, '本练习专业指标加载失败。')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.exercise-detail-page { max-width: 1180px; }
.exercise-contract-band { display: flex; justify-content: space-between; gap: 28px; align-items: start; }
.exercise-contract-band h2 { margin: 6px 0 8px; }
.exercise-contract-band p { margin: 0; color: var(--pr-muted); line-height: 1.65; }
.exercise-status-note { min-width: 180px; display: grid; gap: 5px; padding-left: 22px; border-left: 1px solid var(--pr-line); }
.exercise-status-note span, .exercise-status-note small { color: var(--pr-muted); }
.exercise-status-note strong { font-size: 1.1rem; }
.exercise-dialogue-log { display: grid; gap: 12px; list-style: none; padding: 0; margin: 0; }
.exercise-dialogue-log li { max-width: 74ch; padding: 14px 16px; border: 1px solid var(--pr-line); border-radius: 12px; background: #fff; }
.exercise-dialogue-log li.patient { justify-self: end; background: var(--pr-blue-soft); }
.exercise-dialogue-log span { font-size: .82rem; font-weight: 750; color: var(--pr-muted); }
.exercise-dialogue-log p { margin: 6px 0 0; line-height: 1.6; }
@media (max-width: 640px) {
  .exercise-contract-band { display: grid; }
  .exercise-status-note { min-width: 0; padding: 14px 0 0; border-left: 0; border-top: 1px solid var(--pr-line); }
}
</style>
