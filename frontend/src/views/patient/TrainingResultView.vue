<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">单题反馈</span>
      <h1>这次训练已经保存</h1>
      <p>分数只是康复辅助反馈，不代表临床诊断。</p>
    </div>
    <ScorePanel v-if="score" :score="score" />
    <div v-else class="empty-state">
      <p>还没有评分结果。</p>
      <RouterLink to="/training">开始一次训练</RouterLink>
    </div>
    <div class="action-row">
      <RouterLink class="secondary-link" to="/training">再练一题</RouterLink>
      <RouterLink class="primary-link" to="/report">查看记录</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ScorePanel from '@/components/report/ScorePanel.vue'
import { useTrainingStore } from '@/stores/training'

const store = useTrainingStore()
const score = computed(() => store.latestScore)
</script>
