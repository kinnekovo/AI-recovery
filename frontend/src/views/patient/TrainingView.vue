<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">进入训练</span>
      <h1>今天先练最合适的一项</h1>
      <p>系统会根据你的能力画像给出建议，你也可以自己选择另一种训练。</p>
    </div>
    <section v-if="recommendation" class="recommendation-panel">
      <div class="recommendation-copy">
        <span class="recommendation-label">
          {{ recommendation.source === 'therapist' ? '治疗师建议' : '系统建议' }}
        </span>
        <h2>{{ recommendation.headline }}</h2>
        <p>{{ recommendation.reason }}</p>
        <small v-if="recommendation.therapist_notes">治疗师备注：{{ recommendation.therapist_notes }}</small>
      </div>
      <div class="recommendation-action">
        <span>{{ recommendation.suggested_minutes }} 分钟</span>
        <RouterLink class="primary-link" :to="recommendedTrainingLink(recommendation)">按建议开始</RouterLink>
      </div>
      <div class="focus-strip">
        <span v-for="point in recommendation.focus_points" :key="point">{{ point }}</span>
      </div>
    </section>
    <p v-if="error" class="error-text">{{ error }}</p>
    <div class="training-choice">
      <RouterLink class="choice-panel" :class="{ recommended: recommendation?.recommended_type === 'repeat' }" to="/training/repeat">
        <span v-if="recommendation?.recommended_type === 'repeat'" class="choice-badge">推荐</span>
        <strong>跟读训练</strong>
        <p>系统展示目标句子，你录音跟读。适合先把一句话说完整、说清楚。</p>
      </RouterLink>
      <RouterLink
        class="choice-panel"
        :class="{ recommended: recommendation?.recommended_type === 'scenario' }"
        to="/training/scenario"
      >
        <span v-if="recommendation?.recommended_type === 'scenario'" class="choice-badge">推荐</span>
        <strong>场景表达</strong>
        <p>围绕生活场景自由表达。适合练习把想法组织起来，说出自己的需求。</p>
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { trainingApi } from '@/api/training'
import type { TrainingRecommendation } from '@/types/api'

const recommendation = ref<TrainingRecommendation | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    recommendation.value = await trainingApi.recommendation()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '暂时无法读取训练建议，可以先手动选择训练。'
  }
})

function recommendedTrainingLink(item: TrainingRecommendation) {
  return {
    path: `/training/${item.recommended_type}`,
    query: {
      recommended: '1',
      source: item.source,
      ...(item.id ? { recommendation_id: item.id } : {}),
      headline: item.headline
    }
  }
}
</script>
