<template>
  <section class="page-stack therapist-assessment-page therapist-workbench-page">
    <div class="page-heading therapist-review-heading workbench-header">
      <div>
        <span class="kicker">治疗师工作台</span>
        <h1>{{ selectedPatient ? selectedPatient.username : '患者训练工作台' }}</h1>
        <p>{{ selectedPatient ? `${records.length} 条训练记录 · ${selectedPatient.pending_review_count || 0} 条待复核` : '选择患者后查看训练、趋势与下一步建议。' }}</p>
      </div>
      <div class="form-actions">
        <button class="icon-button" type="button" title="刷新患者数据" :disabled="loadingPatientData" @click="reloadSelected">
          <RefreshCw :size="18" />
        </button>
        <button class="app-button primary" type="button" :disabled="exportingReport || !selectedPatientId" @click="exportStageReport">
          <FileDown :size="17" />{{ exportingReport ? '生成中' : '导出报告' }}
        </button>
      </div>
    </div>

    <p v-if="loading" class="success-text">正在加载患者列表。</p>
    <p v-if="pageError" class="error-text">{{ pageError }}</p>

    <section class="therapist-workbench-grid">
      <article class="therapist-panel patient-queue-panel">
        <div class="panel-heading">
          <div>
            <h2>患者</h2>
            <p>{{ patients.length }} 位患者</p>
          </div>
        </div>

        <label class="patient-search">
          <Search :size="16" />
          <input v-model="patientQuery" type="search" placeholder="搜索患者" />
        </label>

        <div v-if="filteredPatients.length" class="patient-picker">
          <button
            v-for="patient in filteredPatients"
            :key="patient.user_id"
            type="button"
            class="patient-row"
            :class="{ active: patient.user_id === selectedPatientId }"
            @click="selectPatient(patient.user_id)"
          >
            <span class="patient-row-title">
              <strong>{{ patient.username }}</strong>
              <em v-if="patient.pending_review_count">{{ patient.pending_review_count }}</em>
            </span>
            <span>{{ patient.training_status || '训练状态待更新' }}</span>
            <small>{{ patient.latest_assessment_at ? `最近评估：${dateLabel(patient.latest_assessment_at)}` : '暂无阶段评估' }}</small>
          </button>
        </div>
        <div v-else class="empty-state">
          <p>暂时没有患者账号。</p>
        </div>
      </article>

      <div class="therapist-main-flow">
        <article class="therapist-panel training-records-panel">
          <div class="panel-heading records-heading">
            <div>
              <h2>每次训练记录与评分</h2>
              <p>{{ selectedPatient ? `${selectedPatient.username} 最近 ${records.length} 次训练反馈` : '选择患者后显示' }}</p>
            </div>
          </div>

          <div v-if="loadingPatientData" class="success-text">正在汇总训练记录。</div>
          <div v-else-if="records.length" class="therapist-record-list">
            <article v-for="record in displayedRecords" :key="record.attempt_id" class="training-record-row">
              <div class="record-score-block" :class="{ empty: record.overall_score == null }">
                <strong>{{ record.overall_score ?? '--' }}</strong>
                <span>总分</span>
              </div>
              <div class="record-main">
                <div class="record-topline">
                  <strong>{{ record.task_title }}</strong>
                  <span>{{ dateTimeLabel(record.created_at) }}</span>
                </div>
                <p>{{ record.target_text }}</p>
                <div class="record-tags">
                  <span>{{ trainingTypeLabel(record.training_type) }}</span>
                  <span>{{ analysisStatusLabel(record.analysis_status) }}</span>
                  <span v-if="record.recommendation_source">{{ record.recommendation_matched ? '符合推荐' : '未按推荐' }}</span>
                </div>
                <button
                  v-if="record.pronunciation_analysis_id"
                  class="record-review-action"
                  type="button"
                  @click="openPronunciationReview(record)"
                >
                  复核发音 <ChevronRight :size="16" />
                </button>
              </div>
              <div class="record-metric-strip">
                <span>完整度 {{ metricValue(record.process_metrics.script_accuracy, '%') }}</span>
                <span>错误 {{ metricValue(record.process_metrics.error_count, '次') }}</span>
                <span>语速 {{ metricValue(record.process_metrics.speech_rate, '字/min') }}</span>
                <span>相对响度 {{ metricValue(record.process_metrics.loudness, 'dBFS') }}</span>
              </div>
            </article>
            <button v-if="records.length > 3" class="records-expand-button" type="button" @click="showAllRecords = !showAllRecords">
              {{ showAllRecords ? '收起历史记录' : `展开其余 ${records.length - 3} 条记录` }}
              <ChevronRight :size="17" :class="{ rotated: showAllRecords }" />
            </button>
          </div>
          <div v-else class="empty-state">
            <p>暂无训练记录。患者完成一次训练并生成评分后，这里会自动出现。</p>
          </div>
        </article>

        <Teleport to="body">
        <div v-if="selectedPronunciationRecord" class="pronunciation-drawer-backdrop" @click.self="closePronunciationReview">
        <aside class="pronunciation-review-panel" aria-label="精细发音复核">
          <div class="panel-heading">
            <div>
              <h2>精细发音复核</h2>
              <p>{{ selectedPronunciationRecord.task_title }} · {{ pronunciationSummary }}</p>
            </div>
            <button class="icon-button" type="button" title="关闭精细发音复核" :disabled="pronunciationLoading" @click="closePronunciationReview"><X :size="20" /></button>
          </div>
          <p v-if="pronunciationLoading" class="success-text">正在读取字词级评测结果。</p>
          <p v-else-if="pronunciationError" class="error-text">{{ pronunciationError }}</p>
          <template v-else-if="pronunciation">
            <div class="pronunciation-overview">
              <span>准确度 {{ metricValue(pronunciation.overall_accuracy, '%') }}</span>
              <span>流畅度 {{ metricValue(pronunciation.fluency == null ? null : pronunciation.fluency * 100, '%') }}</span>
              <span>完成度 {{ metricValue(pronunciation.completion == null ? null : pronunciation.completion * 100, '%') }}</span>
              <span>覆盖度 {{ metricValue(pronunciation.coverage * 100, '%') }}</span>
              <span>影子分 {{ metricValue(selectedPronunciationRecord.pronunciation_shadow_score, ' 分') }}</span>
              <span>可懂度代理 {{ metricValue(pronunciation.intelligibility_proxy, '%') }}</span>
            </div>
            <p v-if="pronunciation.error_message" class="error-text">{{ pronunciation.error_message }}</p>
            <div class="pronunciation-audio-bar"><AudioPlayback ref="reviewAudio" :src="selectedPronunciationRecord.audio_url" /></div>
            <label v-if="pronunciation.segments.some((item) => item.level === 'phoneme')" class="pronunciation-level-picker">
              复核层级
              <select v-model="segmentLevel">
                <option value="word">字词</option>
                <option value="phoneme">音素</option>
              </select>
            </label>
            <div v-if="pronunciation.segments.length" class="pronunciation-segment-list">
              <button
                v-for="segment in visibleSegments"
                :key="segment.id"
                class="pronunciation-segment"
                :class="{ active: selectedSegment?.id === segment.id }"
                type="button"
                @click="selectSegment(segment)"
              >
                <strong>{{ segment.reference_text || '未标注' }}</strong>
                <span>{{ matchTypeLabel(segment.match_type) }}</span>
                <small>{{ segment.recognized_text || '未识别' }} · {{ metricValue(segment.accuracy, '%') }}</small>
              </button>
            </div>
            <form v-if="selectedSegment" class="pronunciation-correction-form" @submit.prevent="correctSelectedSegment">
              <strong>修正“{{ selectedSegment.reference_text || '该片段' }}”的机器标签</strong>
              <div class="template-form-grid">
                <label>
                  修正类型
                  <select v-model="correctionMatchType">
                    <option value="matched">匹配</option>
                    <option value="addition">多读</option>
                    <option value="omission">漏读</option>
                    <option value="substitution">替换或错读</option>
                    <option value="out_of_vocabulary">词表外</option>
                    <option value="unavailable">无法判断</option>
                  </select>
                </label>
                <label>
                  复核原因
                  <input v-model="correctionReason" maxlength="300" placeholder="简要说明听辨依据" />
                </label>
              </div>
              <div class="form-actions">
                <button class="app-button secondary" type="submit" :disabled="reviewSaving">
                  保存片段修正
                </button>
              </div>
            </form>
            <form class="pronunciation-correction-form" @submit.prevent="saveIntelligibilityReview">
              <strong>人工可懂度记录</strong>
              <div class="template-form-grid">
                <label>
                  听者类型
                  <input v-model="intelligibilityForm.listener_role" maxlength="80" placeholder="例如：治疗师、家属" required />
                </label>
                <label>
                  正确理解比例
                  <input v-model.number="intelligibilityForm.understood_percent" type="number" min="0" max="100" required />
                </label>
                <label>
                  播放次数
                  <input v-model.number="intelligibilityForm.playback_count" type="number" min="1" max="20" required />
                </label>
                <label>
                  听辨环境
                  <input v-model="intelligibilityForm.listening_environment" maxlength="500" placeholder="例如：安静办公室、耳机" />
                </label>
              </div>
              <label>
                听者转写
                <textarea v-model="intelligibilityForm.listener_transcript" rows="2" maxlength="2000" required placeholder="不参考目标文本，按实际听到的内容转写。"></textarea>
              </label>
              <label>
                备注
                <input v-model="intelligibilityForm.notes" maxlength="2000" placeholder="可选" />
              </label>
              <div class="form-actions">
                <button class="app-button secondary" type="submit" :disabled="reviewSaving">保存可懂度记录</button>
              </div>
              <p v-if="pronunciation.intelligibility_reviews.length" class="success-text">已有 {{ pronunciation.intelligibility_reviews.length }} 条人工可懂度记录。</p>
            </form>
            <div class="form-actions">
              <button class="app-button secondary" type="button" :disabled="reviewSaving" @click="confirmVisibleSegments">
                {{ reviewSaving ? '保存中' : '确认当前机器标注' }}
              </button>
              <button class="app-button primary" type="button" :disabled="reviewSaving || pronunciation.review_status === 'completed'" @click="completePronunciationReview">
                {{ pronunciation.review_status === 'completed' ? '已完成复核' : '完成复核' }}
              </button>
            </div>
            <p v-if="pronunciation.revisions.length" class="success-text">已保留 {{ pronunciation.revisions.length }} 条人工审阅记录。</p>
          </template>
        </aside>
        </div>
        </Teleport>

        <article class="therapist-panel">
          <div class="panel-heading">
            <div>
              <h2>训练得分趋势</h2>
              <p>{{ trends?.overall_summary || '按上次、三天、七天、三十天自动汇总。' }}</p>
            </div>
          </div>

          <div v-if="loadingPatientData" class="success-text">正在计算趋势。</div>
          <div v-else-if="trends" class="trend-window-grid">
            <section v-for="bucket in trends.buckets" :key="bucket.key" class="trend-window-card">
              <div>
                <span>{{ bucket.label }}</span>
                <strong>{{ scoreLabel(bucket.avg_overall_score) }}</strong>
              </div>
              <p>{{ bucket.summary }}</p>
              <div class="record-tags">
                <span>{{ bucket.attempt_count }} 次</span>
                <span>完整度 {{ metricValue(bucket.avg_script_accuracy, '%') }}</span>
                <span>错误 {{ metricValue(bucket.avg_error_count, '次') }}</span>
              </div>
            </section>
          </div>
          <div v-else class="empty-state">
            <p>暂无趋势数据。</p>
          </div>
        </article>

        <article class="therapist-panel">
          <div class="panel-heading">
            <div>
              <h2>双标一致性</h2>
              <p>{{ agreement?.summary || '需要两名记录者对同一录音分别完成听辨记录。' }}</p>
            </div>
          </div>
          <div v-if="agreement" class="record-metric-strip">
            <span>人工记录 {{ agreement.listener_review_count }} 条</span>
            <span>双标训练 {{ agreement.double_labeled_attempt_count }} 次</span>
            <span>平均差异 {{ metricValue(agreement.mean_absolute_percent_difference, ' 个百分点') }}</span>
            <span>10% 内一致 {{ metricValue(agreement.within_ten_percent_rate == null ? null : agreement.within_ten_percent_rate * 100, '%') }}</span>
            <span>转写相似 {{ metricValue(agreement.mean_transcript_similarity == null ? null : agreement.mean_transcript_similarity * 100, '%') }}</span>
          </div>
        </article>
      </div>

      <aside class="therapist-side-flow">
        <article class="therapist-panel recommendation-note-panel">
          <div class="panel-heading">
            <div>
              <h2>自然语言调整推荐</h2>
              <p>这里不是复核算法，只是在必要时补充训练方向。</p>
            </div>
          </div>

          <div v-if="recommendation" class="algorithm-recommendation-box">
            <span>算法当前建议</span>
            <strong>{{ recommendation.headline }}</strong>
            <p>{{ recommendation.reason }}</p>
            <div class="record-tags">
              <span>{{ trainingTypeLabel(recommendation.recommended_type) }}</span>
              <span>{{ recommendation.suggested_minutes }} 分钟</span>
              <span>置信度 {{ Math.round(recommendation.confidence * 100) }}%</span>
              <span>策略 {{ recommendation.policy_version }}</span>
            </div>
          </div>

          <div v-if="effects" class="trend-attribution-box" :class="effects.reminder_level">
            <span>趋势归因与提醒</span>
            <strong>{{ effects.therapist_reminder || effects.strategy_hint }}</strong>
            <ul v-if="effects.attribution_points.length">
              <li v-for="point in effects.attribution_points" :key="point">{{ point }}</li>
            </ul>
          </div>

          <form class="recommendation-note-form" @submit.prevent="saveNote">
            <label>
              给算法和患者端的补充说明
              <textarea
                v-model="noteText"
                maxlength="300"
                rows="7"
                placeholder="例如：这周先降低句子长度，重点练习慢一点说完整；如果连续两次错误少于 1 次，再切到场景表达。"
              ></textarea>
            </label>
            <div class="form-actions">
              <button class="app-button primary" type="submit" :disabled="savingNote || !selectedPatientId">
                {{ savingNote ? '保存中' : '保存调整说明' }}
              </button>
              <button class="app-button secondary" type="button" :disabled="savingNote" @click="clearNote">
                清空
              </button>
            </div>
            <p v-if="noteSaved" class="success-text">{{ noteSaved }}</p>
          </form>
        </article>

        <article class="therapist-panel compact-profile-panel">
          <div class="panel-heading">
            <div>
              <h2>能力概览</h2>
              <p>{{ ability ? `更新于 ${dateTimeLabel(ability.updated_at)}` : '选择患者后显示' }}</p>
            </div>
          </div>
          <div v-if="ability" class="compact-profile-grid">
            <div>
              <span>内容</span>
              <strong>{{ ability.current_content_level }}</strong>
            </div>
            <div>
              <span>自主</span>
              <strong>{{ ability.current_autonomy_level }}</strong>
            </div>
            <div>
              <span>置信</span>
              <strong>{{ Math.round(ability.confidence * 100) }}%</strong>
            </div>
          </div>
          <p v-if="ability" class="compact-profile-summary">{{ ability.assessment_summary }}</p>
        </article>

        <details class="therapist-panel task-library-panel">
          <summary class="task-library-summary">
          <div class="panel-heading">
            <div>
              <h2>训练内容库</h2>
              <p>{{ taskTemplates.length }} 条可用材料</p>
            </div>
          </div>
          <ChevronRight :size="18" />
          </summary>

          <div class="task-template-list">
            <article v-for="template in taskTemplates.slice(0, 5)" :key="template.id" class="task-template-row">
              <div>
                <strong>{{ template.title }}</strong>
                <p>{{ template.target_text }}</p>
              </div>
              <div class="record-tags">
                <span>{{ trainingTypeLabel(template.task_type) }}</span>
                <span>{{ template.content_level }} / {{ template.autonomy_level }}</span>
                <span>权重 {{ template.recommendation_weight }}</span>
              </div>
            </article>
          </div>

          <form class="task-template-form" @submit.prevent="saveTemplate">
            <label>
              材料标题
              <input v-model="templateForm.title" maxlength="80" placeholder="例如：家庭问候短句" />
            </label>
            <label>
              训练文本
              <textarea v-model="templateForm.target_text" maxlength="180" rows="3" placeholder="请输入患者需要练习的句子或表达内容。"></textarea>
            </label>
            <div class="template-form-grid">
              <label>
                类型
                <select v-model="templateForm.task_type">
                  <option value="repeat">跟读训练</option>
                  <option value="scenario">场景表达</option>
                </select>
              </label>
              <label>
                难度
                <select v-model="templateForm.content_level">
                  <option v-for="level in contentLevels" :key="level" :value="level">{{ level }}</option>
                </select>
              </label>
              <label>
                自主
                <select v-model="templateForm.autonomy_level">
                  <option v-for="level in autonomyLevels" :key="level" :value="level">{{ level }}</option>
                </select>
              </label>
            </div>
            <div class="form-actions">
              <button class="app-button secondary" type="submit" :disabled="savingTemplate">
                {{ savingTemplate ? '保存中' : '新增材料' }}
              </button>
            </div>
            <p v-if="templateSaved" class="success-text">{{ templateSaved }}</p>
          </form>
        </details>
      </aside>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronRight, FileDown, RefreshCw, Search, X } from 'lucide-vue-next'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import { therapistApi } from '@/api/therapist'
import type {
  AbilityProfile,
  RecommendationEffectSummary,
  TaskTemplate,
  TaskTemplatePayload,
  TherapistPatient,
  TherapistTrainingRecord,
  TherapistTrainingTrends,
  TherapistInterRaterAgreement,
  PronunciationAnalysis,
  PronunciationSegment,
  TrainingRecommendation
} from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const patients = ref<TherapistPatient[]>([])
const patientQuery = ref('')
const showAllRecords = ref(false)
const selectedPatientId = ref('')
const ability = ref<AbilityProfile | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const effects = ref<RecommendationEffectSummary | null>(null)
const records = ref<TherapistTrainingRecord[]>([])
const selectedPronunciationRecord = ref<TherapistTrainingRecord | null>(null)
const pronunciation = ref<PronunciationAnalysis | null>(null)
const pronunciationLoading = ref(false)
const pronunciationError = ref('')
const reviewSaving = ref(false)
const reviewAudio = ref<InstanceType<typeof AudioPlayback> | null>(null)
const selectedSegment = ref<PronunciationSegment | null>(null)
const correctionMatchType = ref('matched')
const correctionReason = ref('')
const segmentLevel = ref<'word' | 'phoneme'>('word')
const intelligibilityForm = ref({
  listener_role: '',
  listener_transcript: '',
  understood_percent: 100,
  playback_count: 1,
  listening_environment: '',
  notes: ''
})
const trends = ref<TherapistTrainingTrends | null>(null)
const agreement = ref<TherapistInterRaterAgreement | null>(null)
const taskTemplates = ref<TaskTemplate[]>([])
const noteText = ref('')
const templateForm = ref<TaskTemplatePayload>({
  task_type: 'repeat',
  title: '',
  instruction: '请跟我说这一句。',
  target_text: '',
  content_level: 'L2',
  autonomy_level: 'S1',
  scene_prompt: null,
  tags: [],
  recommendation_weight: 60,
  is_active: true
})
const loading = ref(true)
const loadingPatientData = ref(false)
const savingNote = ref(false)
const savingTemplate = ref(false)
const exportingReport = ref(false)
const pageError = ref('')
const noteSaved = ref('')
const templateSaved = ref('')
const contentLevels = ['L1', 'L2', 'L3', 'L4', 'L5']
const autonomyLevels = ['S1', 'S2', 'S3', 'S4']

const selectedPatient = computed(() => patients.value.find((item) => item.user_id === selectedPatientId.value))
const filteredPatients = computed(() => {
  const query = patientQuery.value.trim().toLowerCase()
  return query ? patients.value.filter((patient) => patient.username.toLowerCase().includes(query)) : patients.value
})
const displayedRecords = computed(() => showAllRecords.value ? records.value : records.value.slice(0, 3))
const pronunciationSummary = computed(() => {
  if (!pronunciation.value) return '等待加载'
  if (pronunciation.value.status !== 'completed') return pronunciation.value.status === 'unavailable' ? '服务未启用' : '评测未完成'
  return `准确度 ${metricValue(pronunciation.value.overall_accuracy, '%')}，覆盖度 ${metricValue(pronunciation.value.coverage * 100, '%')}`
})
const visibleSegments = computed(() => pronunciation.value?.segments.filter((item) => item.level === segmentLevel.value) || [])

onMounted(async () => {
  try {
    patients.value = await therapistApi.patients()
    taskTemplates.value = await therapistApi.taskTemplates()
    patients.value.sort((left, right) => right.pending_review_count - left.pending_review_count)
    if (patients.value[0]) await selectPatient(patients.value[0].user_id)
  } catch (err) {
    pageError.value = toUserMessage(err, '患者列表加载失败')
  } finally {
    loading.value = false
  }
})

async function selectPatient(patientUserId: string) {
  selectedPatientId.value = patientUserId
  showAllRecords.value = false
  await reloadSelected()
}

async function reloadSelected() {
  if (!selectedPatientId.value) return
  loadingPatientData.value = true
  pageError.value = ''
  noteSaved.value = ''
  try {
    const [abilityResult, recommendationResult, recordsResult, trendsResult, noteResult, effectsResult, agreementResult] = await Promise.all([
      therapistApi.abilityProfile(selectedPatientId.value),
      therapistApi.trainingRecommendation(selectedPatientId.value),
      therapistApi.trainingRecords(selectedPatientId.value),
      therapistApi.trainingTrends(selectedPatientId.value),
      therapistApi.recommendationNote(selectedPatientId.value),
      therapistApi.recommendationEffects(selectedPatientId.value),
      therapistApi.pronunciationInterRaterAgreement(selectedPatientId.value)
    ])
    ability.value = abilityResult
    recommendation.value = recommendationResult
    records.value = recordsResult
    closePronunciationReview()
    trends.value = trendsResult
    effects.value = effectsResult
    agreement.value = agreementResult
    noteText.value = noteResult.note || recommendationResult.therapist_notes || ''
  } catch (err) {
    pageError.value = toUserMessage(err, '患者训练数据加载失败')
  } finally {
    loadingPatientData.value = false
  }
}

async function openPronunciationReview(record: TherapistTrainingRecord) {
  if (!record.pronunciation_analysis_id) return
  selectedPronunciationRecord.value = record
  pronunciation.value = null
  selectedSegment.value = null
  segmentLevel.value = 'word'
  intelligibilityForm.value = { listener_role: '', listener_transcript: '', understood_percent: 100, playback_count: 1, listening_environment: '', notes: '' }
  pronunciationError.value = ''
  pronunciationLoading.value = true
  try {
    pronunciation.value = await therapistApi.pronunciation(record.pronunciation_analysis_id)
  } catch (err) {
    pronunciationError.value = toUserMessage(err, '精细发音评测加载失败')
  } finally {
    pronunciationLoading.value = false
  }
}

function closePronunciationReview() {
  selectedPronunciationRecord.value = null
  pronunciation.value = null
  selectedSegment.value = null
  pronunciationError.value = ''
}

async function saveIntelligibilityReview() {
  if (!pronunciation.value) return
  reviewSaving.value = true
  try {
    pronunciation.value = await therapistApi.addIntelligibilityReview(pronunciation.value.id, {
      listener_role: intelligibilityForm.value.listener_role.trim(),
      listener_transcript: intelligibilityForm.value.listener_transcript.trim(),
      understood_percent: intelligibilityForm.value.understood_percent,
      playback_count: intelligibilityForm.value.playback_count,
      listening_environment: intelligibilityForm.value.listening_environment.trim() || null,
      notes: intelligibilityForm.value.notes.trim() || null
    })
    intelligibilityForm.value = { listener_role: '', listener_transcript: '', understood_percent: 100, playback_count: 1, listening_environment: '', notes: '' }
  } catch (err) {
    pronunciationError.value = toUserMessage(err, '人工可懂度记录保存失败')
  } finally {
    reviewSaving.value = false
  }
}

function seekSegment(startMs: number | null) {
  if (startMs != null) reviewAudio.value?.seek(startMs / 1000)
}

function selectSegment(segment: PronunciationSegment) {
  selectedSegment.value = segment
  correctionMatchType.value = segment.match_type
  correctionReason.value = ''
  seekSegment(segment.start_ms)
}

async function correctSelectedSegment() {
  if (!pronunciation.value || !selectedSegment.value) return
  reviewSaving.value = true
  try {
    const revisedMatchType = correctionMatchType.value
    await therapistApi.revisePronunciation(pronunciation.value.id, {
      segment_id: selectedSegment.value.id,
      metric_name: 'match_type',
      revised_value: { match_type: revisedMatchType },
      judgment: revisedMatchType === selectedSegment.value.match_type ? 'confirmed' : 'corrected',
      error_category: revisedMatchType === selectedSegment.value.match_type ? null : revisedMatchType,
      reason: correctionReason.value.trim() || null
    })
    pronunciation.value = await therapistApi.pronunciation(pronunciation.value.id)
  } catch (err) {
    pronunciationError.value = toUserMessage(err, '片段修正保存失败')
  } finally {
    reviewSaving.value = false
  }
}

async function confirmVisibleSegments() {
  if (!pronunciation.value) return
  reviewSaving.value = true
  try {
    for (const segment of pronunciation.value.segments.filter((item) => item.level === 'word')) {
      await therapistApi.revisePronunciation(pronunciation.value.id, {
        segment_id: segment.id,
        metric_name: 'match_type',
        revised_value: { match_type: segment.match_type },
        judgment: 'confirmed'
      })
    }
    pronunciation.value = await therapistApi.pronunciation(pronunciation.value.id)
  } catch (err) {
    pronunciationError.value = toUserMessage(err, '人工确认保存失败')
  } finally {
    reviewSaving.value = false
  }
}

async function completePronunciationReview() {
  if (!pronunciation.value) return
  reviewSaving.value = true
  try {
    pronunciation.value = await therapistApi.completePronunciationReview(pronunciation.value.id)
  } catch (err) {
    pronunciationError.value = toUserMessage(err, '完成复核失败')
  } finally {
    reviewSaving.value = false
  }
}

async function saveNote() {
  if (!selectedPatientId.value) return
  savingNote.value = true
  noteSaved.value = ''
  pageError.value = ''
  try {
    const note = await therapistApi.saveRecommendationNote(selectedPatientId.value, {
      note: noteText.value.trim() || null
    })
    noteText.value = note.note || ''
    recommendation.value = await therapistApi.trainingRecommendation(selectedPatientId.value)
    noteSaved.value = note.note ? '调整说明已保存，后续推荐会带上这条治疗师提示。' : '调整说明已清空。'
  } catch (err) {
    pageError.value = toUserMessage(err, '调整说明保存失败')
  } finally {
    savingNote.value = false
  }
}

async function exportStageReport() {
  if (!selectedPatientId.value) return
  exportingReport.value = true
  pageError.value = ''
  try {
    const response = await therapistApi.stageReportExport(selectedPatientId.value)
    const url = URL.createObjectURL(response.data)
    const reportWindow = window.open(url, '_blank', 'noopener,noreferrer')
    if (!reportWindow) {
      URL.revokeObjectURL(url)
      throw new Error('浏览器阻止了报告窗口，请允许弹出窗口后重试。')
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (err) {
    pageError.value = toUserMessage(err, '阶段报告导出失败')
  } finally {
    exportingReport.value = false
  }
}

function clearNote() {
  noteText.value = ''
}

async function saveTemplate() {
  savingTemplate.value = true
  templateSaved.value = ''
  pageError.value = ''
  try {
    const payload: TaskTemplatePayload = {
      ...templateForm.value,
      title: templateForm.value.title.trim(),
      instruction: templateForm.value.task_type === 'scenario' ? '请围绕这个场景说清楚自己的需求。' : '请跟我说这一句。',
      target_text: templateForm.value.target_text.trim(),
      tags: templateForm.value.tags || []
    }
    await therapistApi.createTaskTemplate(payload)
    taskTemplates.value = await therapistApi.taskTemplates()
    templateForm.value.title = ''
    templateForm.value.target_text = ''
    templateSaved.value = '训练材料已加入内容库。'
  } catch (err) {
    pageError.value = toUserMessage(err, '训练材料保存失败')
  } finally {
    savingTemplate.value = false
  }
}

function trainingTypeLabel(type: string) {
  return type === 'scenario' ? '场景表达' : '跟读训练'
}

function analysisStatusLabel(status: string) {
  if (status === 'completed') return '已评分'
  if (status === 'failed') return '分析失败'
  return '分析中'
}

function matchTypeLabel(value: string) {
  return { matched: '匹配', addition: '多读', omission: '漏读', substitution: '替换', out_of_vocabulary: '词表外' }[value] || '未判断'
}

function metricValue(value: number | null | undefined, unit: string) {
  if (value == null) return '--'
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1)
  return `${text}${unit}`
}

function scoreLabel(value: number | null | undefined) {
  return value == null ? '--' : `${metricValue(value, '')} 分`
}

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
