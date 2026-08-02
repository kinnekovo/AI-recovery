<template>
  <section class="score-panel">
    <div class="score-total">
      <span>{{ score.overall_score }}</span>
      <p>综合分</p>
    </div>
    <div class="score-detail">
      <h3>{{ score.feedback.strength }}</h3>
      <p>{{ score.feedback.improve }}</p>
      <div class="score-grid">
        <span>内容 {{ score.dimensions.content }}</span>
        <span>清晰 {{ score.dimensions.clarity }}</span>
        <span>流畅 {{ score.dimensions.fluency }}</span>
        <span>音量 {{ score.dimensions.loudness }}</span>
        <span>提示 {{ score.dimensions.prompt_dependence }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ScoreResult } from '@/types/api'

defineProps<{ score: ScoreResult }>()
</script>
