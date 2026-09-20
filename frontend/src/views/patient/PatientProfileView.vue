<template>
  <section class="page-stack patient-readable">
    <header class="page-heading"><span class="kicker">长期能力记录</span><h1>我的能力画像</h1><p>这里会随着训练和专业评估逐步更新。它不是诊断或综合能力评分。</p></header>
    <AsyncState :loading="loading" :error="error" :empty="!profile?.dimensions.length" empty-title="记录正在形成" empty-text="完成更多训练或评估后，这里会逐步形成长期能力记录。" @retry="load">
      <div class="summary-strip"><div><small>证据状态</small><StatusBadge :status="profile?.status" /></div><div><small>更新时间</small><strong>{{ profile?.freshness === 'fresh' ? '已包含近期记录' : '等待更多记录' }}</strong></div></div>
      <div class="dimension-grid">
        <article v-for="dimension in profile?.dimensions" :key="dimension.code" class="dimension-card">
          <span class="dimension-icon" aria-hidden="true">{{ iconFor(dimension.code) }}</span><div><h2>{{ labelFor(dimension.code) }}</h2><p>{{ stateText(dimension.status) }}</p></div>
          <dl><div><dt>最近趋势</dt><dd>{{ trendText(dimension.trend) }}</dd></div><div><dt>证据状态</dt><dd>{{ evidenceText(dimension.evidence_sufficiency) }}</dd></div></dl>
        </article>
      </div>
      <aside v-if="profile?.limitations.length" class="warning-banner"><strong>请注意</strong><ul><li v-for="item in profile.limitations" :key="item">{{ item }}</li></ul></aside>
    </AsyncState>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { profileV2Api } from '@/api/profileV2'
import AsyncState from '@/components/common/AsyncState.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { PatientProfileProjection } from '@/types/professional'
const loading=ref(true), error=ref(''); const profile=ref<PatientProfileProjection|null>(null)
const labels:Record<string,string>={content_reproduction:'内容表达',fluency_efficiency:'表达流畅',independence:'独立完成',functional_communication:'情境沟通',voice_status:'声音状态'}
function labelFor(code:string){return labels[code]||code.replace(/_/g,' ')}
function iconFor(code:string){return code.includes('communication')?'对':code.includes('independence')?'自':code.includes('fluency')?'顺':'语'}
function trendText(value:string){return ({improving:'上升',stable:'稳定',declining:'需要关注',insufficient:'数据不足'} as Record<string,string>)[value]||'数据不足'}
function stateText(value:string){return value==='observed'?'已有近期记录':value==='not_observed'?'尚未观察':'记录状态：'+value.replace(/_/g,' ')}
function evidenceText(value:string|number|null){if(typeof value==='number')return value>=.7?'较充分':value>=.4?'逐步积累':'仍需积累';return ({sufficient:'较充分',limited:'仍需积累',insufficient:'数据不足'} as Record<string,string>)[String(value)]||'逐步积累'}
async function load(){loading.value=true;error.value='';try{profile.value=await profileV2Api.patientProfile()}catch(e){error.value=e instanceof Error?e.message:'加载失败'}finally{loading.value=false}}
onMounted(load)
</script>
