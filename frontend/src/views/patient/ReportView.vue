<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">康复记录</span>
      <h1>最近训练概览</h1>
      <p>报告基于已保存的作答评分聚合生成。</p>
    </div>
    <section class="report-panel">
      <div>
        <span class="metric">{{ report?.training_count ?? 0 }}</span>
        <p>训练次数</p>
      </div>
      <div>
        <span class="metric">{{ report?.average_score ?? 0 }}</span>
        <p>平均分</p>
      </div>
      <div class="report-suggestion">
        <strong>下一步建议</strong>
        <p>{{ report?.suggestion || '完成一次训练后生成建议。' }}</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { reportsApi } from '@/api/reports'
import type { LatestReport } from '@/types/api'

const report = ref<LatestReport | null>(null)

onMounted(async () => {
  report.value = await reportsApi.latest()
})
</script>
