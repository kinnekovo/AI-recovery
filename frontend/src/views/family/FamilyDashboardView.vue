<template>
  <section class="page-stack family-observation-page family-visual-page">
    <div class="page-heading family-heading">
      <span class="kicker">家属端</span>
      <h1>看见练习变化，陪他稳稳往前</h1>
      <p>这里把训练结果转换成家属容易理解的图标和趋势，不展示治疗师用的专业量表。</p>
    </div>

    <section v-if="boundPatients.length" class="family-bound-switcher" aria-label="绑定患者">
      <button
        v-for="patient in boundPatients"
        :key="patient.patient_user_id"
        type="button"
        :class="{ active: patient.patient_user_id === selectedPatientId }"
        @click="selectPatient(patient.patient_user_id)"
      >
        <strong>{{ patient.patient_username }}</strong>
        <span>{{ patient.relationship_label }}</span>
      </button>
    </section>

    <p v-if="loading" class="success-text">正在加载陪伴观察。</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="observation" class="family-visual-grid">
      <article class="family-status-panel">
        <div class="family-status-copy">
          <span>当前患者</span>
          <strong>{{ observation.patient_username }}</strong>
          <p>{{ observation.trend_summary }}</p>
        </div>
        <div class="family-progress-orb" :style="{ '--progress': progressDegrees }">
          <div>
            <strong>{{ observation.progress_percent }}%</strong>
            <span>{{ observation.current_level_label }}</span>
          </div>
        </div>
      </article>

      <article class="family-status-panel family-keep-panel">
        <div>
          <span>训练坚持</span>
          <strong>{{ observation.training_count }} 次</strong>
          <p>其中 {{ observation.completed_recommended_sessions }} 次完成了建议训练。</p>
        </div>
        <div class="family-keep-icon">
          <CalendarCheck aria-hidden="true" :size="34" />
          <span>{{ observation.progress_label }}</span>
        </div>
      </article>

      <article class="family-wide-panel family-level-panel">
        <div class="panel-heading">
          <div>
            <span>当前水平</span>
            <h2>用四个维度看最近一次表现</h2>
          </div>
        </div>
        <div class="family-level-grid">
          <section v-for="item in observation.level_items" :key="item.key" class="family-level-card" :class="item.tone">
            <div class="family-level-icon">
              <component :is="iconFor(item.icon)" :size="24" aria-hidden="true" />
            </div>
            <div>
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <p>{{ item.hint }}</p>
            </div>
            <div class="family-level-bar" aria-hidden="true">
              <i :style="{ width: `${Math.max(0, Math.min(item.level, 100))}%` }"></i>
            </div>
          </section>
        </div>
      </article>

      <article class="family-wide-panel family-trend-panel">
        <div class="panel-heading">
          <div>
            <span>进步趋势</span>
            <h2>最近几次建议训练后的变化</h2>
          </div>
        </div>
        <div v-if="observation.trend_items.length" class="family-trend-track">
          <section v-for="item in observation.trend_items" :key="item.created_at" class="family-trend-step">
            <div class="trend-stick" :style="{ height: `${Math.max(12, item.value)}%` }"></div>
            <strong>{{ item.value }}%</strong>
            <span>{{ item.label }}</span>
          </section>
        </div>
        <p v-else>还需要完成几次训练，系统才能画出稳定趋势。</p>
      </article>

      <article class="family-wide-panel family-recordings-panel">
        <div class="panel-heading">
          <div>
            <span>训练录音</span>
            <h2>最近几次练习可以回听</h2>
          </div>
        </div>
        <div v-if="observation.recent_records.length" class="family-recording-list">
          <section v-for="record in observation.recent_records" :key="record.attempt_id" class="family-recording-row">
            <div>
              <strong>{{ record.task_title }}</strong>
              <p>{{ record.summary }}</p>
              <small>{{ dateTimeLabel(record.created_at) }} · {{ trainingTypeLabel(record.training_type) }}</small>
            </div>
            <AudioPlayback :src="record.audio_url" compact />
          </section>
        </div>
        <p v-else>患者完成训练后，这里会保存最近几次录音，方便家属陪伴回顾。</p>
      </article>

      <article class="family-wide-panel family-companion-panel">
        <div>
          <span>{{ observation.recommendation_source === 'therapist' ? '治疗师建议' : '系统建议' }}</span>
          <h2>{{ observation.recommendation_headline }}</h2>
          <p>{{ observation.strategy_hint }}</p>
        </div>
        <div v-if="observation.family_reminder" class="family-note" :class="observation.reminder_level">
          <HeartHandshake aria-hidden="true" :size="22" />
          <div>
            <strong>陪伴提醒</strong>
            <p>{{ observation.family_reminder }}</p>
          </div>
        </div>
        <div v-if="observation.therapist_note" class="family-note">
          <HeartHandshake aria-hidden="true" :size="22" />
          <div>
            <strong>治疗师补充</strong>
            <p>{{ observation.therapist_note }}</p>
          </div>
        </div>
      </article>
    </section>
    <div v-else-if="!loading && !error" class="empty-state family-binding-empty">
      <p>当前家属账号还没有绑定患者。</p>
      <small>请先由管理员或治疗师建立家属-患者绑定，再查看陪伴观察。</small>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AudioLines,
  CalendarCheck,
  HeartHandshake,
  MessageCircle,
  ShieldCheck,
  Volume2
} from 'lucide-vue-next'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import { familyApi } from '@/api/family'
import type { FamilyBoundPatient, FamilyObservation } from '@/types/api'

const observation = ref<FamilyObservation | null>(null)
const boundPatients = ref<FamilyBoundPatient[]>([])
const selectedPatientId = ref<string | null>(null)
const loading = ref(true)
const error = ref('')

const progressDegrees = computed(() => `${Math.min(Math.max(observation.value?.progress_percent || 0, 0), 100) * 3.6}deg`)

onMounted(async () => {
  try {
    const [patients, initialObservation] = await Promise.all([familyApi.patients(), familyApi.observation()])
    boundPatients.value = patients.length ? patients : initialObservation.bound_patients
    observation.value = initialObservation.selected_patient_user_id ? initialObservation : null
    selectedPatientId.value = initialObservation.selected_patient_user_id
  } catch (err) {
    error.value = err instanceof Error ? err.message : '陪伴观察加载失败'
  } finally {
    loading.value = false
  }
})

async function selectPatient(patientUserId: string) {
  selectedPatientId.value = patientUserId
  loading.value = true
  error.value = ''
  try {
    observation.value = await familyApi.observation(patientUserId)
    boundPatients.value = observation.value.bound_patients
  } catch (err) {
    error.value = err instanceof Error ? err.message : '陪伴观察加载失败'
  } finally {
    loading.value = false
  }
}

function iconFor(name: string) {
  const icons = {
    'audio-lines': AudioLines,
    'message-circle': MessageCircle,
    'shield-check': ShieldCheck,
    'volume-2': Volume2
  }
  return icons[name as keyof typeof icons] || MessageCircle
}

function dateTimeLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function trainingTypeLabel(value: string) {
  return value === 'scenario' ? '场景表达' : '跟读训练'
}
</script>
