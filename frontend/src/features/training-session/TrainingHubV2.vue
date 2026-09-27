<template>
  <section class="v2-page patient-readable">
    <header class="v2-page-header"><p class="v2-context">训练</p><h1>按计划完成今天的练习</h1><p>正式训练会计入计划完成情况；额外练习会单独记录。</p></header>
    <div v-if="loading" class="v2-state">正在读取训练状态…</div>
    <div v-else-if="error" class="v2-state v2-state-error"><strong>训练状态加载失败</strong><span>{{ error }}</span><button class="v2-button secondary" @click="load">重新加载</button></div>
    <template v-else-if="home">
      <section class="v2-action-sheet">
        <div>
          <p class="v2-section-label">今日练习</p>
          <h2>{{ home.stage_focus || '等待治疗师发布方案' }}</h2>
          <p>{{ formalDescription }}</p>
          <div v-if="home.daily_plan" class="today-facts" aria-label="今日练习概览">
            <span>{{ home.daily_plan.items.length }} 项练习</span>
            <span>约 {{ home.daily_plan.estimated_duration_minutes }} 分钟</span>
            <span v-if="home.daily_plan.source === 'therapist'">治疗师已调整</span>
          </div>
        </div>
        <button class="v2-button primary" :disabled="!home.active_training_plan || starting" @click="start('formal')">{{ starting ? '正在准备…' : formalLabel }}</button>
      </section>
      <section class="v2-section-block extra-practice-panel">
        <div class="v2-section-heading"><div><p class="v2-section-label">额外练习</p><h2>自己选一项继续练习</h2><p>额外练习会单独记录，不会改变今日练习完成情况。</p></div><button class="v2-button secondary" :disabled="starting" @click="refreshPool">换一批</button></div>
        <div v-if="home.extra_practice" class="extra-practice-groups">
          <div><h3>跟读训练 <small>可选 {{ home.extra_practice.repeat.length }} 条</small></h3><div class="extra-practice-grid"><button v-for="item in home.extra_practice.repeat" :key="item.id" class="extra-practice-card" :disabled="starting" @click="start('extra_practice', [item.id])"><span>{{ difficultyLabel(item.difficulty) }}</span><strong>{{ item.target }}</strong><small>{{ item.display_reason }}</small></button></div></div>
          <div><h3>场景训练 <small>可选 {{ home.extra_practice.scenario.length }} 个</small></h3><div class="extra-practice-grid"><button v-for="item in home.extra_practice.scenario" :key="item.id" class="extra-practice-card" :disabled="starting" @click="start('extra_practice', [item.id])"><span>场景表达</span><strong>{{ item.title }}</strong><small>{{ item.display_reason }}</small></button></div></div>
        </div>
        <p v-else class="v2-quiet-copy">额外练习候选正在准备中。</p>
      </section>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { v2Api, type PatientHomeV2 } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'
const router = useRouter(); const home = ref<PatientHomeV2|null>(null); const loading=ref(true); const starting=ref(false); const error=ref('')
const formalLabel=computed(()=>home.value?.state==='completed'?'查看今天总结':home.value?.state==='in_progress'?'继续正式训练':'开始正式训练')
const formalDescription=computed(()=>!home.value?.active_training_plan?'当前没有有效训练方案。':home.value.state==='completed'?'今天的练习已经完成。':`系统根据今天的安排准备了一小组练习，完成大约需要 ${home.value.estimated_duration||10} 分钟。`)
async function load(){loading.value=true;error.value='';try{home.value=await v2Api.patientHome()}catch(err){error.value=toUserMessage(err,'请稍后再试。')}finally{loading.value=false}}
async function start(kind:'formal'|'extra_practice', taskIds:string[]=[]){if(kind==='formal'&&home.value?.state==='completed'&&home.value.today_session){await router.push(`/training/session/${home.value.today_session.id}/summary`);return}starting.value=true;try{const session=await v2Api.startOrResume(kind, taskIds);await router.push(`/training/session/${session.id}`)}catch(err){error.value=toUserMessage(err,'暂时无法开始训练。')}finally{starting.value=false}}
async function refreshPool(){starting.value=true;try{home.value=home.value?{...home.value,extra_practice:await v2Api.extraPracticePool(true)}:home.value}catch(err){error.value=toUserMessage(err,'暂时无法换一批练习。')}finally{starting.value=false}}
function difficultyLabel(level:string){return level==='L1'||level==='L2'?'初级':level==='L3'?'中级':'高级'}
onMounted(load)
</script>

