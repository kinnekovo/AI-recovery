<template>
  <section class="v2-page therapist-v2-page plan-editor-page">
    <div v-if="loading" class="v2-state" role="status" aria-live="polite">正在打开训练方案草稿…</div>
    <div v-else-if="!plan" class="v2-state v2-state-error" role="alert"><strong>方案草稿暂时无法打开</strong><span>{{ error }}</span><RouterLink class="v2-text-link" to="/therapist/plans">返回训练方案</RouterLink></div>
    <template v-else>
      <header class="plan-editor-header"><div><RouterLink v-if="sourceReview" class="v2-text-link" :to="`/therapist/stage-reviews/${sourceReview}`">← 返回阶段复核</RouterLink><RouterLink v-else class="v2-text-link" :to="`/therapist/plans?patient=${plan.patient_user_id}`">← 返回方案列表</RouterLink><p class="v2-context">{{ plan.patient_user_id ? patientName : '治疗师端' }} · 训练方案草稿 v{{ plan.version_number }}</p><h1>调整后续训练安排</h1><p>只有正式发布后，新方案才会影响患者接下来的正式训练。</p></div><span class="review-badge" :class="plan.status === 'draft' ? 'alert' : 'positive'">{{ plan.status === 'draft' ? '草稿，患者仍使用当前方案' : statusLabel(plan.status) }}</span></header>

      <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
      <section class="plan-editor-columns">
        <div class="plan-editor-main">
          <section class="workspace-band plan-editor-section"><div class="workspace-band-heading"><div><p class="v2-context">方案重点</p><h2>明确下一阶段目标</h2></div></div>
            <label class="plan-editor-field"><span>阶段重点</span><input v-model="stageFocus" maxlength="160" :disabled="plan.status !== 'draft'" /></label>
            <div class="plan-editor-fields"><label class="plan-editor-field"><span>训练频率</span><input v-model="frequency" maxlength="80" :disabled="plan.status !== 'draft'" placeholder="例如：每周 5 天" /></label><label class="plan-editor-field"><span>方案参考时长（分钟）</span><input v-model.number="durationMinutes" type="number" min="1" max="180" :disabled="plan.status !== 'draft'" /></label><label class="plan-editor-field"><span>整体难度</span><select v-model="difficulty" :disabled="plan.status !== 'draft'"><option value="supported">支持性</option><option value="standard">标准</option><option value="challenging">挑战性</option></select></label></div>
          </section>

          <section class="workspace-band plan-editor-section"><div class="workspace-band-heading"><div><p class="v2-context">练习编排</p><h2>调整练习顺序与要求</h2></div><span class="review-badge">{{ exerciseRules.length }} 项 · 预计 {{ estimatedMinutes }} 分钟</span></div>
            <p class="v2-quiet-copy">总预计练习时长不超过 30 分钟。上移和下移按钮可完整使用键盘操作。</p>
            <ol class="plan-exercise-list"><li v-for="(rule, index) in exerciseRules" :key="rule.task_template_id" class="plan-exercise-row"><div class="plan-exercise-position"><span>{{ index + 1 }}</span><div><button type="button" class="plan-order-button" :disabled="plan.status !== 'draft' || index === 0" :aria-label="`将 ${rule.title || '练习'} 上移`" @click="moveRule(index, -1)">上移</button><button type="button" class="plan-order-button" :disabled="plan.status !== 'draft' || index === exerciseRules.length - 1" :aria-label="`将 ${rule.title || '练习'} 下移`" @click="moveRule(index, 1)">下移</button></div></div><div class="plan-exercise-fields"><div class="plan-exercise-name"><strong>{{ rule.title || templateName(rule.task_template_id) }}</strong><small>{{ rule.exercise_type === 'scenario' ? '场景表达' : '跟读训练' }}</small></div><label><span>练习角色</span><select v-model="rule.sequence_role" :disabled="plan.status !== 'draft'"><option value="warmup">热身</option><option value="main">主要训练</option><option value="consolidation">巩固</option><option value="challenge">挑战</option></select></label><label><span>每次重复</span><input v-model.number="rule.target_repetitions" type="number" min="1" max="20" :disabled="plan.status !== 'draft'" /></label><label><span>预计秒数</span><input v-model.number="rule.estimated_duration_seconds" type="number" min="30" max="900" step="30" :disabled="plan.status !== 'draft'" /></label><label><span>难度</span><select v-model="rule.difficulty" :disabled="plan.status !== 'draft'"><option value="supported">支持性</option><option value="standard">标准</option><option value="challenging">挑战性</option></select></label><label v-if="rule.exercise_type === 'scenario'"><span>信息单元上限</span><input v-model.number="rule.max_information_units" type="number" min="1" max="20" :disabled="plan.status !== 'draft'" /></label></div><button type="button" class="v2-text-link plan-remove-button" :disabled="plan.status !== 'draft'" @click="removeRule(index)">移除这项练习</button></li></ol>
            <div v-if="plan.status === 'draft'" class="plan-add-exercise"><label><span>添加练习</span><select v-model="templateToAdd"><option value="">选择练习模板</option><option v-for="template in availableTemplates" :key="template.id" :value="template.id">{{ template.title }} · {{ template.task_type === 'scenario' ? '场景表达' : '跟读训练' }}</option></select></label><button class="v2-button secondary" :disabled="!templateToAdd || exerciseRules.length >= 20" @click="addRule">添加到方案</button></div>
          </section>

          <section class="workspace-band plan-diff-section"><div class="workspace-band-heading"><div><p class="v2-context">版本差异</p><h2>与当前正式方案比较</h2></div><button class="v2-text-link" :disabled="diffLoading" @click="loadDiff">{{ diffLoading ? '正在刷新…' : '刷新差异' }}</button></div><div v-if="diffError" class="v2-inline-error" role="alert">{{ diffError }}</div><template v-else-if="diff"><div class="plan-diff-row"><strong>阶段重点</strong><span>{{ baselineFocus || '无旧版本' }}</span><ArrowRight aria-hidden="true"/><span>{{ stageFocus || '未填写' }}</span></div><div class="plan-diff-row"><strong>练习项目</strong><span>{{ baselineRuleSummary }}</span><ArrowRight aria-hidden="true"/><span>{{ currentRuleSummary }}</span></div><div class="plan-diff-row"><strong>参考时长</strong><span>{{ baselineDuration }}</span><ArrowRight aria-hidden="true"/><span>{{ estimatedMinutes }} 分钟</span></div></template><p v-else class="v2-quiet-copy">该草稿暂时没有可比较的已发布基线。</p></section>

          <section v-if="plan.status === 'draft'" class="workspace-band plan-preview-section"><div class="workspace-band-heading"><div><p class="v2-context">患者视角预览</p><h2>患者将看到的训练安排</h2></div></div><div class="patient-plan-preview"><span>下一阶段重点</span><h3>{{ stageFocus || '尚未填写训练重点' }}</h3><p>{{ frequency || '训练频率待设置' }} · 约 {{ estimatedMinutes }} 分钟</p><ol><li v-for="(rule, index) in exerciseRules" :key="rule.task_template_id"><span>{{ index + 1 }}</span><div><strong>{{ rule.title || templateName(rule.task_template_id) }}</strong><small>{{ roleLabel(rule.sequence_role) }} · {{ rule.target_repetitions }} 次练习</small></div></li></ol></div></section>
        </div>

        <aside class="plan-editor-sidebar"><div class="plan-editor-sticky"><section class="plan-publish-check"><h2>发布前检查</h2><ul><li :class="stageFocus.trim() ? 'passed' : 'missing'">{{ stageFocus.trim() ? '已' : '请' }}填写阶段重点</li><li :class="exerciseRules.length ? 'passed' : 'missing'">{{ exerciseRules.length ? '已' : '请' }}至少保留一项练习</li><li :class="orderValid ? 'passed' : 'missing'">{{ orderValid ? '顺序连续' : '重新整理练习顺序' }}</li><li :class="durationValid ? 'passed' : 'missing'">{{ durationValid ? '预计时长在限制内' : '预计总时长需不超过 30 分钟' }}</li><li :class="templatesValid ? 'passed' : 'missing'">{{ templatesValid ? '模板仍有效' : '移除已停用的练习模板' }}</li><li :class="baseStillActive ? 'passed' : 'missing'">{{ baseStillActive ? '正式方案版本未冲突' : '正式方案已变化，请刷新页面' }}</li></ul><p v-if="publishRequestText" class="plan-publish-result" role="status">{{ publishRequestText }}</p><div class="plan-editor-actions"><button v-if="plan.status === 'draft'" class="v2-button secondary" :disabled="saving || !dirty" @click="saveDraft">{{ saving ? '正在保存…' : '保存草稿' }}</button><button v-if="plan.status === 'draft'" class="v2-button primary" :disabled="saving || !canPublish" @click="publishPlan">{{ saving ? '正在处理…' : '正式发布方案' }}</button><button v-if="plan.status === 'draft'" class="v2-text-link destructive-link" :disabled="saving" @click="abandonPlan">废弃此草稿</button><RouterLink v-else class="v2-button secondary" to="/therapist/reviews">返回待复核队列</RouterLink></div></section><p class="plan-editor-safety-copy">草稿未发布前不会改变患者训练。发布成功后，来源待办才会关闭。</p></div></aside>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ArrowRight } from 'lucide-vue-next'
import { therapistApi } from '@/api/therapist'
import { reviewWorkflowApi, newRequestKey, type PlanEditorData } from '@/api/reviewWorkflow'
import type { TaskTemplate } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const plan = ref<PlanEditorData | null>(null)
const templates = ref<TaskTemplate[]>([])
const exerciseRules = ref<PlanEditorData['exercise_rules']>([])
const diff = ref<{ baseline_plan_id: string | null; baseline: Record<string, unknown> | null; draft: Record<string, unknown> } | null>(null)
const loading = ref(true)
const saving = ref(false)
const diffLoading = ref(false)
const error = ref('')
const diffError = ref('')
const dirty = ref(false)
const stageFocus = ref('')
const frequency = ref('daily')
const durationMinutes = ref(15)
const difficulty = ref('standard')
const templateToAdd = ref('')
const abandonReason = ref('')
const publishRequestText = ref('')
const publishRequestKey = ref('')
const sourceReview = computed(() => String(route.query.sourceReview || ''))
const patientName = ref('')
const estimatedSeconds = computed(() => exerciseRules.value.reduce((sum, rule) => sum + Number(rule.estimated_duration_seconds || 0), 0))
const estimatedMinutes = computed(() => Math.round(estimatedSeconds.value / 60 * 10) / 10)
const durationValid = computed(() => exerciseRules.value.length > 0 && estimatedSeconds.value <= 1800)
const orderValid = computed(() => exerciseRules.value.every((rule, index) => rule.order_index === index))
const templatesValid = computed(() => exerciseRules.value.every(rule => templates.value.some(template => template.id === rule.task_template_id && template.is_active)))
const baseStillActive = computed(() => (plan.value?.active_plan?.id || null) === (plan.value?.supersedes_id || null))
const canPublish = computed(() => dirty.value ? false : Boolean(stageFocus.value.trim() && exerciseRules.value.length && orderValid.value && durationValid.value && templatesValid.value && baseStillActive.value))
const availableTemplates = computed(() => templates.value.filter(template => template.is_active && !exerciseRules.value.some(rule => rule.task_template_id === template.id)))
const baseline = computed(() => diff.value?.baseline as { stage_focus?: string; strategy?: Record<string, unknown>; exercise_rules?: Array<Record<string, unknown>> } | null)
const baselineFocus = computed(() => baseline.value?.stage_focus || '没有已发布基线')
const baselineRuleSummary = computed(() => baseline.value?.exercise_rules?.map(item => String(item.title || '练习')).join('、') || '无旧版本')
const currentRuleSummary = computed(() => exerciseRules.value.map(item => item.title || templateName(item.task_template_id)).join('、') || '尚未添加练习')
const baselineDuration = computed(() => { const rows = baseline.value?.exercise_rules || []; const seconds = rows.reduce((sum, item) => sum + Number(item.estimated_duration_seconds || 0), 0); return seconds ? `${Math.round(seconds / 60 * 10) / 10} 分钟` : '无旧版本' })

watch([stageFocus, frequency, durationMinutes, difficulty, exerciseRules], () => { if (plan.value && !loading.value) dirty.value = true }, { deep: true })
async function load() {
  loading.value = true
  error.value = ''
  try {
    const planId = String(route.params.planId)
    const [loadedPlan, available] = await Promise.all([reviewWorkflowApi.plan(planId), therapistApi.taskTemplates()])
    plan.value = loadedPlan
    templates.value = available
    patientName.value = loadedPlan.patient_name
    stageFocus.value = loadedPlan.stage_focus
    frequency.value = String(loadedPlan.strategy.frequency || 'daily')
    durationMinutes.value = Number(loadedPlan.strategy.duration || 15)
    difficulty.value = String(loadedPlan.strategy.difficulty || 'standard')
    exerciseRules.value = loadedPlan.exercise_rules.map(rule => ({ ...rule, sequence_role: rule.sequence_role || 'main', estimated_duration_seconds: rule.estimated_duration_seconds || 90 }))
    dirty.value = false
    await loadDiff()
  } catch (cause) { error.value = toUserMessage(cause, '方案或练习模板加载失败。'); plan.value = null }
  finally { loading.value = false }
}
async function loadDiff() {
  if (!plan.value) return
  diffLoading.value = true
  diffError.value = ''
  try { diff.value = await reviewWorkflowApi.planDiff(plan.value.id) }
  catch (cause) { diffError.value = toUserMessage(cause, '版本差异暂时无法读取。') }
  finally { diffLoading.value = false }
}
function templateName(id: string) { return templates.value.find(item => item.id === id)?.title || '已停用的练习模板' }
function addRule() {
  const template = availableTemplates.value.find(item => item.id === templateToAdd.value)
  if (!template || !plan.value) return
  const scenario = template.task_type === 'scenario'
  exerciseRules.value.push({ id: `new-${template.id}`, task_template_id: template.id, exercise_type: template.task_type, order_index: exerciseRules.value.length, title: template.title, target_repetitions: 1, sequence_role: exerciseRules.value.length === 0 ? 'warmup' : 'main', estimated_duration_seconds: scenario ? 210 : 90, difficulty: difficulty.value, max_information_units: scenario ? 5 : null, prompt_policy: { levels: 3 }, scene_scope: {} })
  templateToAdd.value = ''
}
function moveRule(index: number, delta: number) {
  const next = index + delta
  if (next < 0 || next >= exerciseRules.value.length) return
  const reordered = [...exerciseRules.value]
  const [current] = reordered.splice(index, 1)
  reordered.splice(next, 0, current)
  exerciseRules.value = reordered.map((rule, order_index) => ({ ...rule, order_index }))
}
function removeRule(index: number) { exerciseRules.value = exerciseRules.value.filter((_, current) => current !== index).map((rule, order_index) => ({ ...rule, order_index })) }
function requestPayload() {
  if (!plan.value) throw new Error('方案尚未加载')
  return {
    stage_focus: stageFocus.value.trim(),
    strategy: { ...plan.value.strategy, frequency: frequency.value, duration: durationMinutes.value, difficulty: difficulty.value, forms: [...new Set(exerciseRules.value.map(rule => rule.exercise_type))] },
    rehabilitation_goal_id: plan.value.rehabilitation_goal_id,
    expected_active_plan_id: plan.value.active_plan?.id || null,
    exercise_rules: exerciseRules.value.map(({ id: _id, title: _title, ...rule }) => ({ ...rule, order_index: Number(rule.order_index), estimated_duration_seconds: Number(rule.estimated_duration_seconds), target_repetitions: Number(rule.target_repetitions) })),
  }
}
async function saveDraft() {
  if (!plan.value) return
  saving.value = true
  error.value = ''
  try { plan.value = await reviewWorkflowApi.updatePlan(plan.value.id, requestPayload()); dirty.value = false; await loadDiff(); publishRequestText.value = '草稿已保存；患者继续使用当前已发布方案。' }
  catch (cause) { error.value = toUserMessage(cause, '方案草稿保存失败。') }
  finally { saving.value = false }
}
async function publishPlan() {
  if (!plan.value || !canPublish.value) return
  if (!window.confirm('发布后，新方案将在患者下一次新建正式训练时生效。只有发布成功，来源待办才会关闭。确认发布吗？')) return
  saving.value = true
  error.value = ''
  try {
    publishRequestKey.value ||= newRequestKey()
    plan.value = await reviewWorkflowApi.publishPlan(plan.value.patient_user_id, plan.value.id, plan.value.active_plan?.id || null, publishRequestKey.value)
    dirty.value = false
    publishRequestText.value = `方案 v${plan.value.version_number} 已发布。`
    if (sourceReview.value) await router.push(`/therapist/stage-reviews/${sourceReview.value}`)
    else await load()
  } catch (cause) { error.value = toUserMessage(cause, '发布失败；当前正式方案与待办状态保持不变。请刷新方案差异后重试。') }
  finally { saving.value = false }
}
async function abandonPlan() {
  if (!plan.value) return
  const suppliedReason = window.prompt('请说明废弃草稿的原因。来源待办会回到阶段复核，要求你重新决定。', abandonReason.value)
  if (!suppliedReason?.trim()) return
  saving.value = true
  error.value = ''
  try {
    const abandoned = await reviewWorkflowApi.abandonPlan(plan.value.id, suppliedReason.trim())
    plan.value = abandoned
    dirty.value = false
    if (abandoned.successor_stage_review_id) await router.push(`/therapist/stage-reviews/${abandoned.successor_stage_review_id}`)
    else if (sourceReview.value) await router.push(`/therapist/stage-reviews/${sourceReview.value}`)
    else await router.push('/therapist/plans')
  } catch (cause) { error.value = toUserMessage(cause, '废弃草稿失败。') }
  finally { saving.value = false }
}
function roleLabel(value: string) { return ({ warmup: '热身', main: '主要训练', consolidation: '巩固', challenge: '挑战' } as Record<string, string>)[value] || '主要训练' }
function statusLabel(value: string) { return ({ active: '当前生效', superseded: '历史版本', abandoned: '已废弃', draft: '草稿' } as Record<string, string>)[value] || value }
onBeforeRouteLeave(() => { if (dirty.value && !window.confirm('方案还有未保存的修改，确定离开吗？')) return false })
onMounted(() => { void load() })
</script>
