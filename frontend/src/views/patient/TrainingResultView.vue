<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">单题反馈</span>
      <h1>这次训练已经保存</h1>
      <p>以下是本次训练的过程性指标和练习建议，不代表临床诊断。</p>
    </div>
    <ProcessFeedbackPanel v-if="feedback" :result="feedback" />
    <div v-else class="empty-state">
      <p>还没有训练反馈。</p>
      <RouterLink to="/training">开始一次训练</RouterLink>
    </div>
    <section v-if="usedRecommendation" class="recommendation-complete">
      <strong>已完成建议训练</strong>
      <p>这次训练会和建议记录放在一起，方便治疗师查看后续表现。</p>
    </section>
    <div class="action-row">
      <RouterLink class="secondary-link" to="/training">再练一题</RouterLink>
      <RouterLink class="primary-link" to="/report">查看记录</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ProcessFeedbackPanel from '@/components/report/ProcessFeedbackPanel.vue'
import { useTrainingStore } from '@/stores/training'

const store = useTrainingStore()
const feedback = computed(() => store.latestFeedback)
const usedRecommendation = computed(() => Boolean(store.currentSession?.recommendation_source))
</script>
