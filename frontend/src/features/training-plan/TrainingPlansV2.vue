<template>
  <section class="v2-page therapist-v2-page">
    <header class="v2-page-header"><p class="v2-context">训练方案</p><h1>发布正式训练计划</h1><p>已发布版本不可原地编辑。调整会创建新版本，并从患者下一次新建正式 Session 开始生效。</p></header>
    <section class="plan-patient-picker"><label>患者<select v-model="patientId" @change="loadPatient"><option value="">请选择患者</option><option v-for="item in patients" :key="item.user_id" :value="item.user_id">{{ item.username }}</option></select></label></section>
    <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
    <template v-if="patientId">
      <section class="workspace-band">
        <div class="workspace-band-heading"><div><p class="v2-section-label">Rehabilitation Goal</p><h2>正式康复目标</h2></div></div>
        <form class="plan-form" @submit.prevent="saveGoal"><label>目标类别<input v-model="goalForm.category" required placeholder="例如：功能性沟通" /></label><label class="wide">目标描述<textarea v-model="goalForm.description" required placeholder="写明患者希望在什么日常情境中完成什么表达"></textarea></label><button class="v2-button secondary" :disabled="busy">建立当前目标</button></form>
      </section>
      <section class="workspace-band">
        <div class="workspace-band-heading"><div><p class="v2-section-label">TrainingPlan Draft</p><h2>创建版本化方案</h2></div></div>
        <form class="plan-form" @submit.prevent="createPlan">
          <label class="wide">当前目标<select v-model="planForm.rehabilitation_goal_id" required><option value="">先建立康复目标</option><option v-if="workspace?.rehabilitation_goal" :value="workspace.rehabilitation_goal.id">{{ workspace.rehabilitation_goal.description }}</option></select></label>
          <label>阶段重点<input v-model="planForm.stage_focus" required /></label><label>每次时长（分钟）<input v-model.number="planForm.duration_minutes" type="number" min="1" max="180" /></label>
          <label>难度<select v-model="planForm.difficulty"><option value="supported">支持性</option><option value="standard">标准</option><option value="challenging">挑战性</option></select></label>
          <fieldset class="wide template-picker"><legend>练习编排</legend><p class="v2-quiet-copy">可同时选择复述与情境练习；顺序按下方排列固定到本版本。</p><label v-for="item in templates" :key="item.id" class="template-option"><input v-model="selectedTemplateIds" type="checkbox" :value="item.id" /><span><strong>{{ item.title }}</strong><small>{{ item.task_type === 'scenario' ? '情境练习' : '复述练习' }}</small></span></label></fieldset>
          <button class="v2-button primary" :disabled="busy || !selectedTemplateIds.length">保存草稿</button>
        </form>
      </section>
      <section class="workspace-band"><div class="workspace-band-heading"><div><p class="v2-section-label">Version History</p><h2>方案版本</h2></div></div><div class="plan-version-list"><article v-for="plan in plans" :key="plan.id"><div><span>v{{ plan.version_number }}</span><strong>{{ plan.stage_focus }}</strong><small>{{ plan.status }} · {{ plan.exercise_rules.length }} 项练习</small></div><button v-if="plan.status==='draft'" class="v2-button primary" :disabled="busy" @click="publish(plan.id)">{{ busy?'处理中…':'正式发布' }}</button><span v-else class="status-word">{{ plan.status==='active'?'当前生效':'历史版本' }}</span></article></div></section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { therapistApi } from '@/api/therapist'
import { v2Api, type TrainingPlanV2 } from '@/api/v2'
import type { TaskTemplate, TherapistPatient } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const patients = ref<TherapistPatient[]>([])
const templates = ref<TaskTemplate[]>([])
const selectedTemplateIds = ref<string[]>([])
const patientId = ref(String(route.query.patient || ''))
const workspace = ref<any>(null)
const plans = ref<TrainingPlanV2[]>([])
const busy = ref(false)
const error = ref('')
const goalForm = reactive({ category: 'functional_communication', description: '' })
const planForm = reactive({ rehabilitation_goal_id: '', stage_focus: '日常表达', duration_minutes: 15, difficulty: 'standard' })

async function loadPatient() { workspace.value=null;plans.value=[];error.value='';if (!patientId.value) return; try{[workspace.value, plans.value] = await Promise.all([v2Api.workspace(patientId.value), v2Api.plans(patientId.value)]); planForm.rehabilitation_goal_id = workspace.value.rehabilitation_goal?.id || ''}catch(err){error.value=toUserMessage(err,'患者方案加载失败。')} }
async function saveGoal() { busy.value = true; try { const goal = await v2Api.createGoal(patientId.value, goalForm); planForm.rehabilitation_goal_id = goal.id; await loadPatient() } catch (err) { error.value = toUserMessage(err, '康复目标保存失败。') } finally { busy.value = false } }
async function createPlan() {
  busy.value = true; error.value = ''
  try {
    const selected = templates.value.filter(item => selectedTemplateIds.value.includes(item.id))
    await v2Api.createPlan(patientId.value, { rehabilitation_goal_id: planForm.rehabilitation_goal_id, stage_focus: planForm.stage_focus, duration_minutes: planForm.duration_minutes, difficulty: planForm.difficulty, frequency: 'daily', forms: [...new Set(selected.map(item => item.task_type))], scene_scope: [], prompt_policy: { levels: 3 }, exercise_rules: selected.map((item, index) => ({ task_template_id: item.id, exercise_type: item.task_type, order_index: index, difficulty: planForm.difficulty, prompt_policy: { levels: 3 } })) })
    selectedTemplateIds.value = []; await loadPatient()
  } catch (err) { error.value = toUserMessage(err, '方案草稿保存失败。') } finally { busy.value = false }
}
async function publish(id: string) { if (!window.confirm('发布后该版本不可原地编辑，且只对患者下一次新建的正式训练生效。确认发布吗？')) return; busy.value = true; try { await v2Api.publishPlan(patientId.value, id); await loadPatient() } catch (err) { error.value = toUserMessage(err, '方案发布失败，旧方案仍然有效。') } finally { busy.value = false } }
onMounted(async () => { [patients.value, templates.value] = await Promise.all([therapistApi.patients(), therapistApi.taskTemplates()]); if (patientId.value) await loadPatient() })
</script>
