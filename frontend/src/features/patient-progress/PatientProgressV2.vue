<template>
  <section class="v2-page patient-readable">
    <header class="v2-page-header"><p class="v2-context">我的进展</p><h1>我最近有没有变化？</h1><p>这里只比较训练条件相同、来源可靠的记录。样本不足时，我们会直接说明。</p></header>
    <div v-if="loading" class="v2-state">正在整理进展…</div>
    <div v-else-if="error" class="v2-state v2-state-error"><strong>进展暂时无法加载</strong><span>{{ error }}</span></div>
    <template v-else-if="progress">
      <section class="progress-lead"><div><span>正式训练</span><strong>{{ progress.training_adherence.completed_sessions }} / {{ progress.training_adherence.formal_sessions }}</strong><small>已完成 / 已开始</small></div><p>{{ progress.recent_summary }}</p></section>
      <section class="v2-section-block"><div class="v2-section-heading"><div><p class="v2-section-label">可比较变化</p><h2>同样条件下的变化</h2></div></div>
        <div class="trend-list"><article v-for="item in progress.comparable_trends" :key="item.code" class="trend-line"><div><strong>{{ item.label }}</strong><span>{{ item.trend.sample_count }} 次记录</span></div><p>{{ item.explanation }}</p><small>{{ item.trend.status === 'measured' ? '可比较' : '数据积累中' }}</small></article></div>
      </section>
      <section class="v2-section-block"><div class="v2-section-heading"><div><p class="v2-section-label">里程碑</p><h2>值得记住的小变化</h2></div></div>
        <p v-if="!progress.milestones.length" class="v2-quiet-copy">完成更多练习后，这里会记录由真实训练事实触发的里程碑。</p>
        <ol v-else class="milestone-list"><li v-for="item in progress.milestones" :key="item.id"><CheckCircle2 :size="22" aria-hidden="true"/><div><strong>{{ item.title }} <em v-if="item.source_status==='mock'">演示数据</em></strong><p>{{ item.description }}</p><small>{{ formatDate(item.achieved_at) }}</small></div></li></ol>
      </section>
    </template>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { CheckCircle2 } from 'lucide-vue-next'; import { v2Api, type ProgressV2 } from '@/api/v2'; import { toUserMessage } from '@/utils/errors'
const progress=ref<ProgressV2|null>(null);const loading=ref(true);const error=ref('');onMounted(async()=>{try{progress.value=await v2Api.progress()}catch(err){error.value=toUserMessage(err,'请稍后再试。')}finally{loading.value=false}});function formatDate(value:string){return new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric'}).format(new Date(value))}
</script>
