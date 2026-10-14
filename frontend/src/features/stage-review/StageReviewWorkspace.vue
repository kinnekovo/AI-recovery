<template>
  <section class="v2-page therapist-v2-page stage-review-page">
    <div v-if="loading" class="v2-state" role="status" aria-live="polite">正在整理阶段复核事实…</div>
    <div v-else-if="!review" class="v2-state v2-state-error" role="alert"><strong>阶段复核暂时无法打开</strong><span>{{ error }}</span><RouterLink class="v2-text-link" to="/therapist/reviews">返回待复核队列</RouterLink></div>
    <template v-else>
      <header class="stage-review-context">
        <RouterLink v-if="review.primary_attention_item_id" class="v2-text-link" :to="`/therapist/reviews/${review.primary_attention_item_id}`">← 返回证据复核</RouterLink>
        <RouterLink v-else class="v2-text-link" to="/therapist/reviews">← 返回待复核队列</RouterLink>
        <p class="v2-context">阶段复核 · {{ statusLabel(review.status) }}</p>
        <h1>{{ review.patient?.name || '患者阶段复核' }}</h1>
        <dl><div><dt>康复目标</dt><dd>{{ review.goal?.description || '尚未建立正式康复目标' }}</dd></div><div><dt>当前方案</dt><dd>{{ review.active_plan ? `v${review.active_plan.version_number} · ${review.active_plan.stage_focus}` : '尚无已发布方案' }}</dd></div><div><dt>复核编号</dt><dd>{{ review.id.slice(0, 8) }}</dd></div><div><dt>观察窗口</dt><dd>{{ windowLabel }}</dd></div></dl>
      </header>
      <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>

      <section class="stage-review-facts">
        <div class="review-section-heading"><div><p class="v2-context">事实与来源</p><h2>本次阶段判断依据</h2></div><p>创建时已冻结患者目标、方案版本和来源范围。</p></div>
        <div v-if="review.attention_item_ids.length" class="stage-source-list"><article v-for="itemId in review.attention_item_ids" :key="itemId"><span>来源待办</span><RouterLink :to="`/therapist/reviews/${itemId}`">{{ attentionLabel(itemId) }} · 查看录音和修订</RouterLink></article></div>
        <div v-if="review.evidence_review_revisions.length" class="stage-revision-list"><h3>已完成的人工证据复核</h3><article v-for="revision in review.evidence_review_revisions" :key="revision.id"><div><strong>{{ revision.action === 'corrected' ? '已修正' : revision.action === 'confirmed' ? '已确认' : '无法判断' }}</strong><time>{{ formatDate(revision.created_at) }}</time></div><p>{{ revision.reason || '未填写补充说明' }}</p><details><summary>复核前后结果</summary><pre>{{ JSON.stringify({ automatic: revision.automatic, revised: revision.revised }, null, 2) }}</pre></details></article></div>
        <div v-if="review.facts.trends?.length" class="stage-trend-list"><h3>可比较趋势</h3><article v-for="trend in review.facts.trends" :key="trend.code"><strong>{{ trend.label }}</strong><p>{{ trend.explanation }}</p></article></div>
        <div class="stage-review-layers">
          <section><h3>正式评估</h3><p v-if="!review.formal_assessments.length" class="v2-quiet-copy">本次复核没有正式评估。日常训练不会替代临床量表。</p><article v-for="assessment in review.formal_assessments" :key="assessment.id"><strong>{{ assessment.instrument_name }} · {{ assessment.instrument_version }}</strong><p>{{ formatDate(assessment.assessed_at) }} · {{ assessment.review_status }}</p><small>已施测：{{ assessment.measured_metrics.join('、') || '无；缺失项按未施测保留' }}</small></article></section>
          <section><h3>治疗师观察</h3><p v-if="review.therapist_notes">{{ review.therapist_notes }}</p><p v-else class="v2-quiet-copy">本次没有附加治疗师观察。</p><ul v-if="review.observations.length"><li v-for="item in review.observations" :key="item.id">{{ item.statement }}</li></ul></section>
          <section><h3>候选建议</h3><p v-if="!review.recommendations.length" class="v2-quiet-copy">系统没有生成候选建议；这不会阻止治疗师作出决定。</p><p v-for="item in review.recommendations" :key="item.id">{{ item.candidate_action }}</p></section>
        </div>
      </section>

      <section class="stage-decision-section">
        <div class="review-section-heading"><div><p class="v2-context">治疗师决定</p><h2>决定下一阶段怎么安排</h2></div><span class="review-badge">最终判断由治疗师作出</span></div>
        <div v-if="review.status === 'draft'" class="stage-ready-prompt"><div><strong>先确认事实快照完整</strong><p>进入可决定状态后，这份复核快照将锁定，后续训练会进入新的复核记录。</p></div><button class="v2-button primary" :disabled="busy" @click="markReady">{{ busy ? '正在检查…' : '事实已核对，开始决定' }}</button></div>
        <form v-else-if="review.status === 'ready_for_decision'" class="stage-decision-form" @submit.prevent="submitDecision">
          <label><span>决定类型</span><select v-model="decisionType"><option value="continue_current_plan">继续当前方案</option><option value="adjust_stage_focus">调整阶段重点并创建新方案</option><option value="adjust_strategy">调整训练策略并创建新方案</option><option value="request_formal_assessment">请求正式评估</option><option value="add_clinical_note">记录专业观察</option><option value="no_action">确认无需处理</option></select></label>
          <label v-if="createsPlan"><span>新的阶段重点</span><input v-model="stageFocus" maxlength="160" required placeholder="描述患者下一阶段要练习的能力" /></label>
          <label class="stage-decision-reason"><span>专业理由</span><textarea v-model="reason" rows="4" required placeholder="结合原音、人工复核和可比较事实说明你的判断"></textarea></label>
          <div class="stage-decision-impact"><strong>决定会产生的结果</strong><p v-if="createsPlan">生成可编辑的方案草稿；待办保持“等待方案发布”，患者继续使用当前已发布方案。</p><p v-else-if="decisionType === 'request_formal_assessment'">创建正式评估待办；当前复核来源待办会记录处理结果。</p><p v-else-if="decisionType === 'add_clinical_note'">将专业观察作为本次决定理由留档，并关闭来源待办。</p><p v-else-if="decisionType === 'no_action'">记录误报/无需处理理由，并关闭来源待办。</p><p v-else>记录治疗师决定并关闭本次来源待办。</p></div>
          <button class="v2-button primary" :disabled="busy || !reason.trim()">{{ busy ? '正在保存决定…' : createsPlan ? '保存决定并编辑新方案' : '确认并保存阶段决定' }}</button>
        </form>
        <div v-else-if="review.decision" class="stage-decision-result">
          <p class="v2-context">决定已保存 · {{ formatDate(review.decision.decided_at) }}</p><h3>{{ decisionLabel(review.decision.decision_type) }}</h3><p>{{ review.decision.reason }}</p>
          <RouterLink v-if="draftPlanId" class="v2-button primary" :to="`/therapist/plans/${draftPlanId}/edit?sourceReview=${review.id}`">编辑方案草稿</RouterLink>
          <RouterLink v-else-if="review.decision.resulting_training_plan_version_id" class="v2-button secondary" to="/therapist/plans">查看训练方案</RouterLink>
          <span v-if="review.decision.attention_resolution_policy === 'wait_plan'" class="review-badge alert">待办等待方案发布</span>
          <span v-else class="review-badge positive">待办已按决定处理</span>
        </div>
      </section>
      <p class="review-live-status" role="status" aria-live="polite">{{ liveMessage }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reviewWorkflowApi, newRequestKey, type StageReviewData } from '@/api/reviewWorkflow'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const review = ref<StageReviewData | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const liveMessage = ref('')
const decisionType = ref('continue_current_plan')
const reason = ref('')
const pendingDecisionRequest = ref<{ fingerprint: string; key: string } | null>(null)
const stageFocus = ref('')
const createsPlan = computed(() => ['adjust_stage_focus', 'adjust_strategy', 'create_new_training_plan_version'].includes(decisionType.value))
const windowLabel = computed(() => { const value = review.value?.review_window; return value?.from || value?.to ? `${value.from ? formatDate(value.from) : '起始时间未限定'} 至 ${value.to ? formatDate(value.to) : '当前'}` : '系统默认窗口' })
const draftPlanId = computed(() => String(review.value?.decision?.result?.draft_training_plan_version_id || ''))

async function load() {
  error.value = ''
  try { review.value = await reviewWorkflowApi.stageReview(String(route.params.reviewId)) }
  catch (cause) { error.value = toUserMessage(cause, '阶段复核加载失败。'); review.value = null }
  finally { loading.value = false }
}
async function markReady() {
  busy.value = true
  error.value = ''
  try { review.value = await reviewWorkflowApi.readyStageReview(String(route.params.reviewId)); liveMessage.value = '事实快照已检查，可以记录阶段决定。' }
  catch (cause) { error.value = toUserMessage(cause, '当前事实快照还不能进入决定阶段。') }
  finally { busy.value = false }
}
async function submitDecision() {
  if (!review.value) return
  busy.value = true
  error.value = ''
  try {
    const requestPayload = {
      decision_type: decisionType.value,
      reason: reason.value.trim(),
      source_attention_item_ids: review.value.attention_item_ids,
      attention_resolution_policy: createsPlan.value ? 'wait_plan' : decisionType.value === 'no_action' ? 'dismiss' : 'resolve',
      expected_review_version: review.value.version,
      payload: createsPlan.value ? { stage_focus: stageFocus.value.trim() || review.value.active_plan?.stage_focus || '', strategy: {} } : {},
    }
    const fingerprint = JSON.stringify(requestPayload)
    if (!pendingDecisionRequest.value || pendingDecisionRequest.value.fingerprint !== fingerprint) pendingDecisionRequest.value = { fingerprint, key: newRequestKey() }
    const result = await reviewWorkflowApi.createDecision(review.value.id, { ...requestPayload, request_key: pendingDecisionRequest.value.key })
    pendingDecisionRequest.value = null
    if (createsPlan.value && result.resulting_training_plan_version_id) {
      await router.push(`/therapist/plans/${result.resulting_training_plan_version_id}/edit?sourceReview=${review.value.id}`)
    } else {
      await load()
      liveMessage.value = '阶段决定已保存，来源待办已记录处理结果。'
    }
  } catch (cause) { error.value = toUserMessage(cause, '阶段决定保存失败；请重新载入确认是否已保存。') }
  finally { busy.value = false }
}
function attentionLabel(id: string) { return id === review.value?.primary_attention_item_id ? '主要触发事项' : '关联事项' }
function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function statusLabel(value: string) { return ({ draft: '待核对', ready_for_decision: '可作决定', finalized: '已完成' } as Record<string, string>)[value] || value }
function decisionLabel(value: string) { return ({ continue_current_plan: '继续当前方案', adjust_stage_focus: '调整阶段重点', adjust_strategy: '调整训练策略', create_new_training_plan_version: '创建新方案版本', request_formal_assessment: '请求正式评估', add_clinical_note: '记录专业观察', no_action: '无需处理' } as Record<string, string>)[value] || value }
onMounted(() => { void load() })
</script>
