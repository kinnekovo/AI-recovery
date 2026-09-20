<template>
  <section class="page-stack wide-workspace">
    <header class="page-heading"><span class="kicker">Patients</span><h1>患者工作区</h1><p>查看已分配患者并进入评估、画像、策略与受控操作。</p></header>
    <div class="toolbar"><label>搜索患者<input v-model="query" type="search" placeholder="输入姓名或标识符" /></label><label>待处理状态<select v-model="filter"><option value="all">全部</option><option value="pending">有待复核</option><option value="active">训练中</option></select></label></div>
    <AsyncState :loading="loading" :error="error" :empty="filtered.length===0" empty-title="没有匹配的患者" empty-text="调整筛选条件，或确认治疗师与患者已建立分配关系。" @retry="load">
      <div class="data-table-wrap"><table class="data-table"><thead><tr><th>患者</th><th>评估状态</th><th>训练状态</th><th>待复核</th><th>最近评估</th><th></th></tr></thead><tbody><tr v-for="patient in filtered" :key="patient.user_id"><td><strong>{{ patient.username }}</strong><small>{{ patient.user_id }}</small></td><td><StatusBadge :status="patient.assessment_status" /></td><td><StatusBadge :status="patient.training_status" /></td><td>{{ patient.pending_review_count }}</td><td>{{ formatDateTime(patient.latest_assessment_at) }}</td><td><RouterLink class="text-link" :to="`/therapist/patients/${patient.user_id}/overview`">打开工作区</RouterLink></td></tr></tbody></table></div>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { computed,onMounted,ref } from 'vue'; import { therapistApi } from '@/api/therapist'; import AsyncState from '@/components/common/AsyncState.vue'; import StatusBadge from '@/components/common/StatusBadge.vue'; import { formatDateTime } from '@/utils/date'; import type { TherapistPatient } from '@/types/api'
const patients=ref<TherapistPatient[]>([]),loading=ref(true),error=ref(''),query=ref(''),filter=ref('all')
const filtered=computed(()=>patients.value.filter(p=>(!query.value||`${p.username} ${p.user_id}`.toLowerCase().includes(query.value.toLowerCase()))&&(filter.value==='all'||filter.value==='pending'&&p.pending_review_count>0||filter.value==='active'&&p.training_status==='active')))
async function load(){loading.value=true;error.value='';try{patients.value=await therapistApi.patients()}catch(e){error.value=e instanceof Error?e.message:'加载失败'}finally{loading.value=false}} onMounted(load)
</script>
