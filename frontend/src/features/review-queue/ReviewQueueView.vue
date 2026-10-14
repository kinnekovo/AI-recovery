<template>
  <section class="v2-page therapist-v2-page review-queue-page">
    <header class="v2-page-header">
      <p class="v2-context">治疗师工作台 · 待复核</p>
      <h1>先处理需要你判断的事项</h1>
      <p>队列按紧急程度和等待时间排列。接手后会保留负责人，原始训练材料不会被修改。</p>
    </header>

    <section v-if="summary" class="review-queue-summary" aria-label="待办概况">
      <span><strong>{{ summary.open }}</strong>待接手</span>
      <span><strong>{{ summary.mine }}</strong>由我负责</span>
      <span><strong>{{ summary.waiting_information }}</strong>等待补充</span>
      <span><strong>{{ summary.waiting_plan_publish }}</strong>等待方案发布</span>
    </section>

    <section class="review-filter-bar" aria-label="筛选待复核事项">
      <label class="review-search-field"><span>患者</span><input v-model="patient" type="search" placeholder="按姓名筛选" @keyup.enter="applyFilters" /></label>
      <label><span>状态</span><select v-model="status"><option value="">全部未关闭</option><option value="open">待接手</option><option value="acknowledged,in_review">我已接手</option><option value="waiting_information">等待补充</option><option value="waiting_plan_publish">等待方案发布</option></select></label>
      <label><span>事项类型</span><select v-model="type"><option value="">全部类型</option><option v-for="option in typeOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      <label><span>优先级</span><select v-model="priority"><option value="">全部</option><option value="high">高</option><option value="normal">普通</option><option value="low">低</option></select></label>
      <label><span>负责人</span><select v-model="assignedTo"><option value="all">全部负责人</option><option value="me">我负责</option><option value="unassigned">待分配</option></select></label>
      <button class="v2-button secondary review-filter-submit" :disabled="loading" @click="applyFilters">筛选</button>
    </section>

    <div v-if="error" class="v2-inline-error" role="alert"><span>{{ error }}</span><button class="v2-text-link" @click="load()">重新加载</button></div>
    <div v-if="loading && !items.length" class="review-queue-skeleton" role="status" aria-live="polite">正在读取待复核事项…</div>
    <section v-else-if="!items.length" class="review-queue-empty">
      <CheckCircle2 :size="28" aria-hidden="true" />
      <h2>{{ hasFilters ? '没有符合条件的事项' : '目前没有待复核事项' }}</h2>
      <p>{{ hasFilters ? '可以调整筛选条件后再查看。' : '患者训练仍会正常记录；有事项需要专业判断时会出现在这里。' }}</p>
      <button v-if="hasFilters" class="v2-button secondary" @click="clearFilters">清除筛选</button>
    </section>
    <section v-else class="review-queue-list" aria-label="待复核列表">
      <article v-for="item in items" :key="item.id" class="review-queue-row">
        <div class="review-queue-priority" :class="`priority-${priorityTone(item.priority)}`">
          <AlertTriangle v-if="item.priority === 'high'" :size="17" aria-hidden="true" />
          <Clock3 v-else :size="17" aria-hidden="true" />
          <span>{{ priorityLabel(item.priority) }}</span>
        </div>
        <div class="review-queue-main">
          <div class="review-queue-title"><h2>{{ item.patient }}</h2><span class="review-type-label">{{ typeLabel(item.type) }}</span><span class="review-status-label">{{ statusLabel(item.status) }}</span></div>
          <p>{{ item.summary }}</p>
          <div class="review-queue-meta"><span>{{ item.next_step }}</span><span>{{ item.evidence_count }} 条关联来源</span><span>{{ formatDate(item.created_at) }}</span><span v-if="item.assigned_to">负责人：{{ item.assigned_to }}</span></div>
        </div>
        <div class="review-queue-actions">
          <button class="v2-button primary" :disabled="busyId === item.id" @click="openReview(item)">{{ busyId === item.id ? '正在打开…' : item.status === 'open' || item.status === 'acknowledged' ? (item.assigned_to_user_id && item.assigned_to_user_id !== currentUserId ? '查看事项' : item.assigned_to_user_id === currentUserId ? '继续复核' : '接手并复核') : item.status === 'waiting_information' ? '查看补充状态' : item.assigned_to_user_id === currentUserId ? '继续复核' : '查看事项' }}</button>
          <RouterLink class="v2-text-link" :to="`/therapist/patients/${item.patient_user_id}`">查看患者</RouterLink>
        </div>
      </article>
      <div v-if="nextCursor" class="review-queue-more"><button class="v2-button secondary" :disabled="loading" @click="loadMore">{{ loading ? '正在加载…' : '加载更多' }}</button></div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, CheckCircle2, Clock3 } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { reviewWorkflowApi, type ReviewQueueItem, type ReviewQueueResponse } from '@/api/reviewWorkflow'
import { toUserMessage } from '@/utils/errors'

const router = useRouter()
const auth = useAuthStore()
const currentUserId = computed(() => auth.me?.user.id || '')
const items = ref<ReviewQueueItem[]>([])
const summary = ref<ReviewQueueResponse['summary'] | null>(null)
const nextCursor = ref<string | null>(null)
const loading = ref(false)
const busyId = ref('')
const error = ref('')
const patient = ref('')
const status = ref('')
const type = ref('')
const priority = ref('')
const assignedTo = ref('all')
const hasFilters = computed(() => Boolean(patient.value || status.value || type.value || priority.value || assignedTo.value !== 'all'))
const typeOptions = [
  { value: 'patient_help_request', label: '患者请求帮助' },
  { value: 'repeated_comparable_difficulty', label: '持续困难' },
  { value: 'increasing_prompt_dependency', label: '提示依赖增加' },
  { value: 'repeated_ungradable_attempt', label: '连续无法评分' },
  { value: 'training_adherence_drop', label: '训练坚持度下降' },
  { value: 'assessment_due', label: '正式评估' },
  { value: 'comparable_metric_decline', label: '趋势变化' },
  { value: 'evaluation_write_failure', label: '数据处理异常' },
]

function filters(cursor?: string | null) {
  return { patient: patient.value.trim(), status: status.value, type: type.value, priority: priority.value, assigned_to: assignedTo.value, cursor: cursor || undefined, limit: 20 }
}
async function load(append = false, cursor?: string | null) {
  loading.value = true
  error.value = ''
  try {
    const result = await reviewWorkflowApi.queue(filters(cursor))
    items.value = append ? [...items.value, ...result.items] : result.items
    summary.value = result.summary
    nextCursor.value = result.next_cursor
  } catch (cause) {
    error.value = toUserMessage(cause, '待复核队列暂时无法加载。')
  } finally {
    loading.value = false
  }
}
function applyFilters() { void load() }
function loadMore() { if (nextCursor.value) void load(true, nextCursor.value) }
function clearFilters() { patient.value = ''; status.value = ''; type.value = ''; priority.value = ''; assignedTo.value = 'all'; void load() }
async function openReview(item: ReviewQueueItem) {
  busyId.value = item.id
  error.value = ''
  try {
    if (['open', 'acknowledged'].includes(item.status) && (!item.assigned_to_user_id || item.assigned_to_user_id === currentUserId.value)) await reviewWorkflowApi.begin(item.id)
    await router.push(`/therapist/reviews/${item.id}`)
  } catch (cause) {
    error.value = toUserMessage(cause, '无法接手该事项；请刷新后查看负责人状态。')
    await load()
  } finally {
    busyId.value = ''
  }
}
function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }
function priorityTone(value: string) { return value === 'high' ? 'high' : value === 'low' ? 'low' : 'normal' }
function priorityLabel(value: string) { return value === 'high' ? '高优先' : value === 'low' ? '一般' : '需要关注' }
function statusLabel(value: string) { return ({ open: '待接手', acknowledged: '已接手', in_review: '复核中', waiting_information: '等待补充', waiting_plan_publish: '等待方案发布' } as Record<string, string>)[value] || value }
function typeLabel(value: string) { return typeOptions.find(item => item.value === value)?.label || '需要复核' }
onMounted(() => { void load() })
</script>
