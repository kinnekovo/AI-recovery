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
      <section class="v2-section-block extra-practice-entry">
        <div><p class="v2-section-label">额外练习</p><h2>再练一组</h2><p>系统会组合跟读和场景练习。额外练习单独记录，不改变今日练习的完成情况。</p></div>
        <RouterLink v-if="home.active_training_plan" class="v2-button secondary" to="/training/extra">进入额外训练</RouterLink>
        <button v-else class="v2-button secondary" disabled>等待训练方案</button>
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
async function start(kind:'formal'){if(home.value?.state==='completed'&&home.value.today_session){await router.push(`/training/session/${home.value.today_session.id}/summary`);return}starting.value=true;try{const session=await v2Api.startOrResume(kind);await router.push(`/training/session/${session.id}`)}catch(err){error.value=toUserMessage(err,'暂时无法开始训练。')}finally{starting.value=false}}
onMounted(load)
</script>

