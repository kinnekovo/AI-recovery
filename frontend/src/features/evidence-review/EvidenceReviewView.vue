<template>
  <section class="v2-page therapist-v2-page evidence-review-page">
    <div v-if="loading" class="v2-state" role="status" aria-live="polite">正在载入患者原始材料与评估证据…</div>
    <div v-else-if="!bundle" class="v2-state v2-state-error" role="alert"><strong>复核材料暂时无法打开</strong><span>{{ error }}</span><button class="v2-button secondary" @click="load">重新加载</button><RouterLink class="v2-text-link" to="/therapist/reviews">返回待复核队列</RouterLink></div>
    <template v-else>
      <header class="evidence-review-context">
        <div><RouterLink to="/therapist/reviews" class="v2-text-link">← 返回待复核队列</RouterLink><p class="v2-context">{{ bundle.patient.name }} · {{ typeLabel(bundle.attention.type) }}</p><h1>{{ bundle.attention.summary }}</h1><p>{{ bundle.goal?.description || '尚未建立正式康复目标。' }}</p></div>
        <dl><div><dt>当前方案</dt><dd>{{ bundle.active_plan ? `v${bundle.active_plan.version_number} · ${bundle.active_plan.stage_focus}` : '尚无已发布方案' }}</dd></div><div><dt>待办状态</dt><dd>{{ statusLabel(bundle.attention.status) }}</dd></div><div><dt>负责人</dt><dd>{{ bundle.attention.assigned_to || '待接手' }}</dd></div></dl>
      </header>

      <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
      <section class="evidence-review-why"><div><strong>为什么需要复核</strong><p>{{ bundle.attention.summary }}</p></div><span :class="bundle.attention.priority === 'high' ? 'review-badge alert' : 'review-badge'">{{ priorityLabel(bundle.attention.priority) }}</span><span class="review-badge">{{ bundle.attention.evidence_count }} 条关联来源</span></section>

      <section class="evidence-review-section">
        <div class="review-section-heading"><div><p class="v2-context">原始材料</p><h2>先听原音，再看系统结果</h2></div><p>原始录音与原始转写保持不变；复核内容会另存为版本。</p></div>
        <div v-if="bundle.source.attempts.length" class="review-source-list">
          <article v-for="attempt in bundle.source.attempts" :key="attempt.id" class="review-source-row">
            <div class="review-source-heading"><div><h3>{{ attempt.task.title }}</h3><p>{{ attempt.task.session_date || '训练日期未记录' }} · 第 {{ attempt.attempt_no }} 次作答 · 提示等级 {{ attempt.prompt_level }}</p></div><span class="review-badge">{{ qualityLabel(attempt.audio_quality) }}</span></div>
            <dl class="review-source-facts"><div><dt>练习目标</dt><dd>{{ attempt.task.target || '未提供目标文本' }}</dd></div><div><dt>数据状态</dt><dd>{{ attempt.analysis_status === 'completed' ? '分析已完成' : '分析未完成' }} · {{ attempt.technical_validity }}</dd></div></dl>
            <div v-if="attempt.audio" class="review-audio-block"><span>患者原音</span><audio controls preload="none" :src="attempt.audio.url" @play="audioOpened(attempt.audio.file_id)">浏览器不支持音频播放。</audio></div>
            <div v-else class="review-audio-missing" role="status"><strong>未找到本次录音</strong><span>依赖原音判断的维度只能标记为“无法判断”，可将待办转为等待补充。</span></div>
            <div class="review-transcript"><strong>ASR 原始转写</strong><p>{{ attempt.transcript || '未生成转写；这不代表患者没有表达。' }}</p></div>
          </article>
        </div>
        <div v-for="dialogue in bundle.source.dialogues" :key="dialogue.id" class="review-dialogue-block">
          <div class="review-source-heading"><div><h3>{{ dialogue.task.title }}</h3><p>{{ dialogue.task.session_date || '训练日期未记录' }} · {{ dialogue.contract_version }} · {{ dialogue.status === 'completed' ? '对话已结束' : '对话未完成' }}</p></div><span class="review-badge">{{ dialogue.turns.length }} 轮对话</span></div>
          <p class="review-contract-copy">{{ contractGoal(dialogue.contract) }}</p>
          <ol class="review-turn-list"><li v-for="turn in dialogue.turns" :key="turn.id" :class="turn.speaker === 'patient' ? 'patient-turn' : 'agent-turn'"><div class="review-turn-top"><strong>{{ turn.speaker_label }}</strong><time>{{ formatDate(turn.created_at) }}</time></div><p>{{ turn.text || '没有识别到文字内容。' }}</p><audio v-if="turn.audio" controls preload="none" :src="turn.audio.url" @play="audioOpened(turn.audio.file_id)">浏览器不支持音频播放。</audio><span v-else-if="turn.speaker === 'patient'" class="review-turn-no-audio">该回合没有录音</span></li></ol>
        </div>
        <div v-if="!bundle.source.attempts.length && !bundle.source.dialogues.length" class="review-source-empty"><strong>没有解析到训练来源</strong><p>系统保留了待办，但无法定位原始训练材料。请将待办标记为等待补充，避免基于缺失证据作出判断。</p></div>
      </section>

      <section class="evidence-review-section">
        <div class="review-section-heading"><div><p class="v2-context">系统测量</p><h2>评估结果与质量门控</h2></div><span class="review-badge">系统结果仅供专业核对</span></div>
        <div v-if="!bundle.evaluation_runs.length" class="review-source-empty"><strong>尚无可复核的评估运行</strong><p>可记录“等待补充”并由后续复核处理；当前没有可供确认的自动分数。</p></div>
        <template v-for="run in bundle.evaluation_runs" :key="run.id">
          <article class="review-run-block">
            <div class="review-source-heading"><div><h3>{{ domainLabel(run.domain) }}</h3><p>{{ run.adoption_status === 'adopted' ? '当前采用版本' : run.adoption_status === 'superseded' ? '历史版本' : '候选结果' }} · {{ formatDate(run.created_at) }} · {{ run.algorithm_version }}</p></div><span class="review-badge" :class="run.profile_eligibility ? 'positive' : 'alert'">{{ run.profile_eligibility ? '可进入画像' : '不能进入画像' }}</span></div>
            <div v-if="qualityReasons(run).length" class="review-quality-note"><strong>质量门控</strong><span>{{ qualityReasons(run).map(reasonLabel).join('、') }}</span><p>质量或数据问题不能解释为能力下降。</p></div>
            <div class="review-dimension-table" role="table" :aria-label="`${domainLabel(run.domain)}各维度结果`"><div class="review-dimension-head" role="row"><span role="columnheader">测量维度</span><span role="columnheader">自动结果</span><span role="columnheader">状态</span><span role="columnheader">证据说明</span></div><div v-for="dimension in run.dimension_results" :key="dimension.id" class="review-dimension-row" role="row"><strong role="cell">{{ dimensionLabel(dimension.dimension_code) }}</strong><span role="cell">{{ dimensionValue(dimension) }}</span><span role="cell">{{ dimensionStatus(dimension.status) }}</span><span role="cell">{{ evidenceSummary(dimension.evidence_snapshot) }}</span></div></div>
            <details class="review-technical-details"><summary>技术详情与来源版本</summary><p>输入来源：{{ run.source_type }} · {{ run.source_id }} · 画像资格：{{ run.profile_eligibility ? '允许' : '不允许' }}</p><pre>{{ JSON.stringify({ quality_gate: run.quality_gate, input_provenance: run.input_provenance, limitations: run.limitations }, null, 2) }}</pre></details>
          </article>
        </template>
      </section>

      <section v-if="bundle.evaluation_runs.length && !readOnly" class="evidence-review-section review-form-section">
        <div class="review-section-heading"><div><p class="v2-context">治疗师复核</p><h2>确认、修正，或说明无法判断</h2></div><p>修正必须包含依据。录音不可用时，系统会限制为“无法判断”。</p></div>
        <form class="review-form" @submit.prevent="submitReview">
          <label><span>评估运行</span><select v-model="selectedRunId" @change="syncDimension"><option v-for="run in bundle.evaluation_runs" :key="run.id" :value="run.id">{{ domainLabel(run.domain) }} · {{ run.adoption_status === 'adopted' ? '当前采用' : '历史版本' }} · {{ formatDate(run.created_at) }}</option></select></label>
          <label><span>复核维度</span><select v-model="selectedDimensionId" @change="syncDimension"><option v-for="dimension in selectedRun?.dimension_results || []" :key="dimension.id" :value="dimension.id">{{ dimensionLabel(dimension.dimension_code) }} · {{ dimensionValue(dimension) }}</option></select></label>
          <fieldset class="review-action-options"><legend>本次处理</legend><label><input v-model="action" type="radio" value="confirmed" :disabled="!selectedRunHasAudio" /><span><strong>确认自动结果</strong><small>原音与证据支持当前测量</small></span></label><label><input v-model="action" type="radio" value="corrected" :disabled="!selectedRunHasAudio" /><span><strong>修正结果</strong><small>保存新的人工复核版本，不覆盖自动结果</small></span></label><label><input v-model="action" type="radio" value="unjudgeable" /><span><strong>无法判断</strong><small>证据不足、录音缺失或质量不合格</small></span></label></fieldset>
          <div v-if="action === 'corrected'" class="review-correction-fields"><label><span>修正原因</span><select v-model="reasonCode"><option value="other">其他临床修正</option><option value="asr_mismatch">ASR 转写与原音不一致</option><option value="insufficient_evidence">自动证据不足</option><option value="noise">录音质量影响判断</option></select></label><label v-if="selectedDimension?.value !== null"><span>修正数值 {{ selectedDimension?.unit || '' }}</span><input v-model="editedValue" type="number" step="any" /></label><label v-if="selectedDimension?.level"><span>修正等级或结论</span><input v-model="editedLevel" maxlength="80" /></label><label><span>修正状态</span><select v-model="editedStatus"><option value="measured">已测得</option><option value="not_observed">未观察到</option><option value="unavailable">不可用</option><option value="not_applicable">不适用</option></select></label><label v-if="selectedRun?.domain === 'functional_communication'" class="review-wide-field"><span>原音校正转写（可选）</span><textarea v-model="transcriptOverride" rows="3" placeholder="仅在治疗师回听原音后填写；原始 ASR 转写会保留"></textarea></label><label v-if="selectedRun?.domain === 'functional_communication'" class="review-wide-field"><span>{{ reasonCode === 'asr_mismatch' ? '在校正转写中定位的患者原话' : '可在原始转写中定位的患者原话（可选）' }}</span><input v-model="quotedEvidence" maxlength="500" placeholder="填写患者实际表达的原话片段" /></label></div>
          <label v-if="action === 'unjudgeable'"><span>无法判断原因</span><select v-model="reasonCode" required><option value="">请选择原因</option><option value="audio_unavailable">录音不可用</option><option value="noise">噪声或录音质量问题</option><option value="insufficient_evidence">证据不足</option><option value="task_not_applicable">任务不适用</option><option value="not_observed">本次未观察到</option><option value="other">其他</option></select></label>
          <label><span>{{ action === 'confirmed' ? '补充说明（可选）' : '复核依据' }}</span><textarea v-model="reason" :required="action !== 'confirmed'" rows="3" :placeholder="action === 'confirmed' ? '可补充需要留存的说明' : '写明你从原音和证据中核对到的内容'"></textarea></label>
          <div class="review-submit-summary"><strong>保存前确认</strong><p>{{ bundle.patient.name }} · {{ dimensionLabel(selectedDimension?.dimension_code || '') }} · {{ actionLabel(action) }}</p><span v-if="action === 'corrected'">自动值仍保留；人工结果会作为新的 adopted 评估版本记录。</span><span v-else-if="action === 'unjudgeable'">该维度会被标记为不可用，不会作为 0 分进入画像。</span><span v-else>追加治疗师确认记录，不更改自动评估运行。</span></div>
          <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
          <button class="v2-button primary" :disabled="!canSubmitReview">{{ saving ? '正在保存复核…' : action === 'corrected' ? '确认并保存修正' : action === 'unjudgeable' ? '保存无法判断记录' : '确认自动结果' }}</button>
        </form>
      </section>

      <section v-if="bundle.review_history.length" class="evidence-review-section">
        <div class="review-section-heading"><div><p class="v2-context">审计记录</p><h2>此前的复核</h2></div></div>
        <ol class="review-history-list"><li v-for="entry in bundle.review_history" :key="entry.id"><time>{{ entry.created_at ? formatDate(entry.created_at) : '时间未记录' }}</time><strong>{{ actionLabel(entry.action) }}</strong><span>{{ entry.reason || '未填写说明' }}</span><details><summary>查看修订前后快照</summary><pre>{{ JSON.stringify({ automatic: entry.automatic, revised: entry.revised }, null, 2) }}</pre></details></li></ol>
      </section>

      <section v-if="bundle.attention.status === 'in_review' || bundle.attention.status === 'waiting_information'" class="review-next-step">
        <div><p class="v2-context">下一步</p><h2>形成阶段决定</h2><p>把本条待办和本次复核证据带入阶段复核，只纳入你明确选择的来源。</p></div>
        <div class="review-next-actions"><span v-if="bundle.attention.status === 'waiting_information'" class="review-badge alert">当前待办已暂停，继续将按现有证据进入阶段决定</span><button v-if="bundle.attention.status === 'in_review' && (bundle.quality.audio_missing || !bundle.quality.source_refs_resolved)" class="v2-button secondary" :disabled="saving || readOnly" @click="waitForInformation">等待补充材料</button><button class="v2-button primary" :disabled="saving || readOnly" @click="createStageReview">{{ bundle.attention.status === 'waiting_information' ? '仍按当前证据形成阶段决定' : '继续到阶段决定' }}</button></div>
      </section>
      <section v-else-if="bundle.attention.status === 'waiting_plan_publish'" class="review-next-step"><div><p class="v2-context">待办等待方案</p><h2>方案尚未发布</h2><p>待办会在方案发布后自动关闭。</p></div><RouterLink class="v2-button primary" to="/therapist/plans">查看训练方案</RouterLink></section>
      <p v-if="readOnly && !['resolved', 'dismissed', 'waiting_plan_publish'].includes(bundle.attention.status)" class="review-readonly-note" role="status">该待办由其他治疗师负责，当前页面只读。可联系负责人转交后再操作。</p>
      <p class="review-live-status" role="status" aria-live="polite">{{ liveMessage }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { reviewWorkflowApi, newRequestKey, type EvaluationReviewPayload, type EvaluationRunReview, type ReviewBundle, type ReviewDimension } from '@/api/reviewWorkflow'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const bundle = ref<ReviewBundle | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const liveMessage = ref('')
const selectedRunId = ref('')
const selectedDimensionId = ref('')
const action = ref<'confirmed' | 'corrected' | 'unjudgeable'>('confirmed')
const editedValue = ref('')
const editedLevel = ref('')
const editedStatus = ref('measured')
const reason = ref('')
const reasonCode = ref<EvaluationReviewPayload['reason_code'] | ''>('')
const pendingReviewRequest = ref<{ fingerprint: string; key: string } | null>(null)
const transcriptOverride = ref('')
const quotedEvidence = ref('')
const openedAudioIds = new Set<string>()
const attentionId = computed(() => String(route.params.attentionItemId))
const selectedRun = computed<EvaluationRunReview | undefined>(() => bundle.value?.evaluation_runs.find(run => run.id === selectedRunId.value))
const selectedDimension = computed<ReviewDimension | undefined>(() => selectedRun.value?.dimension_results.find(dimension => dimension.id === selectedDimensionId.value))
const readOnly = computed(() => {
  if (!bundle.value) return true
  if (['resolved', 'dismissed', 'waiting_plan_publish'].includes(bundle.value.attention.status)) return true
  const ownerId = bundle.value.attention.assigned_to_user_id
  return Boolean(ownerId && ownerId !== auth.me?.user.id && auth.me?.user.role !== 'admin')
})
const canSubmitReview = computed(() => Boolean(!saving.value && !readOnly.value && selectedRun.value && selectedDimension.value && (action.value === 'unjudgeable' || selectedRunHasAudio.value) && (action.value === 'confirmed' || reason.value.trim()) && (action.value !== 'unjudgeable' || reasonCode.value)))
const selectedRunHasAudio = computed(() => {
  if (!bundle.value || !selectedRun.value) return false
  if (selectedRun.value.source_type === 'attempt') return bundle.value.source.attempts.some(item => item.id === selectedRun.value?.source_id && item.audio)
  if (selectedRun.value.source_type === 'dialogue_session') return bundle.value.source.dialogues.some(item => item.id === selectedRun.value?.source_id && item.turns.some(turn => turn.speaker === 'patient' && turn.audio))
  return false
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const existing = await reviewWorkflowApi.bundle(attentionId.value)
    if (['open', 'acknowledged'].includes(existing.attention.status) && (!existing.attention.assigned_to_user_id || existing.attention.assigned_to_user_id === auth.me?.user.id || auth.me?.user.role === 'admin')) await reviewWorkflowApi.begin(attentionId.value)
    bundle.value = await reviewWorkflowApi.bundle(attentionId.value)
    if (!selectedRunId.value || !bundle.value.evaluation_runs.some(run => run.id === selectedRunId.value)) selectedRunId.value = bundle.value.evaluation_runs.find(run => run.adoption_status === 'adopted')?.id || bundle.value.evaluation_runs[0]?.id || ''
    syncDimension()
  } catch (cause) {
    error.value = toUserMessage(cause, '复核证据包加载失败。')
    bundle.value = null
  } finally {
    loading.value = false
  }
}
function syncDimension() {
  const dimension = selectedRun.value?.dimension_results.find(item => item.id === selectedDimensionId.value) || selectedRun.value?.dimension_results[0]
  selectedDimensionId.value = dimension?.id || ''
  editedValue.value = dimension?.value === null || dimension?.value === undefined ? '' : String(dimension.value)
  editedLevel.value = dimension?.level || ''
  editedStatus.value = dimension?.status || 'measured'
}
async function audioOpened(fileId: string) {
  if (openedAudioIds.has(fileId)) return
  openedAudioIds.add(fileId)
  try { await reviewWorkflowApi.audioOpened(attentionId.value, fileId) } catch { openedAudioIds.delete(fileId) }
}
async function submitReview() {
  if (!bundle.value || !selectedRun.value || !selectedDimension.value) return
  saving.value = true
  error.value = ''
  try {
    const revised: Record<string, unknown> = {}
    if (action.value === 'corrected') {
      if (editedValue.value !== '') revised.value = Number(editedValue.value)
      if (editedLevel.value.trim()) revised.level = editedLevel.value.trim()
      revised.status = editedStatus.value
    }
    const evidenceOverride: Record<string, unknown> = {}
    if (transcriptOverride.value.trim()) evidenceOverride.transcript_override = transcriptOverride.value.trim()
    if (quotedEvidence.value.trim()) evidenceOverride.quoted_evidence = quotedEvidence.value.trim()
    const requestPayload = {
      review_action: action.value,
      dimension_result_id: selectedDimension.value.id,
      revised_value_snapshot: revised,
      evidence_override: evidenceOverride,
      reason_code: reasonCode.value || (action.value === 'corrected' ? 'other' : undefined),
      reason: reason.value.trim() || undefined,
    }
    const fingerprint = JSON.stringify(requestPayload)
    if (!pendingReviewRequest.value || pendingReviewRequest.value.fingerprint !== fingerprint) pendingReviewRequest.value = { fingerprint, key: newRequestKey() }
    const payload = { ...requestPayload, review_request_key: pendingReviewRequest.value.key }
    await reviewWorkflowApi.submitEvaluationReview(attentionId.value, selectedRun.value.id, payload)
    liveMessage.value = action.value === 'corrected' ? '修正已保存，原始自动结果仍可追溯。' : action.value === 'unjudgeable' ? '无法判断记录已保存。' : '治疗师确认记录已保存。'
    reason.value = ''
    transcriptOverride.value = ''
    quotedEvidence.value = ''
    await load()
  } catch (cause) {
    error.value = toUserMessage(cause, '复核保存失败；请刷新页面确认是否已经保存后再重试。')
  } finally {
    saving.value = false
  }
}
async function createStageReview() {
  if (!bundle.value) return
  saving.value = true
  error.value = ''
  try {
    const review = await reviewWorkflowApi.createStageReview(attentionId.value, {})
    await router.push(`/therapist/stage-reviews/${review.id}`)
  } catch (cause) {
    error.value = toUserMessage(cause, '阶段复核创建失败。')
  } finally {
    saving.value = false
  }
}
async function waitForInformation() {
  saving.value = true
  error.value = ''
  try {
    await reviewWorkflowApi.waitForInformation(attentionId.value, bundle.value?.quality.audio_missing ? 'audio_unavailable' : 'source_not_resolved', reason.value.trim() || '原始材料缺失或不可访问，需要补充后再判断。')
    liveMessage.value = '待办已转为等待补充材料。'
    await load()
  } catch (cause) { error.value = toUserMessage(cause, '无法将待办转为等待补充。') }
  finally { saving.value = false }
}
function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function typeLabel(value: string) { return ({ patient_help_request: '患者请求帮助', repeated_comparable_difficulty: '持续困难', increasing_prompt_dependency: '提示依赖增加', repeated_ungradable_attempt: '连续无法评分', training_adherence_drop: '训练坚持度下降', assessment_due: '正式评估到期', comparable_metric_decline: '趋势变化', evaluation_write_failure: '数据处理异常' } as Record<string, string>)[value] || '需要复核' }
function statusLabel(value: string) { return ({ open: '待接手', acknowledged: '已接手', in_review: '复核中', waiting_information: '等待补充', waiting_plan_publish: '等待方案发布', resolved: '已完成', dismissed: '已忽略' } as Record<string, string>)[value] || value }
function priorityLabel(value: string) { return value === 'high' ? '高优先' : value === 'low' ? '一般' : '普通优先' }
function domainLabel(value: string) { return value === 'repeat' ? '跟读训练' : value === 'functional_communication' ? '场景沟通' : value === 'clinical_stage' ? '阶段支撑' : '专业评估' }
function dimensionLabel(value: string) { return ({ content_reproduction: '内容复现', fluency_efficiency: '表达效率', disfluency_events: '流利度事件', voice_state: '声音状态', independence: '独立程度', articulation_evidence: '发音观察', goal_achievement: '目标完成', information_sufficiency: '信息完整度', response_ability: '回应能力', relevance_and_organization: '相关性与组织', repair_ability: '沟通修复' } as Record<string, string>)[value] || value || '评估维度' }
function dimensionStatus(value: string) { return ({ measured: '已测得', not_observed: '未观察到', unavailable: '不可用', not_applicable: '不适用' } as Record<string, string>)[value] || value }
function dimensionValue(dimension: ReviewDimension) { if (dimension.value !== null && dimension.value !== undefined) return `${dimension.value}${dimension.unit || ''}`; return dimension.level || dimensionStatus(dimension.status) }
function qualityLabel(value: string | null) { return value ? ({ good: '录音质量良好', pass: '录音质量通过', poor: '录音质量较差', failed: '录音不可用' } as Record<string, string>)[value] || `录音质量：${value}` : '录音质量未评估' }
function qualityReasons(run: EvaluationRunReview) { const gate = run.quality_gate as { reasons?: unknown[] }; return Array.isArray(gate.reasons) ? gate.reasons.map(String) : [] }
function reasonLabel(value: string) { return ({ quality_not_passed: '录音质量未通过', analysis_missing: '缺少分析结果', semantic_provider_not_formal: '语义来源非正式服务', asr_provider_not_formal: '语音转写来源未确认', semantic_citation_unlocatable: '证据引用无法定位', semantic_measurement_quality_insufficient: '语义证据置信度不足', dialogue_not_completed: '对话未完成', no_patient_utterance: '没有患者回合', contract_version_missing: '任务版本缺失' } as Record<string, string>)[value] || value }
function evidenceSummary(value: Record<string, unknown>) { const citations = value.citations; if (Array.isArray(citations)) return `${citations.length} 条语义引用`; const target = value.target_text_snapshot; if (typeof target === 'string' && target) return `目标句：${target}`; const count = value.opportunity_count; if (typeof count === 'number') return `${count} 次回应机会`; return '查看维度说明与原始材料' }
function contractGoal(value: Record<string, unknown>) { const contract = value as { scenario_title?: string; task_goal?: string; scene_prompt?: string }; return contract.task_goal || contract.scene_prompt || contract.scenario_title || '请结合任务目标与患者原话复核。' }
function actionLabel(value: string) { return ({ confirmed: '确认自动结果', corrected: '修正评估结果', unjudgeable: '无法判断' } as Record<string, string>)[value] || value }
onMounted(() => { void load() })
</script>
